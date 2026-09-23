"""@file test_main_window.py
@brief The baud renegotiation state machine in MainWindow, against a stub worker.

Offscreen Qt (see conftest.py), no serial port and no event loop: the test plays the part
of the firmware by calling the slots that SerialWorker's signals would call, and checks
what MainWindow sends and how it leaves the connection panel.
"""
import pytest
from PyQt5.QtCore import QObject, pyqtSignal

import main_window as mw
import widgets.connection_panel as cp


class StubWorker(QObject):
    """@brief SerialWorker stand-in: same signals, records what was sent."""

    frame_received = pyqtSignal(list)
    bad_line = pyqtSignal(str)
    connected = pyqtSignal(str, int)
    disconnected = pyqtSignal()
    baud_changed = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        ## Payloads passed to send(), in order.
        self.sent = []
        ## Baud rates passed to request_baud(), in order.
        self.baud_requests = []

    def send(self, payload):
        self.sent.append(payload)
        return True

    def request_baud(self, baud):
        self.baud_requests.append(baud)

    def open(self, port, baud):
        return True

    def close(self):
        pass


@pytest.fixture
def window(qapp, monkeypatch):
    """@brief A MainWindow wired to a StubWorker and already "connected" at 921600."""
    monkeypatch.setattr(mw, "SerialWorker", StubWorker)
    w = mw.MainWindow()
    w._on_connected("FAKE", 921600)
    return w


def _pick_baud(window, baud):
    """@brief Choose @p baud in the panel, as a user would."""
    combo = window.connection.baud_combo
    combo.setCurrentIndex(combo.findData(baud))


def test_successful_renegotiation(window):
    """@brief Selector -> BAUD -> ACK,BAUD -> switch -> INIT -> ACK,INIT completes the change."""
    _pick_baud(window, 230400)
    assert window.worker.sent == ["BAUD,230400"]
    assert not window.connection.baud_combo.isEnabled()   # locked while in flight
    assert window._baud_pending == 230400

    # The firmware answers at the old speed, then switches; the PC follows.
    window._on_frame(["ACK", "BAUD", "230400"])
    assert window.worker.baud_requests == [230400]

    # The worker reports the port is at the new speed: INIT proves it to the firmware.
    window._on_baud_changed(230400)
    assert window.worker.sent == ["BAUD,230400", "INIT"]
    assert window._baud_pending == 230400                 # not committed yet

    window._on_frame(["ACK", "INIT", "1.0"])
    assert window._baud == 230400
    assert window._baud_pending is None
    assert window.connection.baud_combo.isEnabled()
    assert not window._baud_timer.isActive()


def test_timeout_falls_back_to_the_previous_speed(window):
    """@brief Nothing comes back at the new speed: the PC returns to where the firmware
    will also have reverted (LINK_BAUD_REVERT_MS)."""
    _pick_baud(window, 115200)
    window._on_frame(["ACK", "BAUD", "115200"])
    window._on_baud_changed(115200)

    window._on_baud_timeout()

    assert window.worker.baud_requests == [115200, 921600]
    assert window._baud == 921600
    assert window._baud_pending is None
    assert window.connection.baud_combo.currentData() == 921600
    assert window.connection.baud_combo.isEnabled()


def test_err_aborts_without_waiting_for_the_timeout(window):
    """@brief A refused rate is handled on the spot: the firmware never switched."""
    _pick_baud(window, 460800)
    window._on_frame(["ERR", "BADARG"])

    assert window._baud == 921600
    assert window._baud_pending is None
    assert window.connection.baud_combo.currentData() == 921600
    assert not window._baud_timer.isActive()


def test_disconnect_restores_the_boot_speed(window):
    """@brief A renegotiated speed must not survive the connection.

    The board reboots into LINK_BAUD on the next connect (the GUI pulses EN), so a selector
    still showing the negotiated rate would open the port at a speed nothing is talking at:
    the GUI would report a healthy connection and receive nothing.
    """
    _pick_baud(window, 230400)
    window._on_frame(["ACK", "BAUD", "230400"])
    window._on_baud_changed(230400)
    window._on_frame(["ACK", "INIT", "1.0"])
    assert window._baud == 230400

    window._on_disconnected()

    assert window.connection.baud_combo.currentData() == cp.DEFAULT_BAUD
    assert window._baud == 0
    assert window.worker.sent[-1] != "BAUD,921600"   # restoring the selector sends nothing


def test_reselecting_the_current_speed_sends_nothing(window):
    """@brief Landing back on the speed already in use must not start a renegotiation."""
    _pick_baud(window, 230400)
    window._on_frame(["ACK", "BAUD", "230400"])
    window._on_baud_changed(230400)
    window._on_frame(["ACK", "INIT", "1.0"])
    window.worker.sent.clear()

    _pick_baud(window, 230400)
    assert window.worker.sent == []
