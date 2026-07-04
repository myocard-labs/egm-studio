"""Per-trace detail pane — waveforms + feature/metadata table + pluggable finds (B8g).

The shared bottom half of an Explore tab: a selected trace's waveform(s) beside its
feature + metadata (and ML-outcome) values, over a row of "find related traces"
controls. The finds are :class:`Finder` strategies passed at construction, so Flow A
and Flow B reuse the same pane with different diagnostics — Flow A finds the nearest
trace in each other bank; Flow B finds a misclassification's nearest correctly-classified
counterpart, or a trace's in-class peers.

Selecting rows (``on_selection``) tracks the single "source" row (needed by the finds)
and renders the detail; a find (``run_finder``) shows the source beside its matches. The
view owns the result list + wires its ``selectionChanged`` / ``findSimilarRequested`` here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.gui.widgets.trace import TraceData
from myocard_egm_studio.gui.widgets.trace_view import TraceView
from myocard_egm_studio.view_model import FEATURE_COLUMNS, DetailRow, TraceDetail, trace_detail

_DETAIL_CAP = 3  # traces shown side-by-side (the 3-pane comparison cap)
_SELECT_PROMPT = "Select trace(s) in the list to view"


def _always(_frame: pd.DataFrame, _row_id: int) -> bool:
    return True


@dataclass(frozen=True)
class Finder:
    """One "find related traces" strategy for the detail pane.

    ``find(frame, source_row_id, feature) -> [row_id, ...]`` returns the matches to show
    beside the source (order preserved). ``can_run(frame, source_row_id)`` gates its button
    (beyond a single selection) — e.g. Flow A needs a second bank present.
    """

    label: str
    find: Callable[[pd.DataFrame, int, str], list[int]]
    can_run: Callable[[pd.DataFrame, int], bool] = field(default=_always)


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


def _cells_with_deltas(row: DetailRow) -> list[str]:
    """Per-trace value cells; rows with deltas append each column's change vs the source."""
    if not row.deltas:
        return list(row.values)
    return [
        f"{value}  ({delta})" if delta else value
        for value, delta in zip(row.values, row.deltas, strict=True)
    ]


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
    """Right detail pane: the selected trace(s)' Features / Model / Metadata values."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("traceDetailTable")
        self.setColumnCount(1)
        self.setMinimumWidth(280)  # keep value columns visible beside the wider waveform pane

    def set_detail(self, detail: TraceDetail) -> None:
        self.clear()
        self.setColumnCount(1 + len(detail.headers))
        self.setHeaderLabels(["Attribute", *detail.headers])
        self._add_section("Features", detail.features)
        self._add_section("Model", detail.ml)  # ML-outcome rows (empty for a raw bank)
        self._add_section("Metadata", detail.metadata)
        self.expandAll()
        for column in range(self.columnCount()):
            self.resizeColumnToContents(column)
        self.setColumnWidth(0, min(self.columnWidth(0), 190))

    def _add_section(self, title: str, rows: Sequence[DetailRow]) -> None:
        if not rows:
            return
        section = QtWidgets.QTreeWidgetItem([title])
        self.addTopLevelItem(section)
        for row in rows:
            label = f"{row.label} ({row.unit})" if row.unit else row.label
            section.addChild(QtWidgets.QTreeWidgetItem([label, *_cells_with_deltas(row)]))


class ExploreDetail(QtWidgets.QWidget):
    """Waveforms + value table for the selected trace(s), with pluggable find controls."""

    def __init__(
        self,
        palette: Any,
        finders: Sequence[Finder],
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("exploreDetail")
        self._palette = palette
        self._finders = list(finders)
        self._frame = pd.DataFrame()
        self._traces: list[TraceData] = []
        self._source_row_id: int | None = None

        self._waveforms = _WaveformHost()
        self._detail_table = _TraceDetailTable()
        panes = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        panes.addWidget(self._waveforms)
        panes.addWidget(self._detail_table)
        panes.setStretchFactor(0, 3)
        panes.setStretchFactor(1, 2)

        page = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addLayout(self._build_find_control())
        page_layout.addWidget(panes, 1)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(_placeholder(_SELECT_PROMPT))  # page 0 — nothing selected
        self._stack.addWidget(page)  # page 1 — controls + waveforms + values
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

    def _build_find_control(self) -> QtWidgets.QHBoxLayout:
        self._feature_combo = QtWidgets.QComboBox()
        self._feature_combo.setObjectName("findFeature")
        self._feature_combo.addItems(FEATURE_COLUMNS)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 0)
        row.addWidget(QtWidgets.QLabel("Find along"))
        row.addWidget(self._feature_combo)
        self._buttons: list[QtWidgets.QPushButton] = []
        for index, finder in enumerate(self._finders):
            button = QtWidgets.QPushButton(finder.label)
            button.setObjectName("findButton")
            button.clicked.connect(lambda *_, i=index: self._on_find_clicked(i))
            row.addWidget(button)
            self._buttons.append(button)
        row.addStretch(1)
        self._update_find_enabled()
        return row

    def set_context(self, frame: pd.DataFrame, traces: Sequence[TraceData]) -> None:
        """Set the frame the finds search + the display traces the detail resolves into."""
        self._frame = frame
        self._traces = list(traces)
        self._update_find_enabled()

    def on_selection(self, row_ids: list[int]) -> None:
        """React to a result-list selection: track the source row, then show the detail."""
        self._source_row_id = row_ids[0] if len(row_ids) == 1 else None
        self._update_find_enabled()
        self.show_rows(row_ids)

    def run_finder(self, index: int, source_row_id: int) -> None:
        """Show ``source_row_id`` beside the matches its ``index``-th finder returns."""
        finder = self._finders[index]
        matches = finder.find(self._frame, source_row_id, self._feature_combo.currentText())
        self.show_rows([source_row_id, *matches])

    def show_rows(self, row_ids: Sequence[int]) -> None:
        """Render the detail for ``row_ids`` (capped, source-first); empty -> the prompt."""
        shown = [i for i in row_ids[:_DETAIL_CAP] if 0 <= i < len(self._traces)]
        if not shown:
            self._stack.setCurrentIndex(0)
            return
        self._waveforms.show_widget(
            TraceView([self._traces[i] for i in shown], palette=self._palette)
        )
        self._detail_table.set_detail(trace_detail(self._frame, shown))
        self._stack.setCurrentIndex(1)

    def restyle(self, palette: Any) -> None:
        """Re-apply the theme to an open waveform view (the shell calls this on a toggle)."""
        self._palette = palette
        content = self._waveforms.content
        if isinstance(content, TraceView):
            content.restyle(palette)

    def _on_find_clicked(self, index: int) -> None:
        if self._source_row_id is not None:
            self.run_finder(index, self._source_row_id)

    def _update_find_enabled(self) -> None:
        """Show a find button only when it applies to the current source (else hide it).

        A find that can't run on the selected trace (e.g. "Find nearest correct" on a
        correctly-classified trace) is hidden rather than greyed — no dead button.
        """
        source = self._source_row_id
        for button, finder in zip(self._buttons, self._finders, strict=True):
            applicable = source is not None and finder.can_run(self._frame, source)
            button.setVisible(applicable)
            button.setEnabled(applicable)
