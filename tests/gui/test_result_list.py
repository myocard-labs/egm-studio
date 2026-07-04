"""Tests for the sortable result list (gui/widgets/result_list)."""

from __future__ import annotations

import pandas as pd
from PySide6 import QtCore
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import ResultList


def _df() -> pd.DataFrame:
    # row_id distinct from trace_idx (as it would be for a second loaded bank), so
    # the selection tests prove the list emits row_id, not the per-bank trace_idx.
    return pd.DataFrame(
        {
            "trace_idx": [0, 1, 2],
            "row_id": [10, 11, 12],  # hidden global key
            "source_bank_id": ["b", "b", "b"],  # hidden plumbing column
            "source": ["synthetic", "synthetic", "iafdb"],
            "label_name": ["healthy", "fibrotic", "healthy"],
            "sample_entropy": [2.0, 10.0, 1.0],
        }
    )


def _list(qtbot: QtBot) -> ResultList:
    widget = ResultList()
    qtbot.addWidget(widget)
    widget.set_frame(_df())
    return widget


def _headers(widget: ResultList) -> list[str]:
    table = widget._table
    out: list[str] = []
    for c in range(table.columnCount()):
        item = table.horizontalHeaderItem(c)
        assert item is not None
        out.append(item.text())
    return out


def _hash_column(widget: ResultList) -> list[str]:
    table = widget._table
    col = widget._columns.index("trace_idx")
    out: list[str] = []
    for r in range(table.rowCount()):
        item = table.item(r, col)
        assert item is not None
        out.append(item.text())
    return out


def test_set_frame_populates_and_hides_plumbing(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    headers = _headers(widget)
    assert "#" in headers  # trace_idx renders as #
    assert {"source", "label_name", "sample_entropy"}.issubset(headers)
    assert "source_bank_id" not in headers  # a hidden plumbing column
    assert widget._table.isColumnHidden(widget._columns.index("row_id"))  # hidden, not dropped
    assert widget._table.rowCount() == 3
    assert "3 trace(s)" in widget._count.text()


def test_numeric_columns_sort_numerically(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    entropy_col = widget._columns.index("sample_entropy")
    widget._table.sortItems(entropy_col, QtCore.Qt.SortOrder.AscendingOrder)
    # entropies 2.0(#0) 10.0(#1) 1.0(#2) -> ascending 1,2,10 -> # column order 2,0,1
    # (lexical text sort would give 2,1,0 — "1" < "10" < "2")
    assert _hash_column(widget) == ["2", "0", "1"]


def test_selection_emits_row_id(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    with qtbot.waitSignal(widget.selectionChanged) as blocker:
        widget._table.selectRow(0)
    assert blocker.args[0] == [10]  # row_id of the first row, not its trace_idx (0)


def test_set_frame_reports_progress(qtbot: QtBot) -> None:
    """The table build reports (rows_done, rows_total), bracketed by (0, n)…(n, n)."""
    widget = ResultList()
    qtbot.addWidget(widget)
    seen: list[tuple[int, int]] = []
    widget.set_frame(_df(), progress=lambda done, total: seen.append((done, total)))
    assert seen[0] == (0, 3)
    assert seen[-1] == (3, 3)


def test_selection_is_sort_aware(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    entropy_col = widget._columns.index("sample_entropy")
    widget._table.sortItems(entropy_col, QtCore.Qt.SortOrder.AscendingOrder)
    with qtbot.waitSignal(widget.selectionChanged) as blocker:
        widget._table.selectRow(0)  # smallest entropy -> trace_idx 2 / row_id 12
    assert blocker.args[0] == [12]


def test_select_row_ids_selects_by_row_id(qtbot: QtBot) -> None:
    """select_row_ids (the scatter-click entry point) selects by row_id + emits it."""
    widget = _list(qtbot)
    with qtbot.waitSignal(widget.selectionChanged) as blocker:
        widget.select_row_ids([12])  # the third row's global key
    assert blocker.args[0] == [12]
    assert widget.selected_row_ids() == [12]


def test_select_row_ids_is_sort_agnostic(qtbot: QtBot) -> None:
    """A row_id resolves to its row regardless of the current sort order."""
    widget = _list(qtbot)
    entropy_col = widget._columns.index("sample_entropy")
    widget._table.sortItems(entropy_col, QtCore.Qt.SortOrder.DescendingOrder)
    widget.select_row_ids([10])  # row_id 10 (entropy 2.0) sits mid-table when sorted
    assert widget.selected_row_ids() == [10]
