"""@file main_window.py
@brief Main window: wires the panels, the plots and the serial worker together.

Data flow:

    panels ──(Qt signals)──▶ MainWindow._send_*()  ──▶ SerialWorker.send(payload)
    SerialWorker.frame_received ──▶ MainWindow._on_frame(fields) ──▶ plots / env panel / status bar

Nothing here touches pyserial directly and nothing in serial_worker.py touches widgets.
"""
from __future__ import annotations

from typing import List

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

import protocol
from serial_worker import SerialWorker, available_ports
from widgets.accel_plots import AccelPlots
from widgets.config_panel import ConfigPanel
from widgets.connection_panel import ConnectionPanel
from widgets.env_panel import EnvPanel


class MainWindow(QMainWindow):
    """@brief Top-level window: control column on the left, the three plots on the right.

    Owns the SerialWorker and translates between widget signals and protocol payloads in
    both directions. Also keeps the valid / rejected frame counters shown in the status bar.
    """

    def __init__(self, parent=None):
        """@brief Build the widgets, lay them out and connect every signal.

        The configuration panel starts disabled and is only enabled while connected.

        @param parent  Optional QWidget parent.
        """
        super().__init__(parent)
        self.setWindowTitle("Tarea 1 CC5328 — Adquisición de datos ESP32")

        ## Serial I/O thread (see serial_worker.py).
        self.worker = SerialWorker(self)
        ## Port / baud / connect / init panel (spec 2.2.1).
        self.connection = ConnectionPanel()
        ## Per-axis and environmental configuration panel (spec 2.2.2).
        self.config = ConfigPanel()
        ## Temperature / humidity indicators (spec 2.2.3).
        self.env = EnvPanel()
        ## Sliding-window plots, one per axis (spec 2.2.3).
        self.plots = AccelPlots()

        # ---- layout: control column on the left, plots on the right ----
        left = QVBoxLayout()
        left.addWidget(self.connection)
        left.addWidget(self.config)
        left.addWidget(self.env)
        left.addStretch(1)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(560)

        root = QHBoxLayout()
        root.addWidget(left_widget)
        root.addWidget(self.plots, 1)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        ## Frames that passed the checksum and were understood.
        self._frames_ok = 0
        ## Lines that were not frames, failed the checksum, or had malformed fields.
        self._frames_bad = 0
        ## Status-bar label showing both counters.
        self._counter_label = QLabel()
        self.statusBar().addPermanentWidget(self._counter_label)
        self._update_counters()

        # ---- wiring (hidden from Doxygen, which would read each self._callback as an attribute) ----
        # @cond
        self.connection.refresh_requested.connect(self._refresh_ports)
        self.connection.connect_requested.connect(self._connect)
        self.connection.disconnect_requested.connect(self.worker.close)
        self.connection.init_requested.connect(self._send_init)
        self.config.axis_changed.connect(self._send_axis_config)
        self.config.env_period_changed.connect(self._send_env_period)

        self.worker.connected.connect(self._on_connected)
        self.worker.disconnected.connect(self._on_disconnected)
        self.worker.error.connect(self._on_error)
        self.worker.frame_received.connect(self._on_frame)
        self.worker.bad_line.connect(self._on_bad_line)
        # @endcond

        self.config.setEnabled(False)
        self._refresh_ports()

    # ------------------------------ connection ------------------------------

    def _refresh_ports(self) -> None:
        """@brief Rescan the serial ports and refill the connection panel's port list."""
        self.connection.set_ports(available_ports())

    def _connect(self, port: str, baud: int) -> None:
        """@brief Ask the worker to open @p port at @p baud (result arrives via signals).

        The worker resets the board and waits for it to boot before emitting connected,
        so the panel shows an intermediate message for about a second.

        @param port  Device name chosen in the connection panel.
        @param baud  Baud rate chosen in the connection panel.
        """
        if self.worker.open(port, baud):
            self.connection.set_connected(False, f"Conectando a {port}… (reiniciando ESP32)")

    def _on_connected(self, port: str, baud: int) -> None:
        """@brief Port open and board rebooted: enable the controls and clear stale data.

        @param port  Device name that was opened.
        @param baud  Baud rate in use.
        """
        self.connection.set_connected(True, f"Conectado a {port} @ {baud}")
        self.config.setEnabled(True)
        self.plots.clear()
        self.env.clear()

    def _on_disconnected(self) -> None:
        """@brief Port closed (by the user or by an error): disable the controls."""
        self.connection.set_connected(False)
        self.config.setEnabled(False)

    def _on_error(self, message: str) -> None:
        """@brief Show a worker error in the status bar for 5 s.

        @param message  Human-readable text from SerialWorker.error.
        """
        self.statusBar().showMessage(message, 5000)

    # --------------------------- outgoing commands ---------------------------
    # Payloads follow README.md "Protocolo"; update both sides together.

    def _send_init(self) -> None:
        """@brief Send INIT. The panel is reset only when the matching ACK arrives."""
        self.worker.send(protocol.CMD_INIT)

    def _send_axis_config(self, axis: str, func: int, amp_g: int, fs_hz: int) -> None:
        """@brief Send a CFG command for one axis and adjust that plot's y range at once.

        @param axis   "X", "Y" or "Z".
        @param func   Waveform 1..3.
        @param amp_g  Amplitude in g: 4, 8 or 16.
        @param fs_hz  Sample rate in Hz: 50, 100, 200, 500 or 1000.
        """
        self.worker.send(f"{protocol.CMD_CFG},{axis},{func},{amp_g},{fs_hz}")
        self.plots.set_amplitude(axis, amp_g)

    def _send_env_period(self, seconds: int) -> None:
        """@brief Send an ENV command with the new environmental period.

        @param seconds  30 or 60.
        """
        self.worker.send(f"{protocol.CMD_ENV},{seconds}")

    # --------------------------- incoming frames ----------------------------

    def _on_frame(self, fields: List[str]) -> None:
        """@brief Route one valid frame by its type and update the counters.

        - ACC: fields are axis, t0_ms, fs_hz, then the sample values -> AccelPlots.push().
        - ENV: temperature and humidity -> EnvPanel.update_values().
        - ACK: shown in the status bar; ACK,INIT also resets the config panel and plots to
          the spec defaults, since the firmware has just done the same.
        - ERR: shown in the status bar.

        A frame with a valid checksum but malformed fields is counted as rejected instead of
        valid, so the two counters stay mutually exclusive.

        @param fields  Payload fields from SerialWorker.frame_received; fields[0] is the type.
        """
        self._frames_ok += 1
        kind = fields[0]
        if kind == protocol.MSG_ACC:
            try:
                axis, t0_ms, fs_hz = fields[1], int(fields[2]), int(fields[3])
                values = [float(v) for v in fields[4:]]
                self.plots.push(axis, t0_ms, fs_hz, values)
            except (ValueError, IndexError):
                self._frames_ok -= 1
                self._frames_bad += 1
        elif kind == protocol.MSG_ENV:
            try:
                temp_c, hum_pct = float(fields[1]), int(fields[2])
                self.env.update_values(temp_c, hum_pct)
            except (ValueError, IndexError):
                self._frames_ok -= 1
                self._frames_bad += 1
        elif kind == protocol.MSG_ACK:
            self.statusBar().showMessage("ESP32: OK " + ",".join(fields[1:]), 3000)
            if len(fields) > 1 and fields[1] == protocol.CMD_INIT:
                self.config.reset_defaults()
                self.plots.clear()
                self.env.clear()      # the firmware sends a fresh $ENV right after this ACK
                for axis in self.config.axes:
                    self.plots.set_amplitude(axis, 4)
        elif kind == protocol.MSG_ERR:
            self.statusBar().showMessage("ESP32: ERROR " + ",".join(fields[1:]), 5000)
        self._update_counters()

    def _on_bad_line(self, _line: str) -> None:
        """@brief Count a line that was not a valid frame (boot output, logs, corruption).

        @param _line  The rejected line; currently unused beyond counting.
        """
        self._frames_bad += 1
        self._update_counters()

    def _update_counters(self) -> None:
        """@brief Refresh the "tramas OK / rechazadas" label in the status bar."""
        self._counter_label.setText(
            f"tramas OK: {self._frames_ok}   rechazadas: {self._frames_bad}")

    # ----------------------------- close ----------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """@brief Close the serial port before the window goes away.

        @param event  QCloseEvent passed by Qt.
        """
        self.worker.close()
        super().closeEvent(event)
