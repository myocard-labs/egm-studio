"""Metadata trace selector — a curated, filterable table for picking traces (B5.1e).

Lists a loaded bank's traces with a curated, per-bank-type set of columns (see
:mod:`myocard_egm_studio.gui.field_config`) and a filter dropdown per categorical
field, so the user narrows thousands of traces to the ones of interest and picks
which to view. Full feature-value filtering (``sample_entropy > x`` ...) is
Block 7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.gui.field_config import FieldSpec, fields_for
from myocard_egm_studio.gui.widgets.trace import TraceData

_ALL = "All"
_NUM_CHUNK = re.compile(r"(\d+)")


def _natural_key(value: str) -> list[tuple[int, str]]:
    """Sort key that orders embedded numbers by value, so "2" sorts before "10"."""
    key: list[tuple[int, str]] = []
    for chunk in _NUM_CHUNK.split(value):
        if chunk.isdigit():
            key.append((0, chunk.zfill(12)))  # zero-pad -> string compare matches numeric
        elif chunk:
            key.append((1, chunk.lower()))
    return key


@dataclass(frozen=True)
class BankTrace:
    """One loaded trace: its (stringified) metadata fields + the display data."""

    index: int
    fields: dict[str, str]
    data: TraceData


@dataclass(frozen=True)
class LoadedBank:
    """A bank opened for the selector: its type + adapted traces."""

    bank_type: str
    traces: list[BankTrace]


def _item(text: str) -> QtWidgets.QTableWidgetItem:
    return QtWidgets.QTableWidgetItem(text)


class TraceSelector(QtWidgets.QWidget):
    """A curated, filterable trace table; emits the selected (visible) BankTrace rows."""

    selectionChanged = QtCore.Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[BankTrace] = []
        self._specs: list[FieldSpec] = []
        self._filters: dict[str, QtWidgets.QComboBox] = {}

        self._filter_form = QtWidgets.QFormLayout()
        self._filter_form.setContentsMargins(0, 0, 0, 6)
        filter_host = QtWidgets.QWidget()
        filter_host.setLayout(self._filter_form)

        self._table = QtWidgets.QTableWidget(0, 0)
        self._table.setObjectName("traceTable")
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._emit_selection)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(filter_host)
        layout.addWidget(self._table, 1)

    def set_bank(self, loaded: LoadedBank) -> None:
        """Populate the table + filters from ``loaded`` (curated columns per bank type)."""
        self._rows = list(loaded.traces)
        present = {key for bt in self._rows for key in bt.fields}
        self._specs = fields_for(loaded.bank_type, present)
        self._rebuild_filters()
        self._rebuild_table()
        self._apply_filters()

    def select_first(self, count: int) -> None:
        """Select the first ``count`` currently-visible rows (drives the initial view)."""
        self._table.blockSignals(True)
        self._table.clearSelection()
        visible = [r for r in range(self._table.rowCount()) if not self._table.isRowHidden(r)]
        last_col = max(self._table.columnCount() - 1, 0)
        for r in visible[:count]:
            self._table.setRangeSelected(
                QtWidgets.QTableWidgetSelectionRange(r, 0, r, last_col), True
            )
        self._table.blockSignals(False)
        self._emit_selection()

    def selected_traces(self) -> list[BankTrace]:
        """The selected + visible BankTrace rows, in table order."""
        rows = sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})
        return [self._rows[r] for r in rows if not self._table.isRowHidden(r)]

    # -- construction / filtering ---------------------------------------------

    def _rebuild_filters(self) -> None:
        while self._filter_form.rowCount():
            self._filter_form.removeRow(0)
        self._filters.clear()
        for spec in self._specs:
            values = sorted(
                {bt.fields.get(spec.key, "") for bt in self._rows} - {""}, key=_natural_key
            )
            if len(values) < 2:  # constant field: no useful filter
                continue
            combo = QtWidgets.QComboBox()
            combo.addItem(_ALL)
            combo.addItems(values)
            combo.currentIndexChanged.connect(self._apply_filters)
            self._filters[spec.key] = combo
            self._filter_form.addRow(spec.label, combo)

    def _rebuild_table(self) -> None:
        self._table.blockSignals(True)
        headers = ["#", *(spec.label for spec in self._specs)]
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(self._rows))
        for r, bt in enumerate(self._rows):
            self._table.setItem(r, 0, _item(str(bt.index)))
            for c, spec in enumerate(self._specs, start=1):
                self._table.setItem(r, c, _item(bt.fields.get(spec.key, "")))
        self._table.resizeColumnsToContents()
        self._table.blockSignals(False)

    def _apply_filters(self) -> None:
        active = {k: c.currentText() for k, c in self._filters.items() if c.currentText() != _ALL}
        for r, bt in enumerate(self._rows):
            hidden = any(bt.fields.get(key, "") != value for key, value in active.items())
            self._table.setRowHidden(r, hidden)
        self._emit_selection()

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(self.selected_traces())
