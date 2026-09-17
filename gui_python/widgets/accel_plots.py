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

import numpy as np
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
        self._cap = int(DEFAULT_WINDOW_S * MAX_FS_HZ) * 2
        self._t: Dict[str, np.ndarray] = {a: np.zeros(self._cap) for a in AXES}
        self._v: Dict[str, np.ndarray] = {a: np.zeros(self._cap) for a in AXES}
        self._idx: Dict[str, int] = {a: 0 for a in AXES}
        self._filled: Dict[str, int] = {a: 0 for a in AXES}
        self._arrivals: Dict[str, int] = {a: 0 for a in AXES}

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

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._redraw)
        self._timer.start(REFRESH_MS)

    # --------------------------------- inputs ---------------------------------

    def push(self, axis: str, t0_ms: int, fs_hz: int, values: Sequence[float]) -> None:
        """Append one batch of samples for `axis` (called for every $ACC frame).

        t0_ms is the timestamp of values[0]; consecutive samples are 1/fs_hz apart.
        """
        n = len(values)
        if n == 0:
            return
        t = t0_ms / 1000.0 + np.arange(n) / fs_hz
        v = np.asarray(values, dtype=float)

        t_buf, v_buf, idx, cap = self._t[axis], self._v[axis], self._idx[axis], self._cap
        end = idx + n
        if end <= cap:
            t_buf[idx:end] = t
            v_buf[idx:end] = v
        else:
            first = cap - idx
            t_buf[idx:cap], v_buf[idx:cap] = t[:first], v[:first]
            t_buf[:end - cap], v_buf[:end - cap] = t[first:], v[first:]

        self._idx[axis] = end % cap
        self._filled[axis] = min(cap, self._filled[axis] + n)
        self._arrivals[axis] += n

    def set_amplitude(self, axis: str, amp_g: int) -> None:
        """Make the y range follow the configured amplitude so a change is visible at once."""
        self._plots[axis].setYRange(-amp_g, amp_g)

    def clear(self) -> None:
        """Forget all samples (on connect / Inicializar)."""
        for axis in AXES:
            self._idx[axis] = 0
            self._filled[axis] = 0
            self._arrivals[axis] = 0
        for curve in self._curves.values():
            curve.setData([], [])

    # --------------------------------- redraw ---------------------------------

    def _redraw(self) -> None:
        for axis in AXES:
            filled = self._filled[axis]
            rate = self._arrivals[axis] / (REFRESH_MS / 1000.0)
            self._arrivals[axis] = 0
            self._plots[axis].setTitle(f"Eje {axis} — {rate:.0f} muestras/s")
            if filled == 0:
                continue

            idx, cap = self._idx[axis], self._cap
            if filled < cap:
                t, v = self._t[axis][:filled], self._v[axis][:filled]
            else:
                t = np.concatenate((self._t[axis][idx:], self._t[axis][:idx]))
                v = np.concatenate((self._v[axis][idx:], self._v[axis][:idx]))

            t_last = t[-1]
            mask = t >= t_last - self.window_s
            self._curves[axis].setData(t[mask], v[mask])
            self._plots[axis].setXRange(t_last - self.window_s, t_last)