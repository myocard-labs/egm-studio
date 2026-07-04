"""Flow A signal-exploration view — Summary landing + load→filter→list→detail (Block 7).

The main-area content for Signal-exploration mode, split into two sub-tabs (B7.7):
a **Summary** landing (bank stats + the ADR-018 responsive feature-distribution
grid) and an **Explore** tab (a sortable ``ResultList`` over a per-trace detail
pane). The shell owns the bank + the sidebar ``FilterPanel``; it feeds the summary
the full frame and the list the filtered frame. Selecting rows pairs their
waveforms (up to the 3-pane cap) with a feature + metadata table of the selected
trace(s) — the seed of the B7.10 compare view.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle
from myocard_egm_studio.gui.preferences import load_ui_scale, save_ui_scale
from myocard_egm_studio.gui.widgets import (
    FeatureDistributionGrid,
    ResultList,
    TraceData,
    TraceView,
)
from myocard_egm_studio.loaders import feature_group_from_frame
from myocard_egm_studio.view_model import BankSummary, TraceDetail, bank_summary, trace_detail

_DETAIL_CAP = 3  # traces shown side-by-side in the detail (the 3-pane comparison cap)
_SELECT_PROMPT = "Select trace(s) in the list to view"
_TAB_SUMMARY, _TAB_EXPLORE = 0, 1  # sub-tab order; Summary is the post-load landing


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


def _provenance_text(summary: BankSummary) -> str:
    """Compact provenance line: bank type(s) · amp · splits · bank id(s)."""
    parts: list[str] = []
    if summary.bank_types:
        parts.append(" / ".join(summary.bank_types))
    if summary.amp_type:
        parts.append(f"amp {summary.amp_type}")
    if summary.splits:
        parts.append("splits: " + ", ".join(summary.splits))
    if summary.bank_ids:
        parts.append(" / ".join(summary.bank_ids))
    return "   ·   ".join(parts)


class _SummaryPanel(QtWidgets.QFrame):
    """The bank-summary header: trace count, class balance, and provenance."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("summaryPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(2)
        self._count = QtWidgets.QLabel()
        self._count.setObjectName("summaryCount")
        self._balance = QtWidgets.QLabel()
        self._balance.setObjectName("summaryLine")
        self._provenance = QtWidgets.QLabel()
        self._provenance.setObjectName("summaryLine")
        self._provenance.setWordWrap(True)
        for widget in (self._count, self._balance, self._provenance):
            layout.addWidget(widget)

    def set_summary(self, summary: BankSummary) -> None:
        self._count.setText(f"{summary.n_traces:,} traces")
        balance = "   ·   ".join(f"{name} {count:,}" for name, count in summary.class_balance)
        self._balance.setText(balance or "—")
        self._provenance.setText(_provenance_text(summary))


class _WaveformHost(QtWidgets.QWidget):
    """Left detail pane: swaps in a TraceView of the selected traces' waveforms."""

    def __init__(self) -> None:
        super().__init__()
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._content: QtWidgets.QWidget = _placeholder(_SELECT_PROMPT)
        self._layout.addWidget(self._content)

    def show_widget(self, widget: QtWidgets.QWidget) -> None:
        self._layout.removeWidget(self._content)
        self._content.deleteLater()
        self._content = widget
        self._layout.addWidget(widget)

    @property
    def content(self) -> QtWidgets.QWidget:
        return self._content


class _TraceDetailTable(QtWidgets.QTreeWidget):
    """Right detail pane: the selected trace(s)' Features + Metadata values."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("traceDetailTable")
        self.setColumnCount(1)
        self.setMinimumWidth(280)  # keep value columns visible beside the wider waveform pane

    def set_detail(self, detail: TraceDetail) -> None:
        self.clear()
        self.setColumnCount(1 + len(detail.headers))
        self.setHeaderLabels(["Attribute", *detail.headers])
        self._add_section("Features", detail)
        self._add_section("Metadata", detail)
        self.expandAll()
        for column in range(self.columnCount()):
            self.resizeColumnToContents(column)
        # cap the attribute column so the per-trace value columns stay visible
        self.setColumnWidth(0, min(self.columnWidth(0), 190))

    def _add_section(self, title: str, detail: TraceDetail) -> None:
        rows = detail.features if title == "Features" else detail.metadata
        section = QtWidgets.QTreeWidgetItem([title])
        self.addTopLevelItem(section)
        for row in rows:
            label = f"{row.label} ({row.unit})" if row.unit else row.label
            section.addChild(QtWidgets.QTreeWidgetItem([label, *row.values]))


class SignalExplorationView(QtWidgets.QWidget):
    """Summary landing + a sortable result list over a per-trace detail (Flow A)."""

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

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

    def _build_summary_page(self, chart_style: PgChartStyle) -> QtWidgets.QWidget:
        """The Summary tab: the stats header over the ADR-018 distribution grid."""
        self._summary_panel = _SummaryPanel()
        self._feature_grid = FeatureDistributionGrid(chart_style)
        self._feature_grid.set_scale_factor(load_ui_scale(1.0))  # ADR-018 persisted scale
        self._feature_grid.scaleChanged.connect(save_ui_scale)
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._summary_panel)
        layout.addWidget(self._feature_grid, 1)
        return page

    def _build_explore_page(self) -> QtWidgets.QWidget:
        """The Explore tab: the sortable result list over the per-trace detail."""
        self._result_list = ResultList()
        self._result_list.selectionChanged.connect(self._show_detail)

        self._waveforms = _WaveformHost()
        self._detail_table = _TraceDetailTable()
        detail = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        detail.addWidget(self._waveforms)
        detail.addWidget(self._detail_table)
        detail.setStretchFactor(0, 3)
        detail.setStretchFactor(1, 2)

        self._detail_stack = QtWidgets.QStackedWidget()
        self._detail_stack.addWidget(_placeholder(_SELECT_PROMPT))  # page 0 — nothing selected
        self._detail_stack.addWidget(detail)  # page 1 — waveforms + values

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setObjectName("exploreSplitter")
        splitter.addWidget(self._result_list)
        splitter.addWidget(self._detail_stack)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        return page

    def set_traces(self, traces: Sequence[TraceData]) -> None:
        """Set the display traces of a newly opened bank (indexed by ``trace_idx``)."""
        self._traces = list(traces)
        self._detail_stack.setCurrentIndex(0)

    def set_summary(self, frame: pd.DataFrame) -> None:
        """Populate the Summary landing from the full-bank frame and land on it.

        Called once per bank load with the unfiltered view-model (the summary +
        distribution grid describe the whole bank, unlike the filter-driven list).
        """
        self._summary_panel.set_summary(bank_summary(frame))
        if len(frame.index):
            self._feature_grid.set_group(feature_group_from_frame(frame))
        self._tabs.setCurrentIndex(_TAB_SUMMARY)

    def set_results(self, frame: pd.DataFrame) -> None:
        """Show the rows the filter kept (also called with the full frame on open)."""
        self._frame = frame
        self._result_list.set_frame(frame)

    def show_summary(self) -> None:
        self._tabs.setCurrentIndex(_TAB_SUMMARY)

    def show_explore(self) -> None:
        self._tabs.setCurrentIndex(_TAB_EXPLORE)

    @property
    def result_list(self) -> ResultList:
        return self._result_list

    def restyle(self, palette: Any, chart_style: PgChartStyle) -> None:
        """Re-apply the theme to the open detail + the distribution grid."""
        self._palette = palette
        content = self._waveforms.content
        if isinstance(content, TraceView):
            content.restyle(palette)
        self._feature_grid.set_style(chart_style)

    def _show_detail(self, row_ids: list[int]) -> None:
        # row_id is the global position in the combined traces list (B7.8).
        shown = [i for i in row_ids[:_DETAIL_CAP] if 0 <= i < len(self._traces)]
        if not shown:
            self._detail_stack.setCurrentIndex(0)
            return
        self._waveforms.show_widget(
            TraceView([self._traces[i] for i in shown], palette=self._palette)
        )
        self._detail_table.set_detail(trace_detail(self._frame, shown))
        self._detail_stack.setCurrentIndex(1)
