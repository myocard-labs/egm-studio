"""Sortable result list over the per-trace view-model (Block 7; model/view — Block 11).

A table of the view-model rows the filter narrows to (``FilterPanel`` emits a spec,
the signal-exploration view applies it and hands the filtered frame here). Every
column is sortable — clicking a header orders by that column, numerically for the
feature / numeric columns (not lexically), so "sort by ``sample_entropy``
descending" behaves. Selecting rows emits their ``row_id`` values (the multi-bank
global key, B7.8), which the detail view resolves back to traces.

**Block 11 — model/view.** The table is a :class:`QtWidgets.QTableView` backed by a
:class:`QtCore.QAbstractTableModel` over the whole (already filtered) frame, with a
sort proxy on top. This replaces the old eager ``QTableWidget``, which allocated one
``QTableWidgetItem`` per cell — ~11 s and ~900 MB on a 66k-row IAFDB-scale frame
(profiling, 2026-07-06). The model holds column arrays, so *every* row is visible to
filter / select / match (ADR-011) while the view renders only the visible rows; the
freeze + the memory spike are both gone. ``row_id`` and the plumbing identity columns
are not display columns — ``row_id`` is kept as a side array so selection reads it per
row; ``trace_idx`` shows as ``#``.

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

#: The global row key (B7.8): held as a side array (not a column) so selection reads it.
_ROW_ID = "row_id"

#: Cap the rows auto-resize scans, so a huge table's column-fit stays ~O(1), not O(N).
_RESIZE_PRECISION = 200


def _display_text(value: Any) -> str:
    """Cell display: ints as ints, floats compactly, NaN / None as blank, else text."""
    if pd.isna(value):
        return ""
    if isinstance(value, (int, float, np.number)):
        number = float(value)
        return str(int(number)) if number.is_integer() else f"{number:g}"
    return str(value)


def _sort_value(value: Any) -> float | str | None:
    """Typed sort key: numbers compare numerically, others as text, NaN / None -> None."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, np.number)):
        return float(value)
    return str(value)


class _ResultModel(QtCore.QAbstractTableModel):
    """Column-array model over the filtered frame; formats + sort-keys cells on demand."""

    def __init__(self) -> None:
        super().__init__()
        self._headers: list[str] = []
        self._columns: list[Any] = []  # one numpy array per display column
        self._n_rows = 0
        self._row_ids: list[int] = []  # per source row; empty when the frame has no row_id
        self._row_id_to_src: dict[int, int] = {}

    def set_data(self, headers: list[str], columns: list[Any], row_ids: list[int]) -> None:
        """Reset to new display columns (+ their arrays) and the per-row ``row_id`` side list."""
        self.beginResetModel()
        self._headers = headers
        self._columns = columns
        self._n_rows = len(columns[0]) if columns else 0
        self._row_ids = row_ids
        self._row_id_to_src = {rid: src for src, rid in enumerate(row_ids)}
        self.endResetModel()

    def rowCount(
        self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()
    ) -> int:
        return 0 if parent.isValid() else self._n_rows

    def columnCount(
        self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()
    ) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def data(
        self,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        value = self._columns[index.column()][index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return _display_text(value)
        if role == _SORT_KEY:
            return _sort_value(value)
        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal and 0 <= section < len(self._headers):
            name = self._headers[section]
            return "#" if name == "trace_idx" else name
        return None

    def row_id_at(self, source_row: int) -> int | None:
        """The ``row_id`` at a *source* (unsorted) row, or None if the frame carried none."""
        if 0 <= source_row < len(self._row_ids):
            return self._row_ids[source_row]
        return None

    def source_rows_for(self, ids: Sequence[int]) -> list[int]:
        """Source rows whose ``row_id`` is in ``ids`` (sort / filter-order agnostic)."""
        wanted = {int(i) for i in ids}
        return [self._row_id_to_src[i] for i in wanted if i in self._row_id_to_src]


class _SortProxy(QtCore.QSortFilterProxyModel):
    """Sort by the typed :data:`_SORT_KEY` (numbers numerically), NaN / blanks first."""

    def lessThan(
        self,
        source_left: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
        source_right: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
    ) -> bool:
        model = self.sourceModel()
        left = model.data(source_left, _SORT_KEY)
        right = model.data(source_right, _SORT_KEY)
        if left is None or right is None:
            return left is None and right is not None  # blanks sort first
        return bool(left < right)


class ResultList(QtWidgets.QWidget):
    """A sortable table of view-model rows; emits the selected rows' ``row_id``."""

    selectionChanged = QtCore.Signal(list)  # list[int] of row_id
    findSimilarRequested = QtCore.Signal(int)  # row_id of the right-clicked row (B7.10)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("resultList")

        self._count = QtWidgets.QLabel("No bank loaded")
        self._count.setObjectName("resultCount")

        self._model = _ResultModel()
        self._proxy = _SortProxy()
        self._proxy.setSourceModel(self._model)

        self._table = QtWidgets.QTableView()
        self._table.setObjectName("resultTable")
        self._table.setModel(self._proxy)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        # Enabling sorting picks an initial header indicator (and sorts by it); clear it so
        # the table opens in source/load order and only sorts once the user clicks a header.
        self._table.sortByColumn(-1, QtCore.Qt.SortOrder.AscendingOrder)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setResizeContentsPrecision(_RESIZE_PRECISION)
        self._table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        selection = self._table.selectionModel()
        selection.selectionChanged.connect(lambda *_: self._emit_selection())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._count)
        layout.addWidget(self._table, 1)

    def set_frame(
        self, df: pd.DataFrame, *, progress: Callable[[int, int], None] | None = None
    ) -> None:
        """Show ``df`` (already filtered) — one row per trace, every column sortable.

        The model resets in one shot (no per-cell widget build), so this is effectively
        instant even at IAFDB scale. ``progress`` (the initial big-bank load,
        B7.8b-perf) is still bracketed ``(0, n)`` … ``(n, n)`` so a caller driving a
        progress bar sees completion; it stays None for the small filter updates.
        """
        frame = df.reset_index(drop=True)
        display = [name for name in frame.columns if name not in _HIDDEN and name != _ROW_ID]
        rows = len(frame.index)
        if progress is not None:
            progress(0, rows)
        columns = [frame[name].to_numpy() for name in display]
        row_ids = [int(v) for v in frame[_ROW_ID].tolist()] if _ROW_ID in frame.columns else []
        self._model.set_data(display, columns, row_ids)
        if progress is not None:
            progress(rows, rows)
        self._table.resizeColumnsToContents()
        self._count.setText(f"{rows} trace(s)")
        self._emit_selection()

    def row_count(self) -> int:
        """Number of rows currently shown (post-filter)."""
        return self._proxy.rowCount()

    def selected_row_ids(self) -> list[int]:
        """The ``row_id`` of the selected rows (in table order, sort-aware)."""
        selection = self._table.selectionModel()
        out: list[int] = []
        for proxy_row in sorted({index.row() for index in selection.selectedRows()}):
            source_row = self._proxy.mapToSource(self._proxy.index(proxy_row, 0)).row()
            row_id = self._model.row_id_at(source_row)
            if row_id is not None:
                out.append(row_id)
        return out

    def select_row_ids(self, ids: Sequence[int]) -> None:
        """Select the rows whose ``row_id`` is in ``ids`` (sort / filter-order agnostic).

        The scatter view calls this when a point is clicked, so the click drives the
        same ``selectionChanged`` -> detail path as clicking the row (B7.9c). Rows are
        matched by their ``row_id``, so sorting doesn't matter; the first match is
        scrolled into view. A no-op if no row carries a wanted id.
        """
        source_rows = self._model.source_rows_for(ids)
        if not source_rows:
            return
        last_col = self._proxy.columnCount() - 1
        selection = QtCore.QItemSelection()
        first_proxy_row: int | None = None
        for source_row in source_rows:
            proxy_row = self._proxy.mapFromSource(self._model.index(source_row, 0)).row()
            selection.select(
                self._proxy.index(proxy_row, 0), self._proxy.index(proxy_row, last_col)
            )
            first_proxy_row = (
                proxy_row if first_proxy_row is None else min(first_proxy_row, proxy_row)
            )
        flag = QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
        self._table.selectionModel().select(selection, flag)
        if first_proxy_row is not None:
            self._table.scrollTo(self._proxy.index(first_proxy_row, 0))

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(self.selected_row_ids())

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        """Right-click a row -> 'Find similar in other bank', emitting that row's row_id."""
        index = self._table.indexAt(pos)
        row_id = self._row_id_at(index.row()) if index.isValid() else None
        if row_id is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Find similar in other bank").triggered.connect(
            lambda *_: self.findSimilarRequested.emit(row_id)
        )
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _row_id_at(self, row: int) -> int | None:
        """The ``row_id`` at a *table* (proxy) row, mapping through the sort proxy."""
        if row < 0:
            return None
        source_row = self._proxy.mapToSource(self._proxy.index(row, 0)).row()
        return self._model.row_id_at(source_row)
