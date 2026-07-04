"""pytest-qt tests for the Flow B training view widget (gui/widgets/training_view, B8f)."""

from __future__ import annotations

import numpy as np
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.gui.widgets import TrainingView


def _curve() -> TrainingCurve:
    epochs = np.arange(1, 6)
    return TrainingCurve(
        epochs=epochs,
        loss={
            "train": np.asarray(1.0 / epochs, dtype=np.float64),
            "val": np.asarray(1.0 / epochs + 0.1, dtype=np.float64),
        },
        metric={"val": np.asarray(0.6 + 0.05 * epochs, dtype=np.float64)},
        metric_name="AUROC",
        best_epoch=4,
    )


def test_set_runs_shows_the_overlay(qtbot: QtBot) -> None:
    view = TrainingView()
    qtbot.addWidget(view)
    view.set_runs([("v1.5", _curve())])
    assert view._stack.currentIndex() == 1
    assert view.overlay is not None


def test_empty_runs_show_the_prompt(qtbot: QtBot) -> None:
    view = TrainingView()
    qtbot.addWidget(view)
    view.set_runs([("v1.5", _curve())])
    view.clear()
    assert view._stack.currentIndex() == 0


def test_roster_lists_a_row_per_run(qtbot: QtBot) -> None:
    view = TrainingView()
    qtbot.addWidget(view)
    view.set_runs([("v1", _curve()), ("v1.5", _curve())])
    assert len(view._roster.findChildren(QtWidgets.QWidget, "runRow")) == 2


def test_remove_request_passes_through_from_the_roster(qtbot: QtBot) -> None:
    view = TrainingView()
    qtbot.addWidget(view)
    view.set_runs([("v1.5", _curve())])
    received: list[str] = []
    view.removeRequested.connect(received.append)
    view._roster.removeRequested.emit("v1.5")
    assert received == ["v1.5"]
