"""pytest-qt tests for the Flow B metrics view widget (gui/widgets/metrics_view, B8f)."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import ConfusionCounts, PredictionGroup
from myocard_egm_studio.charts.pyqtgraph.style import PgChartStyle
from myocard_egm_studio.gui.widgets import MetricsView


def _groups() -> list[PredictionGroup]:
    rng = np.random.default_rng(2)
    groups = []
    for name in ("v1", "v1.5"):
        y = rng.integers(0, 2, 120)
        probs = np.clip(rng.random(120), 0.001, 0.999)
        groups.append(PredictionGroup(name=name, probs=probs, labels=y.astype(np.int64)))
    return groups


def _confusions() -> list[ConfusionCounts]:
    labels = ["healthy", "fibrotic"]
    return [
        ConfusionCounts("v1", np.array([[5, 1], [2, 6]], dtype=np.int64), labels),
        ConfusionCounts("v1.5", np.array([[7, 0], [1, 5]], dtype=np.int64), labels),
    ]


def test_set_metrics_shows_charts_with_one_confusion_per_source(qtbot: QtBot) -> None:
    view = MetricsView()
    qtbot.addWidget(view)
    view.set_metrics(_groups(), _confusions())
    assert view._stack.currentIndex() == 1  # the charts page, not the message
    assert len(view.confusion_plots) == 2


def test_show_message_switches_to_the_note(qtbot: QtBot) -> None:
    view = MetricsView()
    qtbot.addWidget(view)
    view.set_metrics(_groups(), _confusions())
    view.show_message("Metrics need truth labels.")
    assert view._stack.currentIndex() == 0


def test_set_style_rebuilds_while_charts_are_shown(qtbot: QtBot) -> None:
    view = MetricsView()
    qtbot.addWidget(view)
    view.set_metrics(_groups(), _confusions())
    view.set_style(PgChartStyle(background="#101010", foreground="#eeeeee"))
    assert len(view.confusion_plots) == 2


def test_set_norm_rebuilds_the_confusion_panels(qtbot: QtBot) -> None:
    view = MetricsView()
    qtbot.addWidget(view)
    view.set_metrics(_groups(), _confusions())
    view.set_norm("count")
    assert view._norm == "count"
    assert len(view.confusion_plots) == 2  # rebuilt, still one per source


def test_norm_combo_change_emits_the_mode(qtbot: QtBot) -> None:
    view = MetricsView()
    qtbot.addWidget(view)
    view.set_metrics(_groups(), _confusions())
    received: list[str] = []
    view.normChanged.connect(received.append)
    view._norm_combo.setCurrentIndex(3)  # combo order: row / col / overall / count
    assert received == ["count"]
    assert view._norm == "count"
