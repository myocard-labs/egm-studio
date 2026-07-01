"""Composable trace display (ADR-024): TraceWidget + TraceContainer.

ADR-024 models a multi-trace view as vertically-stacked tiles sharing one X-axis
(the clinical-system convention, N from 1 to 64+). ``TraceWidget`` is the unit — a
pyqtgraph ``PlotItem`` that renders one trace + its metadata title.
``TraceContainer`` is a ``GraphicsLayoutWidget`` that hosts N of them as stacked
rows with X-axes linked, so pan / zoom on any tile moves them all. v0.1 usually
uses N=1; the layout is already correct for larger N.

Colours come from the active theme via a :class:`~myocard_egm_studio.gui.theme.PlotPalette`
(pyqtgraph plots aren't QSS-styled), and ``restyle`` re-applies a new one when the
theme changes.

pyqtgraph ships no type information, so its base classes are ``Any``; the two
``# type: ignore[misc]`` below are the deliberate subclass-of-Any acknowledgements.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray

from myocard_egm_studio.gui.theme import DEFAULT_THEME, PlotPalette, plot_palette

_TRACE_WIDTH = 1
_GRID_ALPHA = 0.15
_AXIS_TIME = "time (ms)"
_AXIS_AMP = "mV"


@dataclass(frozen=True)
class TraceData:
    """One trace to display: samples + sampling rate + a metadata label."""

    signal: NDArray[np.float64]
    fs_hz: float
    label: str = ""


def _time_ms(n: int, fs_hz: float) -> NDArray[np.float64]:
    """Sample-index -> milliseconds axis for ``n`` samples at ``fs_hz``."""
    return np.arange(n, dtype=np.float64) / fs_hz * 1000.0


class TraceWidget(pg.PlotItem):  # type: ignore[misc]
    """One trace as a pyqtgraph PlotItem — the ADR-024 composable unit.

    X-axis is milliseconds, Y is amplitude (mV); mouse pan / zoom is limited to X
    (the time-scale slider in B5.2 drives the same range). The metadata label is
    the plot title. Colours come from a theme :class:`PlotPalette`.
    """

    def __init__(self, data: TraceData, *, palette: PlotPalette | None = None) -> None:
        super().__init__()
        self._data = data
        t_ms = _time_ms(data.signal.size, data.fs_hz)
        self._curve = self.plot(t_ms, data.signal)
        self.setLabel("left", _AXIS_AMP)
        self.setLabel("bottom", _AXIS_TIME)
        self.getAxis("left").enableAutoSIPrefix(False)  # plain mV, not "mV (x0.001)"
        self.getAxis("bottom").enableAutoSIPrefix(False)  # plain ms
        self.showGrid(x=True, y=True, alpha=_GRID_ALPHA)
        self.getViewBox().setMouseEnabled(x=True, y=False)
        self.apply_palette(palette or plot_palette(DEFAULT_THEME))

    def apply_palette(self, palette: PlotPalette) -> None:
        """Recolour the trace pen, axes, and title for a theme (used on theme change)."""
        self._curve.setPen(pg.mkPen(palette.trace, width=_TRACE_WIDTH))
        pen = pg.mkPen(palette.foreground)
        for axis_name in ("left", "bottom"):
            axis = self.getAxis(axis_name)
            axis.setPen(pen)
            axis.setTextPen(pen)
        if self._data.label:
            self.setTitle(self._data.label, color=palette.foreground)

    @property
    def data(self) -> TraceData:
        return self._data


class TraceContainer(pg.GraphicsLayoutWidget):  # type: ignore[misc]
    """Stacks N TraceWidgets as rows with a shared (linked) X-axis (ADR-024)."""

    def __init__(self, traces: Sequence[TraceData], *, palette: PlotPalette | None = None) -> None:
        super().__init__()
        self._palette = palette or plot_palette(DEFAULT_THEME)
        self.setBackground(self._palette.background)
        self._traces: list[TraceWidget] = []
        last_row = len(traces) - 1
        for row, data in enumerate(traces):
            widget = TraceWidget(data, palette=self._palette)
            self.addItem(widget, row=row, col=0)
            if self._traces:
                widget.setXLink(self._traces[0])
            if row != last_row:  # only the bottom tile shows the shared time axis
                widget.getAxis("bottom").setStyle(showValues=False)
                widget.setLabel("bottom", "")
            self._traces.append(widget)

    def restyle(self, palette: PlotPalette) -> None:
        """Apply a new theme palette to the background + every trace."""
        self._palette = palette
        self.setBackground(palette.background)
        for widget in self._traces:
            widget.apply_palette(palette)

    def count(self) -> int:
        """Number of stacked traces."""
        return len(self._traces)

    @property
    def palette(self) -> PlotPalette:
        return self._palette

    @property
    def traces(self) -> list[TraceWidget]:
        return list(self._traces)
