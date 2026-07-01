"""Tests for the TraceView composite (traces + time-scale slider)."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.widgets import TraceContainer, TraceData, TraceView


def test_trace_view_composes_and_restyles(qtbot: QtBot) -> None:
    view = TraceView(
        [TraceData(np.zeros(100, dtype=np.float64), 1000.0, "a")], palette=plot_palette("dark")
    )
    qtbot.addWidget(view)
    assert isinstance(view.container, TraceContainer)

    view.restyle(plot_palette("light"))
    assert view.container.palette == plot_palette("light")
