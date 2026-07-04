"""Flow A signal-exploration view — Summary landing + load→filter→list→detail (Block 7).

The main-area content for Signal-exploration mode, split into two sub-tabs (B7.7):
a **Summary** landing (bank stats + the ADR-018 responsive feature-distribution
grid) and an **Explore** tab (a sortable ``ResultList`` over the shared per-trace
:class:`~gui.widgets.explore_detail.ExploreDetail`). The shell owns the bank + the
sidebar ``FilterPanel``; it feeds the summary the full frame and the list the filtered
frame. Selecting rows pairs their waveforms (up to the 3-pane cap) with a feature +
metadata table; the detail's one "find" strategy is the nearest trace in each other
bank (B7.10), the same shared pane Flow B reuses with ML-outcome finders (B8g).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle
from myocard_egm_studio.gui.preferences import (
    load_plot_kind,
    load_scatter_axes,
    load_ui_scale,
    save_plot_kind,
    save_scatter_axes,
    save_ui_scale,
)
from myocard_egm_studio.gui.widgets import (
    ExploreDetail,
    FeatureDistributionGrid,
    FeatureScatterView,
    Finder,
    ResultList,
    TraceData,
)
from myocard_egm_studio.loaders import feature_groups_by_source, scatter_series_by_source
from myocard_egm_studio.view_model import (
    FEATURE_COLUMNS,
    BankSummary,
    bank_summary,
    similar_in_other_sources,
)

_TAB_SUMMARY, _TAB_EXPLORE, _TAB_SCATTER = 0, 1, 2  # sub-tab order; Summary is the landing
_DEFAULT_AXES = (FEATURE_COLUMNS[0], FEATURE_COLUMNS[1])  # scatter's first-load (x, y)

#: Flow A's one find strategy: the nearest trace in each *other* bank (needs 2+ sources).
_OTHER_BANK_FINDER = Finder(
    label="Find similar in other bank",
    find=similar_in_other_sources,
    can_run=lambda frame, _row_id: "source" in frame.columns and frame["source"].nunique() > 1,
)


def _provenance_text(summary: BankSummary) -> str:
    """Compact provenance: bank type(s) · amp · splits (the id lives in the roster)."""
    parts: list[str] = []
    if summary.bank_types:
        parts.append(" / ".join(summary.bank_types))
    if summary.amp_type:
        parts.append(f"amp {summary.amp_type}")
    if summary.splits:
        parts.append("splits: " + ", ".join(summary.splits))
    return "   ·   ".join(parts)


def _bank_line(name: str, summary: BankSummary) -> str:
    """One per-bank stats line: name — count · class balance · provenance."""
    parts = [f"{name} — {summary.n_traces:,} traces"]
    balance = "  ·  ".join(f"{label} {count:,}" for label, count in summary.class_balance)
    if balance:
        parts.append(balance)
    provenance = _provenance_text(summary)
    if provenance:
        parts.append(provenance)
    return "   ·   ".join(parts)


def _clear_layout(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _summaries_by_source(frame: pd.DataFrame) -> list[tuple[str, BankSummary]]:
    """One (source name, BankSummary) per distinct source, in load order."""
    if not len(frame.index):
        return []
    if "source" not in frame.columns:
        return [("bank", bank_summary(frame))]
    return [
        (str(source), bank_summary(frame[frame["source"] == source]))
        for source in frame["source"].dropna().unique()
    ]


class _SummaryPanel(QtWidgets.QFrame):
    """The bank-summary header: total trace count over one stats line per bank."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("summaryPanel")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 8)
        outer.setSpacing(2)
        self._count = QtWidgets.QLabel()
        self._count.setObjectName("summaryCount")
        outer.addWidget(self._count)
        self._banks = QtWidgets.QVBoxLayout()
        self._banks.setContentsMargins(0, 0, 0, 0)
        self._banks.setSpacing(1)
        outer.addLayout(self._banks)

    def set_summaries(self, summaries: Sequence[tuple[str, BankSummary]]) -> None:
        """Show the total count then one stats line per loaded bank."""
        total = sum(summary.n_traces for _, summary in summaries)
        suffix = f"   ·   {len(summaries)} banks" if len(summaries) > 1 else ""
        self._count.setText(f"{total:,} traces{suffix}")
        _clear_layout(self._banks)
        for name, summary in summaries:
            line = QtWidgets.QLabel(_bank_line(name, summary))
            line.setObjectName("summaryLine")
            line.setWordWrap(True)
            self._banks.addWidget(line)


class SignalExplorationView(QtWidgets.QWidget):
    """Summary landing + a sortable result list over the shared per-trace detail (Flow A)."""

    def __init__(
        self,
        palette: Any,
        chart_style: PgChartStyle = DEFAULT_STYLE,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("signalExplorationView")
        self._palette = palette
        self._traces: list[TraceData] = []
        self._frame = pd.DataFrame()

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("flowATabs")
        self._tabs.addTab(self._build_summary_page(chart_style), "Summary")
        self._tabs.addTab(self._build_explore_page(), "Explore")
        self._tabs.addTab(self._build_scatter_page(chart_style), "Scatter")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

    def _build_summary_page(self, chart_style: PgChartStyle) -> QtWidgets.QWidget:
        """The Summary tab: the stats header over the ADR-018 distribution grid."""
        self._summary_panel = _SummaryPanel()
        self._feature_grid = FeatureDistributionGrid(chart_style)
        self._feature_grid.set_scale_factor(load_ui_scale(1.0))  # ADR-018 persisted scale
        self._feature_grid.scaleChanged.connect(save_ui_scale)
        self._feature_grid.set_kind(load_plot_kind("kde"))  # persisted KDE / histogram choice
        self._feature_grid.kindChanged.connect(save_plot_kind)
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._summary_panel)
        layout.addWidget(self._feature_grid, 1)
        return page

    def _build_explore_page(self) -> QtWidgets.QWidget:
        """The Explore tab: the sortable result list over the shared per-trace detail."""
        self._result_list = ResultList()
        self._detail = ExploreDetail(self._palette, [_OTHER_BANK_FINDER])
        self._result_list.selectionChanged.connect(self._detail.on_selection)
        self._result_list.findSimilarRequested.connect(
            lambda row_id: self._detail.run_finder(0, row_id)  # right-click -> the finder
        )
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setObjectName("exploreSplitter")
        splitter.addWidget(self._result_list)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        return page

    def _build_scatter_page(self, chart_style: PgChartStyle) -> QtWidgets.QWidget:
        """The Scatter tab: a 2-D feature scatter of the filtered result (click -> detail)."""
        self._scatter = FeatureScatterView(chart_style)
        self._scatter.set_axes(*load_scatter_axes(_DEFAULT_AXES))  # persisted (x, y) axes
        self._scatter.axesChanged.connect(save_scatter_axes)
        self._scatter.pointClicked.connect(self._on_scatter_pick)
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scatter)
        return page

    def set_traces(self, traces: Sequence[TraceData]) -> None:
        """Set the display traces of a newly opened bank (indexed by ``trace_idx``)."""
        self._traces = list(traces)
        self._detail.show_rows([])  # reset the detail to its prompt

    def set_results(
        self, frame: pd.DataFrame, *, progress: Callable[[int, int], None] | None = None
    ) -> None:
        """Set the current (filtered) frame everywhere — list, scatter, summary grid + stats.

        The one "here is the data to show" entry point: the full frame on open, the
        filtered frame on every Recalculate. The distribution grid + per-bank stats
        reflect the filter just like the list and scatter, so filtering shows how the
        distributions shift (e.g. narrowing a metadata range). No tab switch — the
        landing is an explicit :meth:`show_summary` / :meth:`show_explore`. ``progress``
        drives the table build on the big initial load.
        """
        self._frame = frame
        self._result_list.set_frame(frame, progress=progress)
        self._detail.set_context(frame, self._traces)  # the finds search the filtered frame
        self._scatter.set_series(scatter_series_by_source(frame))
        self._feature_grid.set_groups(feature_groups_by_source(frame))
        self._summary_panel.set_summaries(_summaries_by_source(frame))

    def show_summary(self) -> None:
        self._tabs.setCurrentIndex(_TAB_SUMMARY)

    def show_explore(self) -> None:
        self._tabs.setCurrentIndex(_TAB_EXPLORE)

    def bring_scatter_to_front(self, source: str) -> None:
        """Raise a source's points above the others in the scatter (roster button)."""
        self._scatter.bring_to_front(source)

    @property
    def result_list(self) -> ResultList:
        return self._result_list

    def restyle(self, palette: Any, chart_style: PgChartStyle) -> None:
        """Re-apply the theme to the open detail + the distribution grid + the scatter."""
        self._palette = palette
        self._detail.restyle(palette)
        self._feature_grid.set_style(chart_style)
        self._scatter.set_style(chart_style)

    def _on_scatter_pick(self, row_id: int) -> None:
        """A scatter point was clicked: select that trace + reveal the Explore detail.

        Routes through the result list's selection (not straight to the detail) so the
        list highlight, the detail pane, and the selection all stay in sync — the same
        ``selectionChanged`` -> detail path as clicking the row.
        """
        self._result_list.select_row_ids([row_id])
        self.show_explore()
