"""Three sliding-window plots, one per axis (spec 2.2.3) - the highest-weighted GUI item.

Design (see TODO.md PY4):
  * one numpy ring buffer of (t, value) per axis, sized for the longest window at 1000 Hz;
  * push() is called from the serial signal for every $ACC frame and must only append;
  * a single QTimer repaints all three curves at ~30 fps - never redraw per sample;
  * the x axis is in seconds, so a change of fs shows up as denser/sparser points; the
    y range follows the configured amplitude (+-A), so a change of A is obvious at once;
  * each plot title shows the *measured* incoming rate, which doubles as a link-health check.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np  # noqa: F401  (ring buffers, PY4)
import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QVBoxLayout, QWidget

AXES = ("X", "Y", "Z")
REFRESH_MS = 33            # ~30 fps
DEFAULT_WINDOW_S = 5.0     # width of the sliding window
MAX_FS_HZ = 1000


class AccelPlots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.window_s = DEFAULT_WINDOW_S
        self._plots: Dict[str, pg.PlotWidget] = {}
        self._curves: Dict[str, pg.PlotDataItem] = {}

        layout = QVBoxLayout(self)
        for axis in AXES:
            plot = pg.PlotWidget(title=f"Eje {axis}")
            plot.setLabel("left", "aceleración", units="g")
            plot.setLabel("bottom", "tiempo", units="s")
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setYRange(-4, 4)
            self._curves[axis] = plot.plot(pen=pg.mkPen(width=1))
            self._plots[axis] = plot
            layout.addWidget(plot)

        # TODO(PY4): allocate the ring buffers, e.g. per axis two np.empty(capacity) arrays
        # (t_s, value) plus a write index, capacity = int(DEFAULT_WINDOW_S * MAX_FS_HZ) * 2.

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._redraw)
        self._timer.start(REFRESH_MS)

    # ------------------------------------------------------------------ inputs

    def push(self, axis: str, t0_ms: int, fs_hz: int, values: Sequence[float]) -> None:
        """Append one batch of samples for `axis` (called for every $ACC frame).

        t0_ms is the timestamp of values[0]; consecutive samples are 1/fs_hz apart.
        """
        # TODO(PY4): t = t0_ms / 1000 + np.arange(len(values)) / fs_hz; append to the buffer.
        # Also count arrivals here to compute the measured rate shown in the title.
        pass

    def set_amplitude(self, axis: str, amp_g: int) -> None:
        """Make the y range follow the configured amplitude so a change is visible at once."""
        self._plots[axis].setYRange(-amp_g, amp_g)

    def clear(self) -> None:
        """Forget all samples (on connect / Inicializar)."""
        # TODO(PY4): reset ring-buffer indices.
        for curve in self._curves.values():
            curve.setData([], [])

    # ----------------------------------------------------------------- redraw

    def _redraw(self) -> None:
        # TODO(PY4): for each axis take the newest `window_s` seconds from the ring buffer,
        # curve.setData(t, v), keep the x range as [t_last - window_s, t_last], and update the
        # title: plot.setTitle(f"Eje {axis} — {measured_rate:.0f} muestras/s").
        pass
