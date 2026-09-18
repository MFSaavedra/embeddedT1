"""@file test_serial_worker.py
@brief SerialWorker connect sequence against a fake port: EN reset pulse, boot wait, ordering.

No hardware and no Qt event loop: the signals are connected with Qt.DirectConnection so
PyQt calls the callables straight from the worker thread instead of queueing them.
"""
import threading
import time

import serial
from PyQt5.QtCore import Qt

import protocol
import serial_worker
from serial_worker import SerialWorker

## Scripted board output: ROM banner (garbage at the link baud), an app log line, a frame.
BOOT_LINES = [
    b"ets Jun  8 2016 00:22:57\r\n",
    b"I (130) main: Tarea1 DAQ firmware ready (link 921600 baud)\r\n",
    protocol.build_frame("ENV,23.4,31"),
]


class FakePort:
    """@brief Stand-in for serial.Serial: records DTR/RTS writes, serves BOOT_LINES once."""

    ## Every instance created, so the test can inspect the port after the worker drops it.
    instances = []

    def __init__(self, port, baudrate, timeout):
        self.port, self.baudrate, self.timeout = port, baudrate, timeout
        self.is_open = True
        ## (line, value) pairs in the order the worker set them.
        self.modem_events = []
        self._lines = list(BOOT_LINES)
        FakePort.instances.append(self)

    @property
    def dtr(self):
        return None

    @dtr.setter
    def dtr(self, value):
        self.modem_events.append(("dtr", value))

    @property
    def rts(self):
        return None

    @rts.setter
    def rts(self, value):
        self.modem_events.append(("rts", value))

    def readline(self):
        if self._lines:
            return self._lines.pop(0)
        time.sleep(self.timeout)
        return b""

    def close(self):
        self.is_open = False


def test_connect_pulses_en_then_waits_for_boot_before_connected(monkeypatch):
    monkeypatch.setattr(serial, "Serial", FakePort)
    monkeypatch.setattr(serial_worker, "RESET_PULSE_S", 0.01)
    monkeypatch.setattr(serial_worker, "BOOT_WAIT_S", 0.3)
    FakePort.instances.clear()

    events = []
    connected = threading.Event()
    worker = SerialWorker()
    direct = Qt.DirectConnection
    worker.bad_line.connect(lambda line: events.append(("bad", line)), direct)
    worker.frame_received.connect(lambda fields: events.append(("frame", fields)), direct)
    worker.connected.connect(
        lambda port, baud: (events.append(("connected", port, baud)), connected.set()), direct)
    worker.error.connect(lambda msg: events.append(("error", msg)), direct)

    t0 = time.monotonic()
    assert worker.open("FAKE", 921600)
    assert connected.wait(2.0), events
    elapsed = time.monotonic() - t0
    worker.close()

    port = FakePort.instances[0]
    # esptool-style hard reset: IO0 high (DTR off), EN low (RTS on), EN released.
    assert port.modem_events == [("dtr", False), ("rts", True), ("rts", False)]
    assert not port.is_open

    kinds = [e[0] for e in events]
    assert "error" not in kinds
    # connected comes after the boot wait, and boot output was still reported as bad lines.
    assert elapsed >= 0.3
    assert kinds.index("connected") > kinds.index("bad")
    assert ("connected", "FAKE", 921600) in events
    assert ("frame", ["ENV", "23.4", "31"]) in events
    assert ("bad", "ets Jun  8 2016 00:22:57") in events


class FakePortInfo:
    """@brief Minimal stand-in for serial.tools.list_ports_common.ListPortInfo."""

    def __init__(self, device, vid=None, manufacturer=None, product=None, description=None):
        self.device, self.vid = device, vid
        self.manufacturer, self.product, self.description = manufacturer, product, description


def test_available_ports_lists_usb_adapters_first_with_labels(monkeypatch):
    fake = [
        FakePortInfo("/dev/ttyS0", description="ttyS0"),                     # legacy COM port
        FakePortInfo("/dev/ttyUSB1", vid=0x0403, product="FT232R USB UART", manufacturer="FTDI"),
        FakePortInfo("/dev/ttyUSB0", vid=0x10C4, manufacturer="Silicon Labs",
                     product="CP2102 USB to UART Bridge Controller",
                     description="CP2102 USB to UART Bridge Controller - CP2102 USB to UART Bridge Controller"),
        FakePortInfo("COM3", vid=0x10C4, manufacturer="Silicon Labs",
                     description="Silicon Labs CP210x USB to UART Bridge (COM3)"),
        FakePortInfo("/dev/ttyS1", description="n/a"),
    ]
    monkeypatch.setattr(serial_worker.list_ports, "comports", lambda: fake)

    # USB adapters (any VID) first, each group sorted by device name ("/" < "C").
    assert serial_worker.available_ports() == [
        ("/dev/ttyUSB0", "/dev/ttyUSB0 — Silicon Labs CP2102 USB to UART Bridge Controller"),
        ("/dev/ttyUSB1", "/dev/ttyUSB1 — FTDI FT232R USB UART"),
        ("COM3", "COM3 — Silicon Labs CP210x USB to UART Bridge (COM3)"),
        ("/dev/ttyS0", "/dev/ttyS0"),
        ("/dev/ttyS1", "/dev/ttyS1"),
    ]
