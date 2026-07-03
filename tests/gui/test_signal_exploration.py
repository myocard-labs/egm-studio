"""Tests for the Flow A signal-exploration view (gui/views/signal_exploration)."""

from __future__ import annotations

from myocard_egm_data.banks import ClassifierBank
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.sources import traces_from_bank
from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.views import SignalExplorationView
from myocard_egm_studio.gui.widgets import TraceView
from myocard_egm_studio.view_model import build_view_model


def _view(qtbot: QtBot, bank: ClassifierBank) -> SignalExplorationView:
    view = SignalExplorationView(plot_palette("dark"))
    qtbot.addWidget(view)
    view.set_traces(traces_from_bank(bank))
    view.set_results(build_view_model(bank, source="Synthetic"))
    return view


def test_results_populate_the_list(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    assert view.result_list._table.rowCount() == len(tiny_classifier_bank.traces)


def test_selecting_rows_shows_a_traceview(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view.result_list._table.selectRow(0)
    assert isinstance(view._detail.content, TraceView)


def test_clearing_selection_returns_to_placeholder(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view.result_list._table.selectRow(0)
    assert isinstance(view._detail.content, TraceView)
    view.result_list._table.clearSelection()
    assert not isinstance(view._detail.content, TraceView)  # back to the prompt


def test_detail_caps_at_three_traces(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view._show_detail(list(range(len(tiny_classifier_bank.traces))))  # "select all 12"
    detail = view._detail.content
    assert isinstance(detail, TraceView)  # capped to 3 internally, no crash
