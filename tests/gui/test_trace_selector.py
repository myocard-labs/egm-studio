"""Tests for the metadata trace selector (gui/widgets/trace_selector)."""

from __future__ import annotations

import numpy as np
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import BankTrace, LoadedBank, TraceData, TraceSelector


def _trace(index: int, patient: str, channel: str, klass: str = "healthy") -> BankTrace:
    data = TraceData(np.zeros(10, dtype=np.float64), 1000.0, f"{patient} · {channel}")
    fields = {"patient_id": patient, "source_channel": channel, "class": klass}
    return BankTrace(index=index, fields=fields, data=data)


def _bank(*rows: BankTrace) -> LoadedBank:
    return LoadedBank(bank_type="iafdb", traces=list(rows))


def test_set_bank_builds_curated_columns(qtbot: QtBot) -> None:
    selector = TraceSelector()
    qtbot.addWidget(selector)
    selector.set_bank(_bank(_trace(0, "P01", "1"), _trace(1, "P02", "2")))
    assert selector._table.rowCount() == 2
    assert selector._table.columnCount() == 4  # # + Patient + Channel + Class


def test_select_first_emits_visible_rows(qtbot: QtBot) -> None:
    selector = TraceSelector()
    qtbot.addWidget(selector)
    selector.set_bank(_bank(_trace(0, "P01", "1"), _trace(1, "P02", "2"), _trace(2, "P03", "3")))
    with qtbot.waitSignal(selector.selectionChanged) as blocker:
        selector.select_first(2)
    assert [bt.index for bt in blocker.args[0]] == [0, 1]


def test_filter_narrows_selectable_rows(qtbot: QtBot) -> None:
    selector = TraceSelector()
    qtbot.addWidget(selector)
    selector.set_bank(_bank(_trace(0, "P01", "1"), _trace(1, "P02", "2"), _trace(2, "P01", "3")))

    selector._filters["patient_id"].setCurrentText("P01")
    selector.select_first(10)
    assert {bt.fields["patient_id"] for bt in selector.selected_traces()} == {"P01"}


def test_filter_values_sort_numerically(qtbot: QtBot) -> None:
    selector = TraceSelector()
    qtbot.addWidget(selector)
    rows = [_trace(i, "P01", channel) for i, channel in enumerate(["1", "2", "10", "20"])]
    selector.set_bank(_bank(*rows))

    combo = selector._filters["source_channel"]
    items = [combo.itemText(i) for i in range(combo.count())]
    assert items == ["All", "1", "2", "10", "20"]  # numeric order, not "1, 10, 2, 20"
