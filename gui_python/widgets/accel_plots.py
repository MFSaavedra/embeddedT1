"""@file accel_plots.py
@brief Three sliding-window plots, one per axis (spec 2.2.3) - the highest-weighted GUI item.

Design (see TODO.md PY4):
- one numpy ring buffer of (t, value) per axis, sized for the longest window at 1000 Hz;
- push() is called from the serial signal for every ACC frame and must only append;
- a single QTimer repaints all three curves at ~30 fps - never redraw per sample;
- the x axis is in seconds, so a change of fs shows up as denser/sparser points; the
  y range follows the configured amplitude (+-A), so a change of A is obvious at once;
- each plot title shows the *measured* incoming rate, averaged over RATE_WINDOW_S so it
  reads steadily instead of flickering between quantised per-tick values; it doubles as a
  link-health check (a rate below the configured fs means samples are being dropped).
"""
from __future__ import annotations

import time

from typing import Dict, Optional, Sequence

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QVBoxLayout, QWidget

## Axis letters, in display order (top to bottom).
AXES = ("X", "Y", "Z")
## Redraw period in ms (~30 fps).
REFRESH_MS = 33
## Averaging window for the measured samples/s shown in each title, seconds.
RATE_WINDOW_S = 1.0
## Width of the sliding window in seconds.
DEFAULT_WINDOW_S = 5.0
## Highest sample rate the buffers must hold, Hz.
MAX_FS_HZ = 1000


class AccelPlots(QWidget):
    """@brief Vertical stack of three pyqtgraph plots fed by per-axis ring buffers.

    Producers call push(); the widget redraws itself from a QTimer, so the cost of a frame
    arriving is just a numpy slice assignment.
    """

    def __init__(self, parent=None):
        """@brief Allocate the ring buffers, create the plots and start the redraw timer.

        @param parent  Optional QWidget parent.
        """
        super().__init__(parent)
        ## Width of the sliding window in seconds.
        self.window_s = DEFAULT_WINDOW_S
        ## Plot widget per axis.
        self._plots: Dict[str, pg.PlotWidget] = {}
        ## Curve item per axis (the thing setData() is called on).
        self._curves: Dict[str, pg.PlotDataItem] = {}
        ## Ring buffer capacity in samples: twice the window at the highest rate.
        self._cap = int(DEFAULT_WINDOW_S * MAX_FS_HZ) * 2
        ## Sample times in seconds, per axis (ring buffer).
        self._t: Dict[str, np.ndarray] = {a: np.zeros(self._cap) for a in AXES}
        ## Sample values in g, per axis (ring buffer, parallel to _t).
        self._v: Dict[str, np.ndarray] = {a: np.zeros(self._cap) for a in AXES}
        ## Next write position in the ring buffer, per axis.
        self._idx: Dict[str, int] = {a: 0 for a in AXES}
        ## Number of valid samples in the ring buffer (saturates at _cap), per axis.
        self._filled: Dict[str, int] = {a: 0 for a in AXES}
        ## Samples received since the rate window started, per axis.
        self._arrivals: Dict[str, int] = {a: 0 for a in AXES}
        ## Last measured rate in samples/s, per axis (shown in the title).
        self._rate: Dict[str, float] = {a: 0.0 for a in AXES}
        ## Start of the current rate-averaging window (time.monotonic()).
        self._rate_t0 = time.monotonic()

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

        ## Periodic redraw, REFRESH_MS.
        self._timer = QTimer(self)
        # Doxygen would read self._redraw as an attribute.
        # @cond
        self._timer.timeout.connect(self._redraw)
        # @endcond
        self._timer.start(REFRESH_MS)

    # --------------------------------- inputs ---------------------------------

    def push(self, axis: str, t0_ms: int, fs_hz: int, values: Sequence[float]) -> None:
        """@brief Append one batch of samples for @p axis (called for every ACC frame).

        Timestamps are reconstructed as t0 + i / fs. Writes wrap around the ring buffer;
        nothing is drawn here.

        @param axis    "X", "Y" or "Z".
        @param t0_ms   Timestamp of values[0] in ms, as sent by the firmware.
        @param fs_hz   Sample rate of the batch in Hz (consecutive samples are 1/fs apart).
        @param values  Sample values in g, oldest first; an empty batch is ignored.
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
        """@brief Make the y range follow the configured amplitude so a change is visible at once.

        @param axis   "X", "Y" or "Z".
        @param amp_g  Amplitude A in g; the range becomes [-A, +A].
        """
        self._plots[axis].setYRange(-amp_g, amp_g)

    def clear(self) -> None:
        """@brief Forget all samples and blank the curves (on connect / Inicializar)."""
        for axis in AXES:
            self._idx[axis] = 0
            self._filled[axis] = 0
            self._arrivals[axis] = 0
            self._rate[axis] = 0.0
            self._plots[axis].setTitle(f"Eje {axis} — 0 muestras/s")
        self._rate_t0 = time.monotonic()
        for curve in self._curves.values():
            curve.setData([], [])

    # --------------------------------- redraw ---------------------------------

    def _redraw(self) -> None:
        """@brief Timer slot: update the measured rate in each title and repaint the curves.

        Unrolls the ring buffer in chronological order, keeps only the last window_s
        seconds and scrolls the x range so the newest sample sits at the right edge.
        The measured rate is recomputed once every RATE_WINDOW_S from the samples that
        arrived in that window (arrivals / elapsed), not per redraw tick.
        """
        elapsed = time.monotonic() - self._rate_t0
        update_rate = elapsed >= RATE_WINDOW_S
        for axis in AXES:
            filled = self._filled[axis]
            if update_rate:
                self._rate[axis] = self._arrivals[axis] / elapsed
                self._arrivals[axis] = 0
                self._plots[axis].setTitle(f"Eje {axis} — {self._rate[axis]:.0f} muestras/s")
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
        if update_rate:
            self._rate_t0 += elapsed

