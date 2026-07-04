"""Tests for the pyqtgraph training-curves overlay (charts/pyqtgraph/training, B8f)."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.pyqtgraph import training_curves_overlay


def _curve(shift: float = 0.0) -> TrainingCurve:
    epochs = np.arange(1, 6)
    train = np.asarray(1.0 / epochs + shift, dtype=np.float64)
    val = np.asarray(1.0 / epochs + 0.1 + shift, dtype=np.float64)
    metric = np.asarray(0.6 + 0.05 * epochs, dtype=np.float64)
    return TrainingCurve(
        epochs=epochs,
        loss={"train": train, "val": val},
        metric={"val": metric},
        metric_name="AUROC",
        best_epoch=4,
    )


def _panels(widget: pg.GraphicsLayoutWidget) -> list[pg.PlotItem]:
    return [item for item in widget.ci.items if isinstance(item, pg.PlotItem)]


def test_single_run_draws_train_val_loss_and_the_metric(qtbot: QtBot) -> None:
    widget = training_curves_overlay([("v1.5", _curve())])
    qtbot.addWidget(widget)
    loss, metric = _panels(widget)
    assert len(loss.listDataItems()) == 2  # train + val (single run shows both)
    assert len(metric.listDataItems()) == 1
    # train vs val are distinguished by colour, not just dash style
    colours = {pg.mkPen(item.opts["pen"]).color().name() for item in loss.listDataItems()}
    assert len(colours) == 2


def test_multi_run_overlays_val_only_per_run(qtbot: QtBot) -> None:
    widget = training_curves_overlay([("v1", _curve()), ("v1.5", _curve(0.05))])
    qtbot.addWidget(widget)
    loss, metric = _panels(widget)
    assert len(loss.listDataItems()) == 2  # one val-loss line per run, no train
    assert len(metric.listDataItems()) == 2


def test_empty_runs_draw_bare_panels(qtbot: QtBot) -> None:
    widget = training_curves_overlay([])
    qtbot.addWidget(widget)
    panels = _panels(widget)
    assert len(panels) == 2
    assert all(not panel.listDataItems() for panel in panels)
