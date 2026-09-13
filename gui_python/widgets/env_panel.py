"""Temperature / humidity indicators (spec 2.2.3, "Variables ambientales")."""
from __future__ import annotations

import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel


class EnvPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Variables ambientales", parent)
        self.temp_label = QLabel("-- °C")
        self.hum_label = QLabel("-- %")
        self.updated_label = QLabel("última lectura: —")
        for label in (self.temp_label, self.hum_label):
            label.setStyleSheet("font-size: 28px; font-weight: bold;")
            label.setAlignment(Qt.AlignCenter)

        grid = QGridLayout(self)
        grid.addWidget(QLabel("Temperatura"), 0, 0, Qt.AlignCenter)
        grid.addWidget(QLabel("Humedad"), 0, 1, Qt.AlignCenter)
        grid.addWidget(self.temp_label, 1, 0)
        grid.addWidget(self.hum_label, 1, 1)
        grid.addWidget(self.updated_label, 2, 0, 1, 2, Qt.AlignCenter)
        # TODO(PY5, optional): add a small pyqtgraph history plot of both series here.

    def update_values(self, temp_c: float, hum_pct: int) -> None:
        self.temp_label.setText(f"{temp_c:.1f} °C")
        self.hum_label.setText(f"{hum_pct} %")
        self.updated_label.setText(time.strftime("última lectura: %H:%M:%S"))
        # TODO(PY5): append (time, temp, hum) to a history list for the optional plot.

    def clear(self) -> None:
        self.temp_label.setText("-- °C")
        self.hum_label.setText("-- %")
        self.updated_label.setText("última lectura: —")
