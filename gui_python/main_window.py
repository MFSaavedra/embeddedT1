"""Main window: wires the panels, the plots and the serial worker together.

Data flow
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tarea 1 CC5328 — Adquisición de datos ESP32")

        self.worker = SerialWorker(self)
        self.connection = ConnectionPanel()
        self.config = ConfigPanel()
        self.env = EnvPanel()
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

        self._frames_ok = 0
        self._frames_bad = 0
        self._counter_label = QLabel()
        self.statusBar().addPermanentWidget(self._counter_label)
        self._update_counters()

        # ---- wiring ----
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

        self.config.setEnabled(False)
        self._refresh_ports()

    # ------------------------------------------------------------ connection

    def _refresh_ports(self) -> None:
        self.connection.set_ports(available_ports())

    def _connect(self, port: str, baud: int) -> None:
        self.worker.open(port, baud)

    def _on_connected(self, port: str, baud: int) -> None:
        self.connection.set_connected(True, f"Conectado a {port} @ {baud}")
        self.config.setEnabled(True)
        self.plots.clear()
        self.env.clear()

    def _on_disconnected(self) -> None:
        self.connection.set_connected(False)
        self.config.setEnabled(False)

    def _on_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

    # ------------------------------------------------------ outgoing commands
    # Payloads follow the DRAFT protocol in README.md; update both sides together.

    def _send_init(self) -> None:
        if self.worker.send(protocol.CMD_INIT):
            # TODO(PY3): wait for $ACK,INIT before resetting the panel (optimistic for now)
            self.config.reset_defaults()
            self.plots.clear()
            for axis in self.config.axes:
                self.plots.set_amplitude(axis, 4)

    def _send_axis_config(self, axis: str, func: int, amp_g: int, fs_hz: int) -> None:
        self.worker.send(f"{protocol.CMD_CFG},{axis},{func},{amp_g},{fs_hz}")
        self.plots.set_amplitude(axis, amp_g)

    def _send_env_period(self, seconds: int) -> None:
        self.worker.send(f"{protocol.CMD_ENV},{seconds}")

    # ------------------------------------------------------- incoming frames

    def _on_frame(self, fields: List[str]) -> None:
        self._frames_ok += 1
        kind = fields[0]
        if kind == protocol.MSG_ACC:
            # TODO(PY2): fields = ["ACC", axis, t0_ms, fs_hz, v1, v2, ...] (README "Protocol")
            #   -> self.plots.push(axis, int(t0_ms), int(fs_hz), [float(v) for v in values])
            # Wrap the conversions in try/except ValueError and count malformed frames.
            pass
        elif kind == protocol.MSG_ENV:
            # TODO(PY2): fields = ["ENV", temp_c, hum_pct] -> self.env.update_values(float, int)
            pass
        elif kind == protocol.MSG_ACK:
            self.statusBar().showMessage("ESP32: OK " + ",".join(fields[1:]), 3000)
        elif kind == protocol.MSG_ERR:
            self.statusBar().showMessage("ESP32: ERROR " + ",".join(fields[1:]), 5000)
        self._update_counters()

    def _on_bad_line(self, _line: str) -> None:
        self._frames_bad += 1
        self._update_counters()

    def _update_counters(self) -> None:
        self._counter_label.setText(
            f"tramas OK: {self._frames_ok}   rechazadas: {self._frames_bad}")

    # ---------------------------------------------------------------- close

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.worker.close()
        super().closeEvent(event)
