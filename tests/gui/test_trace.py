"""pytest-qt tests for the ADR-024 trace display (TraceWidget + TraceContainer)."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.theme.palette import DARK, LIGHT
from myocard_egm_studio.gui.widgets import TraceContainer, TraceData, TraceWidget


def _trace(label: str, freq_hz: float = 5.0, n: int = 500, fs: float = 1000.0) -> TraceData:
    t = np.arange(n, dtype=np.float64) / fs
    return TraceData(signal=np.sin(2.0 * np.pi * freq_hz * t), fs_hz=fs, label=label)


def test_trace_widget_renders_one_curve(qapp: QtWidgets.QApplication) -> None:
    widget = TraceWidget(_trace("P01"))
    assert len(widget.listDataItems()) == 1
    assert widget.data.label == "P01"


def test_container_stacks_n_traces(qtbot: QtBot) -> None:
    for n in (1, 2, 4):
        container = TraceContainer([_trace(f"t{i}", 4.0 + i) for i in range(n)])
        qtbot.addWidget(container)
        assert container.count() == n
        assert all(isinstance(w, TraceWidget) for w in container.traces)


def test_container_links_x_axis(qtbot: QtBot) -> None:
    container = TraceContainer([_trace("a"), _trace("b")])
    qtbot.addWidget(container)
    first, second = container.traces

    # structural: the second row's X-axis is linked to the first
    assert second.getViewBox().linkedView(pg.ViewBox.XAxis) is first.getViewBox()

    # behavioural: a range change on the first propagates to the second
    first.setXRange(100.0, 200.0, padding=0)
    qtbot.wait(10)
    x0, x1 = second.getViewBox().viewRange()[0]
    assert abs(x0 - 100.0) < 5.0
    assert abs(x1 - 200.0) < 5.0


def test_plot_palette_maps_from_theme() -> None:
    pp = plot_palette("dark")
    assert pp.background == DARK.surface
    assert pp.trace == DARK.accent


def test_container_restyle_updates_palette(qtbot: QtBot) -> None:
    container = TraceContainer([_trace("a")], palette=plot_palette("dark"))
    qtbot.addWidget(container)
    container.restyle(plot_palette("light"))
    assert container.palette.background == LIGHT.surface
