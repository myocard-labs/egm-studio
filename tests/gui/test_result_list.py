"""Tests for the sortable result list (gui/widgets/result_list)."""

from __future__ import annotations

import pandas as pd
from PySide6 import QtCore
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import ResultList


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trace_idx": [0, 1, 2],
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
    assert widget._table.rowCount() == 3
    assert "3 trace(s)" in widget._count.text()


def test_numeric_columns_sort_numerically(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    entropy_col = widget._columns.index("sample_entropy")
    widget._table.sortItems(entropy_col, QtCore.Qt.SortOrder.AscendingOrder)
    # entropies 2.0(#0) 10.0(#1) 1.0(#2) -> ascending 1,2,10 -> # column order 2,0,1
    # (lexical text sort would give 2,1,0 — "1" < "10" < "2")
    assert _hash_column(widget) == ["2", "0", "1"]


def test_selection_emits_trace_idx(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    with qtbot.waitSignal(widget.selectionChanged) as blocker:
        widget._table.selectRow(0)
    assert blocker.args[0] == [0]


def test_selection_is_sort_aware(qtbot: QtBot) -> None:
    widget = _list(qtbot)
    entropy_col = widget._columns.index("sample_entropy")
    widget._table.sortItems(entropy_col, QtCore.Qt.SortOrder.AscendingOrder)
    with qtbot.waitSignal(widget.selectionChanged) as blocker:
        widget._table.selectRow(0)  # smallest entropy -> trace_idx 2
    assert blocker.args[0] == [2]
