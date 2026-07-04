"""Flow A signal-exploration view — assembled load -> filter -> list -> detail (Block 7).

The main-area content for the Signal-exploration mode: a sortable ``ResultList`` of
the view-model rows over a per-trace detail pane. The shell owns the bank + the
sidebar ``FilterPanel`` and feeds this view the (filtered) frame; selecting rows
here pairs their waveforms (up to the 3-pane cap) with a feature + metadata table
of the selected trace(s). Multiple selected traces become side-by-side value
columns — the seed of the B7.10 compare view.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.gui.widgets import ResultList, TraceData, TraceView
from myocard_egm_studio.view_model import TraceDetail, trace_detail

_DETAIL_CAP = 3  # traces shown side-by-side in the detail (the 3-pane comparison cap)
_SELECT_PROMPT = "Select trace(s) in the list to view"


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


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
    """A sortable result list over a per-trace detail (waveforms + feature table)."""

    def __init__(self, palette: Any, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("signalExplorationView")
        self._palette = palette
        self._traces: list[TraceData] = []
        self._frame = pd.DataFrame()

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

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def set_traces(self, traces: Sequence[TraceData]) -> None:
        """Set the display traces of a newly opened bank (indexed by ``trace_idx``)."""
        self._traces = list(traces)
        self._detail_stack.setCurrentIndex(0)

    def set_results(self, frame: pd.DataFrame) -> None:
        """Show the rows the filter kept (also called with the full frame on open)."""
        self._frame = frame
        self._result_list.set_frame(frame)

    @property
    def result_list(self) -> ResultList:
        return self._result_list

    def restyle(self, palette: Any) -> None:
        """Re-apply the plot palette to the open detail (on a theme change)."""
        self._palette = palette
        content = self._waveforms.content
        if isinstance(content, TraceView):
            content.restyle(palette)

    def _show_detail(self, trace_indices: list[int]) -> None:
        shown = [i for i in trace_indices[:_DETAIL_CAP] if 0 <= i < len(self._traces)]
        if not shown:
            self._detail_stack.setCurrentIndex(0)
            return
        self._waveforms.show_widget(
            TraceView([self._traces[i] for i in shown], palette=self._palette)
        )
        self._detail_table.set_detail(trace_detail(self._frame, shown))
        self._detail_stack.setCurrentIndex(1)
