"""Sensor configuration panel (spec 2.2.2).

Independent waveform / amplitude / sample-rate selectors for each accelerometer axis plus
the transmission period of the environmental sensor. Defaults mirror app_config.h.
"""
from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QVBoxLayout, QWidget)

FUNCTIONS = [(1, "1 · Armónica"), (2, "2 · Modulada AM"), (3, "3 · Multicomp.")]
AMPLITUDES_G = [4, 8, 16]
SAMPLE_RATES_HZ = [50, 100, 200, 500, 1000]
ENV_PERIODS_S = [30, 60]
AXES = ("X", "Y", "Z")

DEFAULT_FUNC = 1
DEFAULT_AMP_G = 4
DEFAULT_FS_HZ = 100
DEFAULT_ENV_S = 30


def _combo(items: Sequence[Tuple[int, str]], default: int) -> QComboBox:
    combo = QComboBox()
    for value, label in items:
        combo.addItem(label, value)
    combo.setCurrentIndex([v for v, _ in items].index(default))
    return combo


class AxisConfigWidget(QGroupBox):
    """Selectors for one axis. Emits changed(axis, func, amp_g, fs_hz) on any change."""

    changed = pyqtSignal(str, int, int, int)

    def __init__(self, axis: str, parent=None):
        super().__init__(f"Eje {axis}", parent)
        self.axis = axis
        self.func_combo = _combo(FUNCTIONS, DEFAULT_FUNC)
        self.amp_combo = _combo([(a, f"{a} g") for a in AMPLITUDES_G], DEFAULT_AMP_G)
        self.fs_combo = _combo([(f, f"{f} Hz") for f in SAMPLE_RATES_HZ], DEFAULT_FS_HZ)

        form = QFormLayout(self)
        form.addRow("Función", self.func_combo)
        form.addRow("Amplitud", self.amp_combo)
        form.addRow("Muestreo", self.fs_combo)

        for combo in (self.func_combo, self.amp_combo, self.fs_combo):
            combo.currentIndexChanged.connect(self._emit_changed)

    def values(self) -> Tuple[int, int, int]:
        return (self.func_combo.currentData(), self.amp_combo.currentData(),
                self.fs_combo.currentData())

    def reset_defaults(self) -> None:
        """Show the defaults without emitting changed() (used after Inicializar)."""
        for combo, value in ((self.func_combo, DEFAULT_FUNC), (self.amp_combo, DEFAULT_AMP_G),
                             (self.fs_combo, DEFAULT_FS_HZ)):
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)

    def _emit_changed(self, _index: int) -> None:
        self.changed.emit(self.axis, *self.values())


class ConfigPanel(QWidget):
    axis_changed = pyqtSignal(str, int, int, int)   # axis, func, amp_g, fs_hz
    env_period_changed = pyqtSignal(int)            # seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.axes: Dict[str, AxisConfigWidget] = {a: AxisConfigWidget(a) for a in AXES}
        self.env_combo = _combo([(p, f"{p} s") for p in ENV_PERIODS_S], DEFAULT_ENV_S)

        accel_box = QGroupBox("Acelerómetro")
        accel_row = QHBoxLayout(accel_box)
        for widget in self.axes.values():
            accel_row.addWidget(widget)
            widget.changed.connect(self.axis_changed)

        env_box = QGroupBox("Sensor ambiental")
        env_row = QHBoxLayout(env_box)
        env_row.addWidget(QLabel("Periodo de envío"))
        env_row.addWidget(self.env_combo, 1)
        self.env_combo.currentIndexChanged.connect(
            lambda _i: self.env_period_changed.emit(self.env_combo.currentData()))

        layout = QVBoxLayout(self)
        layout.addWidget(accel_box)
        layout.addWidget(env_box)

    def reset_defaults(self) -> None:
        for widget in self.axes.values():
            widget.reset_defaults()
        self.env_combo.blockSignals(True)
        self.env_combo.setCurrentIndex(self.env_combo.findData(DEFAULT_ENV_S))
        self.env_combo.blockSignals(False)
