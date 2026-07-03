"""Flow A signal-exploration view — assembled load -> filter -> list -> detail (Block 7).

The main-area content for the Signal-exploration mode: a sortable ``ResultList`` of
the view-model rows over a per-trace detail pane. The shell owns the bank + the
sidebar ``FilterPanel`` and feeds this view the (filtered) frame; selecting rows
here shows those traces' waveforms in the detail. Up to three traces compare at
once (the walkthrough's 3-pane cap); the feature table + metadata panel land in
B7.6, and the ">3 -> bank summary" fallback in B7.7.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.gui.widgets import ResultList, TraceData, TraceView

_DETAIL_CAP = 3  # traces shown side-by-side in the detail (the 3-pane comparison cap)
_SELECT_PROMPT = "Select trace(s) in the list to view"


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class _DetailHost(QtWidgets.QWidget):
    """Bottom pane: swaps between a placeholder and a TraceView of the selected traces."""

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

    def show_placeholder(self, text: str = _SELECT_PROMPT) -> None:
        self.show_widget(_placeholder(text))

    @property
    def content(self) -> QtWidgets.QWidget:
        return self._content


class SignalExplorationView(QtWidgets.QWidget):
    """A sortable result list over a per-trace detail pane; fed the filtered frame."""

    def __init__(self, palette: Any, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("signalExplorationView")
        self._palette = palette
        self._traces: list[TraceData] = []

        self._result_list = ResultList()
        self._result_list.selectionChanged.connect(self._show_detail)
        self._detail = _DetailHost()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.setObjectName("exploreSplitter")
        splitter.addWidget(self._result_list)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def set_traces(self, traces: Sequence[TraceData]) -> None:
        """Set the display traces of a newly opened bank (indexed by ``trace_idx``)."""
        self._traces = list(traces)
        self._detail.show_placeholder()

    def set_results(self, frame: pd.DataFrame) -> None:
        """Show the rows the filter kept (also called with the full frame on open)."""
        self._result_list.set_frame(frame)

    @property
    def result_list(self) -> ResultList:
        return self._result_list

    def restyle(self, palette: Any) -> None:
        """Re-apply the plot palette to the open detail (on a theme change)."""
        self._palette = palette
        content = self._detail.content
        if isinstance(content, TraceView):
            content.restyle(palette)

    def _show_detail(self, trace_indices: list[int]) -> None:
        shown = [self._traces[i] for i in trace_indices[:_DETAIL_CAP] if 0 <= i < len(self._traces)]
        if not shown:
            self._detail.show_placeholder()
            return
        self._detail.show_widget(TraceView(shown, palette=self._palette))
