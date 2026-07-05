"""Composable filter panel over the per-trace view-model (Block 7, ADR-002).

A flat list of condition rows (column / operator / value) combined by one
"Match all" (AND) / "Match any" (OR). Editing the conditions does **not** recompute
live — a big bank's result rebuild is slow — so the user composes several conditions
and then presses **Recalculate** to apply them at once (:attr:`recalculateRequested`).
The logic is pure (:mod:`view_model.filtering`) — this widget only edits a spec. Each
row's editor follows its column: numeric columns get a validated value field +
threshold operators; categorical ones get a value dropdown of the column's known
values + equality operators, so an invalid spec can't be built.

Feeds the result list (B7.4); the signal-exploration view (B7.5) hands in
``filter_columns(df)`` and applies the spec on Recalculate.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.view_model.filtering import (
    COMBINE_LABELS,
    Condition,
    FilterColumn,
    FilterSpec,
)

#: Combine dropdown entries + the parallel FilterSpec codes, derived from the single-source
#: :data:`COMBINE_LABELS` (dict insertion order = dropdown order).
_COMBINE_VALUES = tuple(COMBINE_LABELS)
_COMBINE_LABEL_TEXT = tuple(COMBINE_LABELS.values())


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


class _ConditionRow(QtWidgets.QWidget):
    """One ``column op value`` row; emits :attr:`changed` on edit, :attr:`removed` on delete."""

    changed = QtCore.Signal()
    removed = QtCore.Signal()

    def __init__(
        self, columns: Sequence[FilterColumn], parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._by_name = {column.name: column for column in columns}

        self._column = QtWidgets.QComboBox()
        self._column.addItems([column.name for column in columns])
        self._op = QtWidgets.QComboBox()
        self._value = QtWidgets.QStackedWidget()
        self._line = QtWidgets.QLineEdit()
        self._line.setValidator(QtGui.QDoubleValidator())
        self._line.setPlaceholderText("value")
        self._choice = QtWidgets.QComboBox()
        self._value.addWidget(self._line)  # page 0 — numeric
        self._value.addWidget(self._choice)  # page 1 — categorical
        remove = QtWidgets.QToolButton()
        remove.setText("×")  # noqa: RUF001 — deliberate remove-button glyph
        remove.setToolTip("Remove condition")

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._column, 3)
        row.addWidget(self._op, 2)
        row.addWidget(self._value, 3)
        row.addWidget(remove, 0)

        self._column.currentIndexChanged.connect(self._on_column)
        self._op.currentIndexChanged.connect(self.changed)
        self._line.textChanged.connect(self.changed)
        self._choice.currentIndexChanged.connect(self.changed)
        remove.clicked.connect(self.removed)
        self._on_column()

    def _on_column(self) -> None:
        column = self._current_column()
        if column is None:
            return
        self._op.blockSignals(True)
        self._op.clear()
        self._op.addItems(column.ops)
        self._op.blockSignals(False)
        if column.numeric:
            self._value.setCurrentIndex(0)
        else:
            self._choice.blockSignals(True)
            self._choice.clear()
            self._choice.addItems(column.choices)
            self._choice.blockSignals(False)
            self._value.setCurrentIndex(1)
        self.changed.emit()

    def _current_column(self) -> FilterColumn | None:
        return self._by_name.get(self._column.currentText())

    def condition(self) -> Condition | None:
        """The row's Condition, or None if incomplete (blank / non-numeric value)."""
        column = self._current_column()
        if column is None:
            return None
        if column.numeric:
            value = self._line.text().strip()
            if not _is_number(value):
                return None
        else:
            value = self._choice.currentText()
            if not value:
                return None
        return Condition(column=column.name, op=self._op.currentText(), value=value)

    def set_condition(self, condition: Condition) -> None:
        """Populate the row from ``condition`` (best-effort — ignores an unknown column)."""
        column = self._by_name.get(condition.column)
        if column is None:
            return
        self._column.setCurrentText(condition.column)  # fires _on_column -> op list + value page
        op_index = self._op.findText(condition.op)
        if op_index >= 0:
            self._op.setCurrentIndex(op_index)
        if column.numeric:
            self._line.setText(condition.value)
        else:
            choice_index = self._choice.findText(condition.value)
            if choice_index >= 0:
                self._choice.setCurrentIndex(choice_index)


class FilterPanel(QtWidgets.QWidget):
    """Edits a FilterSpec over the view-model; applies it on an explicit Recalculate.

    Editing conditions only updates the spec; :attr:`recalculateRequested` fires when
    the user presses **Recalculate**, so several conditions apply in one (potentially
    slow) rebuild rather than one per keystroke. The button enables only while the
    edited spec differs from the last applied one, so an unchanged filter can't
    trigger a needless recompute.
    """

    recalculateRequested = QtCore.Signal(object)  # a view_model.FilterSpec, on apply

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filterPanel")
        self._columns: list[FilterColumn] = []
        self._rows: list[_ConditionRow] = []
        self._applied = FilterSpec()  # the spec the shown result currently reflects

        self._combine = QtWidgets.QComboBox()
        self._combine.setObjectName("filterCombine")
        self._combine.addItems(_COMBINE_LABEL_TEXT)
        self._combine.currentIndexChanged.connect(self._sync_recalc)

        self._rows_box = QtWidgets.QVBoxLayout()
        self._rows_box.setContentsMargins(0, 0, 0, 0)
        rows_host = QtWidgets.QWidget()
        rows_host.setLayout(self._rows_box)

        self._add_button = QtWidgets.QPushButton("+ Add condition")
        self._add_button.setObjectName("addCondition")
        self._add_button.clicked.connect(self._add_row)

        self._recalc_button = QtWidgets.QPushButton("Recalculate")
        self._recalc_button.setObjectName("recalculate")
        self._recalc_button.setToolTip("Apply the filter conditions to the result list")
        self._recalc_button.clicked.connect(self._apply)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Match"))
        top.addWidget(self._combine, 1)
        layout.addLayout(top)
        layout.addWidget(rows_host)
        layout.addWidget(self._add_button)
        layout.addWidget(self._recalc_button)
        layout.addStretch(1)
        self._sync_recalc()

    def set_columns(self, columns: Sequence[FilterColumn]) -> None:
        """Set the offered columns (from ``filter_columns(df)``) and reset the rows.

        A fresh load shows the full frame, i.e. the empty filter — so the applied spec
        resets to empty and Recalculate starts disabled until a condition is added.
        """
        self._columns = list(columns)
        self._clear_rows()
        self._add_button.setEnabled(bool(self._columns))
        self._applied = FilterSpec()
        self._sync_recalc()

    def spec(self) -> FilterSpec:
        """The current (edited) FilterSpec (incomplete rows are dropped)."""
        conditions = tuple(c for c in (row.condition() for row in self._rows) if c is not None)
        return FilterSpec(
            conditions=conditions, combine=_COMBINE_VALUES[self._combine.currentIndex()]
        )

    def set_spec(self, spec: FilterSpec) -> None:
        """Restore the panel to ``spec`` (combine + condition rows) — used to reload a
        saved observation's view (B10). Columns must already be set (:meth:`set_columns`);
        a condition naming an unknown column is skipped. The restored spec is marked as
        applied, so Recalculate stays disabled until the user changes something.
        """
        if spec.combine in _COMBINE_VALUES:
            self._combine.setCurrentIndex(_COMBINE_VALUES.index(spec.combine))
        self._clear_rows()
        known = {column.name for column in self._columns}
        for condition in spec.conditions:
            if condition.column in known:
                self._new_row().set_condition(condition)
        self._applied = self.spec()
        self._sync_recalc()

    def _new_row(self) -> _ConditionRow:
        """Create, wire, and mount a fresh condition row (shared by add + restore)."""
        row = _ConditionRow(self._columns)
        row.changed.connect(self._sync_recalc)
        row.removed.connect(lambda: self._remove_row(row))
        self._rows.append(row)
        self._rows_box.addWidget(row)
        return row

    def _add_row(self) -> None:
        if not self._columns:
            return
        self._new_row()
        self._sync_recalc()

    def _remove_row(self, row: _ConditionRow) -> None:
        if row in self._rows:
            self._rows.remove(row)
            self._rows_box.removeWidget(row)
            row.deleteLater()
            self._sync_recalc()

    def _clear_rows(self) -> None:
        for row in self._rows:
            self._rows_box.removeWidget(row)
            row.deleteLater()
        self._rows = []

    def _apply(self) -> None:
        """Apply the edited spec (the Recalculate button) and mark it as the shown one."""
        self._applied = self.spec()
        self._sync_recalc()
        self.recalculateRequested.emit(self._applied)

    def _sync_recalc(self) -> None:
        """Enable Recalculate only when the edited spec differs from the applied one."""
        self._recalc_button.setEnabled(bool(self._columns) and self.spec() != self._applied)
