"""pytest-qt tests for the Flow B output-distribution view widget (B8e)."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.pyqtgraph.style import PgChartStyle
from myocard_egm_studio.gui.widgets import OutputDistributionView


def _groups() -> list[PredictionGroup]:
    rng = np.random.default_rng(1)
    return [
        PredictionGroup(name="v1", probs=rng.uniform(size=120)),
        PredictionGroup(name="v1.5", probs=rng.uniform(size=90)),
    ]


def test_set_groups_overlays_one_curve_each(qtbot: QtBot) -> None:
    view = OutputDistributionView()
    qtbot.addWidget(view)
    view.set_groups(_groups())
    assert len(view.plot.getPlotItem().listDataItems()) == 2


def test_clear_removes_curves(qtbot: QtBot) -> None:
    view = OutputDistributionView()
    qtbot.addWidget(view)
    view.set_groups(_groups())
    view.clear()
    assert view.plot.getPlotItem().listDataItems() == []


def test_set_style_rebuilds_the_panel(qtbot: QtBot) -> None:
    """A theme change recolours without dropping the curves."""
    view = OutputDistributionView()
    qtbot.addWidget(view)
    view.set_groups(_groups())
    view.set_style(PgChartStyle(background="#101010", foreground="#eeeeee"))
    assert len(view.plot.getPlotItem().listDataItems()) == 2
