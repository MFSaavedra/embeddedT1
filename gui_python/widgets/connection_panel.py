"""Connection panel (spec 2.2.1): port + baud selection, Conectar/Desconectar, Inicializar."""
from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton)

BAUD_RATES = [115200, 230400, 460800, 921600]
DEFAULT_BAUD = 115200   # keep in sync with LINK_BAUD in esp32_firmware/main/app_config.h


class ConnectionPanel(QGroupBox):
    connect_requested = pyqtSignal(str, int)   # port, baud
    disconnect_requested = pyqtSignal()
    init_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Conexión serial", parent)
        self._connected = False

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(140)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.setToolTip("Buscar puertos")

        self.baud_combo = QComboBox()
        for baud in BAUD_RATES:
            self.baud_combo.addItem(str(baud), baud)
        self.baud_combo.setCurrentText(str(DEFAULT_BAUD))

        self.connect_btn = QPushButton("Conectar")
        self.init_btn = QPushButton("Inicializar ESP32")
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
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.init_btn.clicked.connect(self.init_requested)
        self.set_connected(False)

    def set_ports(self, ports: List[str]) -> None:
        """Repopulate the port list, keeping the current choice if it still exists."""
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)
        if not ports:
            self.status_label.setText("No se encontraron puertos")

    def set_connected(self, connected: bool, text: Optional[str] = None) -> None:
        self._connected = connected
        self.connect_btn.setText("Desconectar" if connected else "Conectar")
        self.init_btn.setEnabled(connected)
        for w in (self.port_combo, self.baud_combo, self.refresh_btn):
            w.setEnabled(not connected)
        self.status_label.setText(text or ("Conectado" if connected else "Desconectado"))

    def _on_connect_clicked(self) -> None:
        if self._connected:
            self.disconnect_requested.emit()
            return
        port = self.port_combo.currentText()
        if not port:
            self.status_label.setText("Selecciona un puerto")
            return
        self.connect_requested.emit(port, self.baud_combo.currentData())
