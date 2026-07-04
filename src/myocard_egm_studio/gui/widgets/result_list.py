"""Sortable result list over the per-trace view-model (Block 7).

A table of the view-model rows the filter narrows to (``FilterPanel`` emits a spec,
the signal-exploration view applies it and hands the filtered frame here). Every
column is sortable — clicking a header orders by that column, numerically for the
feature / numeric columns (not lexically), so "sort by ``sample_entropy``
descending" behaves. Selecting rows emits their ``row_id`` values (the multi-bank
global key, B7.8), which the detail view resolves back to traces. Plumbing identity
columns are hidden; ``trace_idx`` shows as ``#`` and ``row_id`` is a hidden column
(present per row so it survives sorting, but never displayed).

This is the result-list role the metadata ``trace_selector`` is retired into once
the signal-exploration view wires filter -> list -> detail (B7.5).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pandas as pd
from PySide6 import QtCore, QtWidgets

#: Per-item sort key (raw comparable value), so sorting is typed, not by display text.
_SORT_KEY = QtCore.Qt.ItemDataRole.UserRole

#: View-model plumbing columns the table never shows (``trace_idx`` shows as ``#``).
_HIDDEN = frozenset({"source_bank_id", "source_bank_type", "amp_type", "label"})

#: The global row key (B7.8): kept as a hidden column so selection reads it per row.
_ROW_ID = "row_id"

#: Rows populated between progress ticks on a big-bank load (keeps the UI painting).
_ROW_CHUNK = 500
#: Cap the rows auto-resize scans, so a huge table's column-fit stays ~O(1) not O(N).
_RESIZE_PRECISION = 200


class _Cell(QtWidgets.QTableWidgetItem):
    """A table cell that sorts by its stored :data:`_SORT_KEY` (number or string)."""

    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        left, right = self.data(_SORT_KEY), other.data(_SORT_KEY)
        if left is None or right is None:
            return left is None and right is not None  # blanks sort first
        return bool(left < right)


def _cell(value: Any) -> _Cell:
    """Build a cell: numeric values sort numerically, others as text; NaN -> blank."""
    item = _Cell()
    if pd.isna(value):
        item.setData(_SORT_KEY, None)
        return item
    if isinstance(value, (int, float, np.number)):
        number = float(value)
        item.setText(str(int(number)) if number.is_integer() else f"{number:g}")
        item.setData(_SORT_KEY, number)
    else:
        item.setText(str(value))
        item.setData(_SORT_KEY, str(value))
    return item


class ResultList(QtWidgets.QWidget):
    """A sortable table of view-model rows; emits the selected rows' ``row_id``."""

    selectionChanged = QtCore.Signal(list)  # list[int] of row_id
    findSimilarRequested = QtCore.Signal(int)  # row_id of the right-clicked row (B7.10)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("resultList")
        self._columns: list[str] = []

        self._count = QtWidgets.QLabel("No bank loaded")
        self._count.setObjectName("resultCount")

        self._table = QtWidgets.QTableWidget(0, 0)
        self._table.setObjectName("resultTable")
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setResizeContentsPrecision(_RESIZE_PRECISION)
        self._table.itemSelectionChanged.connect(self._emit_selection)
        self._table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._count)
        layout.addWidget(self._table, 1)

    def set_frame(
        self, df: pd.DataFrame, *, progress: Callable[[int, int], None] | None = None
    ) -> None:
        """Show ``df`` (already filtered) — one row per trace, every column sortable.

        ``progress`` (the initial big-bank load, B7.8b-perf) is called
        ``(rows_done, rows_total)`` as the table populates, so the caller can drive a
        progress bar + pump events; it stays None for the small filter updates.
        """
        frame = df.reset_index(drop=True)
        self._columns = [name for name in frame.columns if name not in _HIDDEN]
        self._table.setSortingEnabled(False)  # off while populating, else rows re-sort mid-fill
        self._table.clear()
        headers = ["#" if name == "trace_idx" else name for name in self._columns]
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        rows = len(frame.index)
        self._table.setRowCount(rows)
        series = [frame[name] for name in self._columns]  # indexed per row below
        for row in range(rows):
            for col, col_series in enumerate(series):
                self._table.setItem(row, col, _cell(col_series.iat[row]))
            if progress is not None and row % _ROW_CHUNK == 0:
                progress(row, rows)
        if progress is not None:
            progress(rows, rows)
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        if _ROW_ID in self._columns:  # queryable per row, but never shown
            self._table.setColumnHidden(self._columns.index(_ROW_ID), True)
        self._count.setText(f"{rows} trace(s)")
        self._emit_selection()

    def selected_row_ids(self) -> list[int]:
        """The ``row_id`` of the selected rows (in table order, sort-aware)."""
        if _ROW_ID not in self._columns:
            return []
        id_col = self._columns.index(_ROW_ID)
        rows = sorted({index.row() for index in self._table.selectionModel().selectedRows()})
        out: list[int] = []
        for row in rows:
            item = self._table.item(row, id_col)
            if item is not None:
                out.append(int(item.data(_SORT_KEY)))
        return out

    def select_row_ids(self, ids: Sequence[int]) -> None:
        """Select the rows whose ``row_id`` is in ``ids`` (sort / filter-order agnostic).

        The scatter view calls this when a point is clicked, so the click drives the
        same ``selectionChanged`` -> detail path as clicking the row (B7.9c). Rows are
        matched by the hidden ``row_id`` column, so sorting doesn't matter; the first
        match is scrolled into view. A no-op if no row carries a wanted id.
        """
        if _ROW_ID not in self._columns:
            return
        id_col = self._columns.index(_ROW_ID)
        wanted = {int(i) for i in ids}
        model = self._table.model()
        selection = QtCore.QItemSelection()
        first_row: int | None = None
        for row in range(self._table.rowCount()):
            item = self._table.item(row, id_col)
            if item is not None and int(item.data(_SORT_KEY)) in wanted:
                selection.select(
                    model.index(row, 0), model.index(row, self._table.columnCount() - 1)
                )
                first_row = row if first_row is None else first_row
        flag = QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
        self._table.selectionModel().select(selection, flag)
        anchor = self._table.item(first_row, 0) if first_row is not None else None
        if anchor is not None:
            self._table.scrollToItem(anchor)

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(self.selected_row_ids())

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        """Right-click a row -> 'Find similar in other bank', emitting that row's row_id."""
        item = self._table.itemAt(pos)
        row_id = self._row_id_at(item.row()) if item is not None else None
        if row_id is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Find similar in other bank").triggered.connect(
            lambda *_: self.findSimilarRequested.emit(row_id)
        )
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _row_id_at(self, row: int) -> int | None:
        """The ``row_id`` at table ``row`` (hidden column), or None if unavailable."""
        if _ROW_ID not in self._columns:
            return None
        item = self._table.item(row, self._columns.index(_ROW_ID))
        return int(item.data(_SORT_KEY)) if item is not None else None
