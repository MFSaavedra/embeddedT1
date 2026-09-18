"""@file connection_panel.py
@brief Connection panel (spec 2.2.1): port + baud selection, Conectar/Desconectar, Inicializar.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton)

## Baud rates offered in the combo box (the higher ones are needed for 3 x 1000 Hz).
BAUD_RATES = [115200, 230400, 460800, 921600]
## Preselected baud rate; keep in sync with LINK_BAUD in esp32_firmware/main/app_config.h.
DEFAULT_BAUD = 115200


class ConnectionPanel(QGroupBox):
    """@brief Port / baud selectors plus the Conectar and Inicializar ESP32 buttons.

    The panel only emits requests; MainWindow performs them and reports back through
    set_ports() and set_connected().
    """

    ## User pressed Conectar: (port, baud).
    connect_requested = pyqtSignal(str, int)
    ## User pressed Desconectar.
    disconnect_requested = pyqtSignal()
    ## User pressed Inicializar ESP32.
    init_requested = pyqtSignal()
    ## User pressed the refresh button next to the port list.
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        """@brief Build the widgets in their disconnected state.

        @param parent  Optional QWidget parent.
        """
        super().__init__("Conexión serial", parent)
        ## Mirrors the last set_connected() call; decides what the connect button does.
        self._connected = False

        ## Serial port selector, filled by set_ports().
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(140)
        ## Rescans the ports (emits refresh_requested).
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.setToolTip("Buscar puertos")

        ## Baud rate selector; item data holds the integer value.
        self.baud_combo = QComboBox()
        for baud in BAUD_RATES:
            self.baud_combo.addItem(str(baud), baud)
        self.baud_combo.setCurrentText(str(DEFAULT_BAUD))

        ## Toggles between Conectar and Desconectar depending on the state.
        self.connect_btn = QPushButton("Conectar")
        ## Sends INIT; only enabled while connected.
        self.init_btn = QPushButton("Inicializar ESP32")
        ## One-line connection status.
        self.status_label = QLabel("Desconectado")

        port_row = QHBoxLayout()
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_btn)

        grid = QGridLayout(self)
        grid.addWidget(QLabel("Puerto"), 0, 0)
        grid.addLayout(port_row, 0, 1)
        grid.addWidget(QLabel("Baud rate"), 1, 0)
        grid.addWidget(self.baud_combo, 1, 1)
        grid.addWidget(self.connect_btn, 2, 0, 1, 2)
        grid.addWidget(self.init_btn, 3, 0, 1, 2)
        grid.addWidget(self.status_label, 4, 0, 1, 2)

        self.refresh_btn.clicked.connect(self.refresh_requested)
        # Doxygen would read self._on_connect_clicked as an attribute.
        # @cond
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        # @endcond
        self.init_btn.clicked.connect(self.init_requested)
        self.set_connected(False)

    def set_ports(self, ports: List[str]) -> None:
        """@brief Repopulate the port list, keeping the current choice if it still exists.

        @param ports  Device names, e.g. from serial_worker.available_ports().
        """
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)
        if not ports:
            self.status_label.setText("No se encontraron puertos")

    def set_connected(self, connected: bool, text: Optional[str] = None) -> None:
        """@brief Reflect the connection state: button labels, enabled widgets, status text.

        While connected the port, baud and refresh controls are locked and Inicializar is
        enabled; while disconnected the opposite.

        @param connected  True if a port is open.
        @param text       Status text; defaults to "Conectado" / "Desconectado".
        """
        self._connected = connected
        self.connect_btn.setText("Desconectar" if connected else "Conectar")
        self.init_btn.setEnabled(connected)
        for w in (self.port_combo, self.baud_combo, self.refresh_btn):
            w.setEnabled(not connected)
        self.status_label.setText(text or ("Conectado" if connected else "Desconectado"))

    def _on_connect_clicked(self) -> None:
        """@brief Emit disconnect_requested or connect_requested depending on the state.

        Does nothing (beyond a hint in the status label) if no port is selected.
        """
        if self._connected:
            self.disconnect_requested.emit()
            return
        port = self.port_combo.currentText()
        if not port:
            self.status_label.setText("Selecciona un puerto")
            return
        self.connect_requested.emit(port, self.baud_combo.currentData())
