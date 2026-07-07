"""Tests for the pyqtgraph metric charts (charts/pyqtgraph/metrics, B8f).

Reuse ``analysis/metrics`` (same as the paper recipes), so these check the panels
assemble — a curve per labelled group + the reference line, a confusion heatmap +
cell text — not the numbers, which are tested with ``analysis``.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pytest
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import ConfusionCounts, PredictionGroup
from myocard_egm_studio.charts.pyqtgraph import draw_calibration, draw_confusion, draw_roc


def _labelled_groups() -> list[PredictionGroup]:
    rng = np.random.default_rng(0)
    groups = []
    for name, sep in (("v1", 0.5), ("v1.5", 1.4)):
        y = rng.integers(0, 2, 200)
        probs = np.clip(0.5 + sep * (y - 0.5) + rng.normal(0, 0.15, 200), 0.001, 0.999)
        groups.append(PredictionGroup(name=name, probs=probs, labels=y.astype(np.int64)))
    return groups


def _plot(qtbot: QtBot) -> pg.PlotWidget:
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    return widget


def test_roc_draws_a_curve_per_group_plus_chance(qtbot: QtBot) -> None:
    widget = _plot(qtbot)
    draw_roc(widget.getPlotItem(), _labelled_groups())
    assert len(widget.getPlotItem().listDataItems()) == 3  # chance diagonal + 2 ROC curves


def test_roc_skips_an_unlabelled_group(qtbot: QtBot) -> None:
    widget = _plot(qtbot)
    draw_roc(widget.getPlotItem(), [PredictionGroup(name="iafdb", probs=np.array([0.2, 0.8]))])
    assert len(widget.getPlotItem().listDataItems()) == 1  # only the chance diagonal


def test_calibration_draws_a_curve_per_group_plus_diagonal(qtbot: QtBot) -> None:
    widget = _plot(qtbot)
    draw_calibration(widget.getPlotItem(), _labelled_groups())
    assert len(widget.getPlotItem().listDataItems()) == 3


_CONFUSION = ConfusionCounts(
    name="v1", matrix=np.array([[8, 2], [1, 9]], dtype=np.int64), labels=["healthy", "fibrotic"]
)


@pytest.mark.parametrize(
    ("normalize", "expected"),
    [
        ("row", ["10%", "20%", "80%", "90%"]),  # divide by each true-class row total
        ("col", ["11%", "18%", "82%", "89%"]),  # divide by each predicted-class col total
        ("overall", ["10%", "40%", "45%", "5%"]),  # divide by the grand total
        ("count", ["1", "2", "8", "9"]),  # raw counts
    ],
)
def test_confusion_cell_labels_per_normalize_mode(
    qtbot: QtBot, normalize: str, expected: list[str]
) -> None:
    widget = _plot(qtbot)
    draw_confusion(widget.getPlotItem(), _CONFUSION, normalize=normalize)
    items = widget.getPlotItem().items
    assert any(isinstance(it, pg.ImageItem) for it in items)
    texts = sorted(it.toPlainText() for it in items if isinstance(it, pg.TextItem))
    assert texts == sorted(expected)


def test_confusion_rejects_an_unknown_normalize_mode(qtbot: QtBot) -> None:
    with pytest.raises(ValueError, match="normalize must be one of"):
        draw_confusion(_plot(qtbot).getPlotItem(), _CONFUSION, normalize="bogus")
