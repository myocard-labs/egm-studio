"""pytest-qt tests for the Flow B ML-diagnostics view scaffold (gui/views/ml_diagnostics, B8d)."""

from __future__ import annotations

from myocard_egm_data.banks import ClassifierBank
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.views import MlDiagnosticsView
from myocard_egm_studio.view_model import build_view_model


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
    assert view._tabs.currentIndex() == view._TAB_EXPLORE  # lands on the populated tab


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
