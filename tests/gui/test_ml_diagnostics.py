"""pytest-qt tests for the Flow B ML-diagnostics view scaffold (gui/views/ml_diagnostics, B8d)."""

from __future__ import annotations

import numpy as np
from myocard_egm_data.banks import ClassifierBank
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.gui.views import MlDiagnosticsView
from myocard_egm_studio.view_model import build_view_model, combine_view_models


def test_has_the_flow_b_subtabs(qtbot: QtBot) -> None:
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    assert [view._tabs.tabText(i) for i in range(view._tabs.count())] == [
        "Output",
        "Metrics",
        "Training",
        "Explore",
    ]


def test_landing_prompt_before_any_bank(qtbot: QtBot) -> None:
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    assert "Open a bank with model predictions" in view._header.text()


def test_set_evaluated_populates_the_list_and_header(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank
) -> None:
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    frame = build_view_model(tiny_predictions_bank, source="v1.5")
    view.set_evaluated(frame, "full")
    assert view.result_list._table.rowCount() == tiny_predictions_bank.n_traces
    assert "v1.5" in view._header.text()
    assert "full diagnostics" in view._header.text()
    assert view._tabs.currentIndex() == 0  # lands on the Output overlay (the headline)


def test_set_evaluated_populates_the_output_overlay(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank
) -> None:
    """A single evaluated bank draws one output-distribution curve for its source."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_evaluated(build_view_model(tiny_predictions_bank, source="v1.5"), "full")
    assert len(view._output_view.plot.getPlotItem().listDataItems()) == 1


def test_multi_source_overlay_and_header(
    qtbot: QtBot,
    tiny_predictions_bank: ClassifierBank,
    tiny_unlabeled_predictions_bank: ClassifierBank,
) -> None:
    """Two evaluated banks overlay two curves; the header reports the source count."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    frame = combine_view_models(
        [
            build_view_model(tiny_predictions_bank, source="v1"),
            build_view_model(tiny_unlabeled_predictions_bank, source="v1.5"),
        ]
    )
    view.set_evaluated(frame, "qualitative")
    assert "2 sources" in view._header.text()
    assert len(view._output_view.plot.getPlotItem().listDataItems()) == 2


def test_full_mode_populates_the_metric_suite(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank
) -> None:
    """A labelled eval bank draws the Metrics tab (charts + one confusion per source)."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_evaluated(build_view_model(tiny_predictions_bank, source="v1"), "full")
    assert view._metrics_view._stack.currentIndex() == 1  # charts, not the note
    assert len(view._metrics_view.confusion_plots) == 1


def test_qualitative_mode_shows_the_metrics_note(
    qtbot: QtBot, tiny_unlabeled_predictions_bank: ClassifierBank
) -> None:
    """An unlabelled eval set can't be scored — the Metrics tab shows a message."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_evaluated(
        build_view_model(tiny_unlabeled_predictions_bank, source="iafdb"), "qualitative"
    )
    assert view._metrics_view._stack.currentIndex() == 0  # the note, not charts


def test_set_runs_lands_on_the_training_tab(qtbot: QtBot) -> None:
    """Feeding training runs populates + reveals the Training tab (independent of banks)."""
    epochs = np.arange(1, 5)
    curve = TrainingCurve(
        epochs=epochs,
        loss={"val": np.asarray(1.0 / epochs, dtype=np.float64)},
        metric={"val": np.asarray(0.6 + 0.05 * epochs, dtype=np.float64)},
        metric_name="AUROC",
    )
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_runs([("v1.5", curve)])
    assert view._tabs.currentIndex() == 2  # Training tab
    assert view._training_view.overlay is not None


def test_run_remove_request_passes_through_to_the_shell(qtbot: QtBot) -> None:
    """The Training tab's remove ✕ re-emits at the view level for the shell to handle."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    received: list[str] = []
    view.runRemoveRequested.connect(received.append)
    view._training_view.removeRequested.emit("v1.5")
    assert received == ["v1.5"]


def test_clear_returns_to_the_landing_state(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank
) -> None:
    """A subsequent raw-bank load clears Flow B back to the landing prompt + empty list."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_evaluated(build_view_model(tiny_predictions_bank, source="v1.5"), "full")
    view.clear()
    assert view.result_list._table.rowCount() == 0
    assert "Open a bank with model predictions" in view._header.text()
    assert view._tabs.currentIndex() == 0
