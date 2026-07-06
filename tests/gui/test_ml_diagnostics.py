"""pytest-qt tests for the Flow B ML-diagnostics view scaffold (gui/views/ml_diagnostics, B8d)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from myocard_egm_data.banks import ClassifierBank
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.gui.views import MlDiagnosticsView
from myocard_egm_studio.gui.widgets import TraceData
from myocard_egm_studio.view_model import (
    FEATURE_COLUMNS,
    apply_filter,
    build_view_model,
    combine_view_models,
)
from myocard_egm_studio.view_model.filtering import Condition, FilterSpec


def _traces(n: int) -> list[TraceData]:
    return [TraceData(signal=np.zeros(8), fs_hz=1000.0, label=f"t{i}") for i in range(n)]


def _eval_frame() -> pd.DataFrame:
    """4 traces spanning the buckets: row 0 = FP, 1 = TP, 2 = TN, 3 = FN."""
    data: dict[str, object] = {
        "row_id": range(4),
        "trace_idx": range(4),
        "source": "v1",
        "label": [0, 1, 0, 1],
        "label_name": ["healthy", "fibrotic", "healthy", "fibrotic"],
        "predicted_prob": [0.9, 0.9, 0.1, 0.1],
        "predicted_class": [1, 1, 0, 0],
        "correctness_bucket": ["FP", "TP", "TN", "FN"],
        "per_trace_loss": [0.5, 0.1, 0.1, 0.5],
        "calibration_residual": [0.9, -0.1, 0.1, -0.9],
    }
    for feature in FEATURE_COLUMNS:
        data[feature] = np.linspace(1.0, 2.0, 4)
    return pd.DataFrame(data)


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
    assert view.result_list.row_count() == tiny_predictions_bank.n_traces
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


def test_explore_tab_offers_the_two_ml_finders(qtbot: QtBot) -> None:
    """Flow B's Explore detail wires the misclassification + outlier finds (B8g)."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    assert [button.text() for button in view._detail._buttons] == [
        "Find nearest correct",
        "Find in-class peers",
    ]


def test_set_explore_results_narrows_the_result_list(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank
) -> None:
    """The shared shell filter narrows the Explore list via set_explore_results (B8g-r1)."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    frame = build_view_model(tiny_predictions_bank, source="v1")
    view.set_evaluated(frame, "full")
    total = view.result_list.row_count()
    spec = FilterSpec((Condition("correctness_bucket", "==", "TP"),))
    view.set_explore_results(frame[apply_filter(frame, spec)], spec)
    assert 0 < view.result_list.row_count() < total  # dropped the non-TP traces


def test_nearest_correct_button_only_shown_for_a_misclassification(qtbot: QtBot) -> None:
    """'Find nearest correct' hides on a correct trace, appears on an FP / FN (B8g-r2)."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_evaluated(_eval_frame(), "full", traces=_traces(4))
    nearest = view._detail._buttons[0]  # "Find nearest correct"
    view._detail.on_selection([2])  # a TN (correctly classified)
    assert nearest.isHidden()
    view._detail.on_selection([0])  # the FP
    assert not nearest.isHidden()


def test_nearest_correct_searches_past_the_correctness_filter(qtbot: QtBot) -> None:
    """Filtering the list to FP still lets the find reach a correct counterpart (B8g-r3)."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    full = _eval_frame()
    view.set_evaluated(full, "full", traces=_traces(4))
    spec = FilterSpec((Condition("correctness_bucket", "==", "FP"),))
    view.set_explore_results(full[apply_filter(full, spec)], spec)
    assert view.result_list.row_count() == 1  # the list shows only the FP
    view._detail.on_selection([0])  # select it
    view._detail._buttons[0].click()  # find nearest correct
    assert view._detail._detail_table.columnCount() == 1 + 2  # FP + its nearest-correct match


def test_clear_returns_to_the_landing_state(
    qtbot: QtBot, tiny_predictions_bank: ClassifierBank
) -> None:
    """A subsequent raw-bank load clears Flow B back to the landing prompt + empty list."""
    view = MlDiagnosticsView()
    qtbot.addWidget(view)
    view.set_evaluated(build_view_model(tiny_predictions_bank, source="v1.5"), "full")
    view.clear()
    assert view.result_list.row_count() == 0
    assert "Open a bank with model predictions" in view._header.text()
    assert view._tabs.currentIndex() == 0
