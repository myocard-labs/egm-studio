"""Tests for the pyqtgraph output-distribution overlay (charts/pyqtgraph, B8e).

Like the feature-distribution twin: reuses ``analysis/distributions``, so these check
the panel assembles + one curve per non-empty source + the 0.5 guide; the numeric
histogram tests already live with ``analysis``.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.pyqtgraph import output_distribution_overlay


def _groups() -> list[PredictionGroup]:
    rng = np.random.default_rng(0)
    return [
        PredictionGroup(name="v1", probs=rng.uniform(0.0, 1.0, 200)),
        PredictionGroup(name="v1.5", probs=rng.uniform(0.0, 1.0, 150)),
    ]


def test_one_curve_per_source(qtbot: QtBot) -> None:
    widget = output_distribution_overlay(_groups())
    qtbot.addWidget(widget)
    assert len(widget.getPlotItem().listDataItems()) == 2


def test_empty_groups_draw_bare_axes(qtbot: QtBot) -> None:
    widget = output_distribution_overlay([])
    qtbot.addWidget(widget)
    assert widget.getPlotItem().listDataItems() == []


def test_group_with_no_finite_prob_is_skipped(qtbot: QtBot) -> None:
    widget = output_distribution_overlay(
        [
            PredictionGroup(name="ok", probs=np.array([0.1, 0.9, 0.5])),
            PredictionGroup(name="all-nan", probs=np.array([np.nan, np.nan])),
        ]
    )
    qtbot.addWidget(widget)
    assert len(widget.getPlotItem().listDataItems()) == 1


def test_threshold_guide_at_half(qtbot: QtBot) -> None:
    """A single dashed guide sits at the 0.5 decision boundary."""
    widget = output_distribution_overlay(_groups())
    qtbot.addWidget(widget)
    lines = [it for it in widget.getPlotItem().items if isinstance(it, pg.InfiniteLine)]
    assert len(lines) == 1
    assert lines[0].value() == 0.5
