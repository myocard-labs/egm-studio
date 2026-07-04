"""Tests for the Flow A signal-exploration view (gui/views/signal_exploration)."""

from __future__ import annotations

from myocard_egm_data.banks import ClassifierBank
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.sources import traces_from_bank
from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.views import SignalExplorationView
from myocard_egm_studio.gui.widgets import TraceView
from myocard_egm_studio.view_model import build_view_model, combine_view_models
from myocard_egm_studio.view_model.builder import FEATURE_COLUMNS


def _view(qtbot: QtBot, bank: ClassifierBank) -> SignalExplorationView:
    view = SignalExplorationView(plot_palette("dark"))
    qtbot.addWidget(view)
    # the GUI keys detail selection on row_id, so feed a combined frame (B7.8)
    frame = combine_view_models([build_view_model(bank, source="Synthetic")])
    view.set_traces(traces_from_bank(bank))
    view.set_results(frame)
    return view


def _top(view: SignalExplorationView, index: int) -> QtWidgets.QTreeWidgetItem:
    item = view._detail_table.topLevelItem(index)
    assert item is not None
    return item


def test_results_populate_the_list(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    assert view.result_list._table.rowCount() == len(tiny_classifier_bank.traces)


def test_selecting_rows_shows_waveforms_and_detail(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view.result_list._table.selectRow(0)
    assert view._detail_stack.currentIndex() == 1  # the waveform + detail page
    assert isinstance(view._waveforms.content, TraceView)
    assert [_top(view, 0).text(0), _top(view, 1).text(0)] == ["Features", "Metadata"]
    assert _top(view, 0).childCount() == len(FEATURE_COLUMNS)  # the 11 egm-features
    assert _top(view, 1).childCount() > 0  # metadata rows


def test_clearing_selection_returns_to_placeholder(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view.result_list._table.selectRow(0)
    assert view._detail_stack.currentIndex() == 1
    view.result_list._table.clearSelection()
    assert view._detail_stack.currentIndex() == 0  # back to the prompt


def test_detail_caps_at_three_traces(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view._show_detail(list(range(len(tiny_classifier_bank.traces))))  # "select all 12"
    assert isinstance(view._waveforms.content, TraceView)  # capped to 3 internally
    assert view._detail_table.columnCount() == 1 + 3  # attribute column + 3 trace columns


def test_results_populate_the_grid_and_stats(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    """set_results fills the 11-panel grid + stats too, so filtering drives them."""
    view = _view(qtbot, tiny_classifier_bank)  # _view already calls set_results
    assert len(view._feature_grid.panels) == len(FEATURE_COLUMNS)
    assert "traces" in view._summary_panel._count.text()
    # a narrower frame re-feeds the grid + stats (the point-3 filter-drives-grid path)
    subset = combine_view_models([build_view_model(tiny_classifier_bank, source="Synthetic")])
    view.set_results(subset.head(4))
    assert len(view._feature_grid.panels) == len(FEATURE_COLUMNS)
    assert "4 traces" in view._summary_panel._count.text()


def test_tab_switch_helpers(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    view.show_explore()
    assert view._tabs.currentIndex() == 1
    view.show_summary()
    assert view._tabs.currentIndex() == 0


def test_summary_overlays_per_source_with_a_stats_line_each(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    """Two banks overlay one curve per source in the 11 panels + a stats line each."""
    view = SignalExplorationView(plot_palette("dark"))
    qtbot.addWidget(view)
    combined = combine_view_models(
        [
            build_view_model(tiny_classifier_bank, source="A"),
            build_view_model(tiny_unlabeled_bank, source="B"),
        ]
    )
    view.set_results(combined)
    assert len(view._feature_grid.panels) == len(FEATURE_COLUMNS)  # overlaid, not doubled
    assert len(view._feature_grid._groups) == 2  # two source curves
    assert view._summary_panel._banks.count() == 2  # one stats line per bank


def test_has_three_subtabs_including_scatter(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, tiny_classifier_bank)
    assert [view._tabs.tabText(i) for i in range(view._tabs.count())] == [
        "Summary",
        "Explore",
        "Scatter",
    ]


def test_results_feed_the_scatter(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    """set_results feeds the scatter the same filtered set — one cloud per source."""
    view = SignalExplorationView(plot_palette("dark"))
    qtbot.addWidget(view)
    combined = combine_view_models(
        [
            build_view_model(tiny_classifier_bank, source="A"),
            build_view_model(tiny_unlabeled_bank, source="B"),
        ]
    )
    view.set_results(combined)
    assert len(view._scatter.items) == 2  # one scatter cloud per source


def test_scatter_click_selects_row_and_shows_explore_detail(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    """A scatter point click selects the row, opens the detail, and jumps to Explore."""
    view = _view(qtbot, tiny_classifier_bank)
    view._scatter.pointClicked.emit(0)  # click the trace at row_id 0
    assert view.result_list.selected_row_ids() == [0]  # list selection synced
    assert view._detail_stack.currentIndex() == 1  # detail populated
    assert view._tabs.currentIndex() == 1  # revealed the Explore tab


def _two_bank_view(qtbot: QtBot, a: ClassifierBank, b: ClassifierBank) -> SignalExplorationView:
    view = SignalExplorationView(plot_palette("dark"))
    qtbot.addWidget(view)
    combined = combine_view_models(
        [build_view_model(a, source="A"), build_view_model(b, source="B")]
    )
    view.set_traces([*traces_from_bank(a), *traces_from_bank(b)])  # global row_id order
    view.set_results(combined)
    return view


def test_find_similar_enabled_only_on_single_selection_with_another_bank(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    view = _two_bank_view(qtbot, tiny_classifier_bank, tiny_unlabeled_bank)
    assert not view._find_button.isEnabled()  # nothing selected
    view.result_list._table.selectRow(0)
    assert view._find_button.isEnabled()  # one source trace + another bank to search


def test_find_similar_disabled_for_a_single_bank(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, tiny_classifier_bank)  # one bank
    view.result_list._table.selectRow(0)
    assert not view._find_button.isEnabled()  # no other bank to search


def test_find_similar_button_shows_source_plus_match(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    view = _two_bank_view(qtbot, tiny_classifier_bank, tiny_unlabeled_bank)
    view.result_list._table.selectRow(0)  # a source trace in bank A
    view._find_button.click()
    assert view._detail_stack.currentIndex() == 1
    assert view._detail_table.columnCount() == 1 + 2  # attribute + source + its nearest in B


def test_right_click_find_similar_shows_compare(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    view = _two_bank_view(qtbot, tiny_classifier_bank, tiny_unlabeled_bank)
    view.result_list.findSimilarRequested.emit(0)  # right-click row_id 0
    assert view._detail_table.columnCount() == 1 + 2  # source + match


def test_compare_table_annotates_feature_deltas(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    view = _two_bank_view(qtbot, tiny_classifier_bank, tiny_unlabeled_bank)
    view._show_detail([0, 1])  # two traces -> the second column carries deltas
    features = view._detail_table.topLevelItem(0)  # the "Features" section
    assert features is not None
    first_feature = features.child(0)
    assert "(" in first_feature.text(2)  # the match column shows a "(Δ)" annotation
