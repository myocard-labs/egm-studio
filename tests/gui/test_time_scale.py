"""Tests for the time-scale slider bound to a TraceContainer's X-axis."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import TimeScaleWidget, TraceContainer, TraceData


def _container(qtbot: QtBot) -> TraceContainer:
    container = TraceContainer([TraceData(np.zeros(1000, dtype=np.float64), 1000.0, "a")])
    qtbot.addWidget(container)
    return container


def _visible_width(container: TraceContainer) -> float:
    viewbox = container.shared_viewbox()
    assert viewbox is not None
    lo, hi = viewbox.viewRange()[0]
    return float(hi - lo)


def test_slider_controls_visible_width(qtbot: QtBot) -> None:
    container = _container(qtbot)
    scale = TimeScaleWidget()
    scale.bind(container)
    qtbot.addWidget(scale)

    scale._slider.setValue(80)
    wide = _visible_width(container)
    scale._slider.setValue(20)
    narrow = _visible_width(container)
    assert narrow < wide


def test_range_change_updates_slider(qtbot: QtBot) -> None:
    container = _container(qtbot)
    scale = TimeScaleWidget()
    scale.bind(container)
    qtbot.addWidget(scale)

    full = scale._slider.value()
    container.set_x_range(0.0, 100.0)  # zoom to 100 ms of the ~1000 ms trace
    assert scale._slider.value() < full
