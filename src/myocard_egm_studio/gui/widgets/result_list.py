"""Sortable result list over the per-trace view-model (Block 7).

A table of the view-model rows the filter narrows to (``FilterPanel`` emits a spec,
the signal-exploration view applies it and hands the filtered frame here). Every
column is sortable — clicking a header orders by that column, numerically for the
feature / numeric columns (not lexically), so "sort by ``sample_entropy``
descending" behaves. Selecting rows emits their ``trace_idx`` values, which the
detail view (B7.6) resolves back to traces. Plumbing identity columns are hidden;
``trace_idx`` shows as ``#``.

This is the result-list role the metadata ``trace_selector`` is retired into once
the signal-exploration view wires filter -> list -> detail (B7.5).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from PySide6 import QtCore, QtWidgets

#: Per-item sort key (raw comparable value), so sorting is typed, not by display text.
_SORT_KEY = QtCore.Qt.ItemDataRole.UserRole

#: View-model plumbing columns the table never shows (``trace_idx`` shows as ``#``).
_HIDDEN = frozenset({"source_bank_id", "source_bank_type", "amp_type", "label"})


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
    """A sortable table of view-model rows; emits the selected rows' ``trace_idx``."""

    selectionChanged = QtCore.Signal(list)  # list[int] of trace_idx

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
        self._table.itemSelectionChanged.connect(self._emit_selection)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._count)
        layout.addWidget(self._table, 1)

    def set_frame(self, df: pd.DataFrame) -> None:
        """Show ``df`` (already filtered) — one row per trace, every column sortable."""
        frame = df.reset_index(drop=True)
        self._columns = [name for name in frame.columns if name not in _HIDDEN]
        self._table.setSortingEnabled(False)  # off while populating, else rows re-sort mid-fill
        self._table.clear()
        headers = ["#" if name == "trace_idx" else name for name in self._columns]
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(frame.index))
        for col, name in enumerate(self._columns):
            series = frame[name]
            for row in range(len(frame.index)):
                self._table.setItem(row, col, _cell(series.iat[row]))
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        self._count.setText(f"{len(frame.index)} trace(s)")
        self._emit_selection()

    def selected_trace_indices(self) -> list[int]:
        """The ``trace_idx`` of the selected rows (in table order, sort-aware)."""
        if "trace_idx" not in self._columns:
            return []
        idx_col = self._columns.index("trace_idx")
        rows = sorted({index.row() for index in self._table.selectionModel().selectedRows()})
        out: list[int] = []
        for row in rows:
            item = self._table.item(row, idx_col)
            if item is not None:
                out.append(int(item.data(_SORT_KEY)))
        return out

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(self.selected_trace_indices())
