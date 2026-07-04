"""Curated figure-spec editor form — the left half of Flow C (Block 9).

A typed form over a :class:`FigureSpec`: the always-shown identity + inputs + output
fields, plus a per-recipe block of styling knobs driven by :data:`RECIPE_FIELDS`. On any
edit it rebuilds the spec and emits :attr:`specChanged`, which the view (B9c) resolves +
previews; debouncing lives at the view (B9d), so the form itself stays eager + dumb.

**Curated, not schema-generated.** Each recipe's editable knobs are hand-listed as
:class:`FieldSpec`s (the same keys the recipes actually read — ``styling.kind`` /
``inputs.positive_label`` / ...), matching the in-code field-config convention used for
the trace selector. Recipes with no scalar knobs (data-driven galleries / tables) simply
have no styling block. Fields the form doesn't expose (e.g. ``layout.features``) are
**preserved untouched** on every rebuild — the form overlays its edits onto the loaded
spec rather than reconstructing it from scratch, so nothing is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from myocard_egm_data.phases import FigureSpec
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.matplotlib import RECIPES

_FORMATS = ("pdf", "png", "svg")

__all__ = ["RECIPE_FIELDS", "FieldSpec", "FigureForm"]


@dataclass(frozen=True)
class FieldSpec:
    """One curated, editable knob of a recipe's spec.

    ``section`` says which loose spec dict the key lives in (``"styling"`` or
    ``"inputs"``); ``kind`` picks the widget (``choice`` / ``int`` / ``bool`` / ``text``).
    ``choices`` applies to ``choice``; ``minimum`` / ``maximum`` bound ``int``.
    """

    key: str
    section: str
    label: str
    kind: str
    default: Any
    choices: tuple[str, ...] = ()
    minimum: int = 0
    maximum: int = 1000


#: Per-recipe curated knobs — the keys each recipe reads from ``styling`` / ``inputs``.
#: Recipes absent here (bar-chart-with-deltas, trace-pair-gallery, summary-table,
#: training-curve) are data-driven and expose no scalar styling.
RECIPE_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    "feature-distribution-overlay": (
        FieldSpec("kind", "styling", "Curve kind", "choice", "kde", ("kde", "histogram")),
        FieldSpec("annotate", "styling", "Annotate", "choice", "ks", ("ks", "wasserstein", "none")),
        FieldSpec("bins", "styling", "Bins", "int", 40, minimum=1, maximum=500),
    ),
    "prediction-histogram": (
        FieldSpec("bins", "styling", "Bins", "int", 30, minimum=1, maximum=500),
        FieldSpec("density", "styling", "Density", "bool", False),
        FieldSpec("xlabel", "styling", "X-axis label", "text", "P(positive class)"),
    ),
    "calibration-reliability-diagram": (
        FieldSpec("n_bins", "styling", "Reliability bins", "int", 10, minimum=1, maximum=100),
        FieldSpec("positive_label", "inputs", "Positive label", "int", 1, minimum=0, maximum=100),
    ),
    "roc-curve-multi-line": (
        FieldSpec("positive_label", "inputs", "Positive label", "int", 1, minimum=0, maximum=100),
    ),
}


class FigureForm(QtWidgets.QWidget):
    """Edits a :class:`FigureSpec` and emits it on every change (:attr:`specChanged`)."""

    specChanged = QtCore.Signal(object)  # a rebuilt FigureSpec

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("figureForm")
        self._spec: FigureSpec | None = None  # the always-current spec (edits fold in here)
        self._loading = False  # guards populate-time signals from firing specChanged
        self._field_widgets: list[tuple[FieldSpec, QtWidgets.QWidget]] = []

        self._id_edit = QtWidgets.QLineEdit()
        self._id_edit.setObjectName("figSpecId")
        self._description_edit = QtWidgets.QLineEdit()
        self._recipe_combo = QtWidgets.QComboBox()
        self._recipe_combo.setObjectName("figSpecRecipe")
        self._recipe_combo.addItems(sorted(RECIPES))
        self._format_combo = QtWidgets.QComboBox()
        self._format_combo.addItems(_FORMATS)
        self._path_edit = QtWidgets.QLineEdit()

        self._groups = _GroupsTable()
        self._styling_box = QtWidgets.QGroupBox("Styling")
        self._styling_form = QtWidgets.QFormLayout(self._styling_box)

        self._build_layout()
        self._wire()

    # ---- construction ---------------------------------------------------- #

    def _build_layout(self) -> None:
        form = QtWidgets.QFormLayout()
        form.addRow("Figure id", self._id_edit)
        form.addRow("Description", self._description_edit)
        form.addRow("Recipe", self._recipe_combo)

        output_row = QtWidgets.QHBoxLayout()
        output_row.addWidget(self._format_combo)
        output_row.addWidget(self._path_edit, 1)
        form.addRow("Output", output_row)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel("Groups"))
        layout.addWidget(self._groups)
        layout.addWidget(self._styling_box)
        layout.addStretch(1)

    def _wire(self) -> None:
        self._id_edit.textEdited.connect(self._emit)
        self._description_edit.textEdited.connect(self._emit)
        self._path_edit.textEdited.connect(self._emit)
        self._format_combo.currentTextChanged.connect(self._emit)
        self._recipe_combo.currentTextChanged.connect(self._on_recipe_changed)
        self._groups.changed.connect(self._emit)

    # ---- public API ------------------------------------------------------ #

    def set_spec(self, spec: FigureSpec) -> None:
        """Populate every field from ``spec`` (without emitting :attr:`specChanged`)."""
        self._loading = True
        try:
            self._spec = spec
            self._id_edit.setText(spec.id)
            self._description_edit.setText(spec.description or "")
            self._select_recipe(spec.recipe)
            self._format_combo.setCurrentText(spec.output.format.value)
            self._path_edit.setText(spec.output.path)
            groups = (spec.inputs.groups if spec.inputs else None) or []
            self._groups.set_rows([(g.name, g.bank_id) for g in groups])
            self._rebuild_fields(spec)
        finally:
            self._loading = False

    def spec(self) -> FigureSpec:
        """The current spec — the loaded one with the form's edits overlaid.

        Raises :class:`RuntimeError` if called before :meth:`set_spec`.
        """
        if self._spec is None:
            raise RuntimeError("FigureForm.spec() called before set_spec()")
        return self._spec

    # ---- editing --------------------------------------------------------- #

    def _emit(self, *_args: Any) -> None:
        # *_args: Qt slots receive their signal's payload (textEdited(str), valueChanged(int),
        # ...); we ignore it and rebuild from the whole form.
        if self._loading:
            return
        self._spec = self._build_spec()
        self.specChanged.emit(self._spec)

    def _on_recipe_changed(self, *_args: Any) -> None:
        if self._loading:
            return
        # Fold the current edits in (under the *new* recipe name), then rebuild the
        # styling block for the new recipe — reading shared keys back from the folded
        # spec so e.g. an edited `bins` survives a recipe switch.
        self._spec = self._build_spec()
        self._loading = True
        try:
            self._rebuild_fields(self._spec)
        finally:
            self._loading = False
        self.specChanged.emit(self._spec)

    def _build_spec(self) -> FigureSpec:
        """Overlay the widgets' values onto the loaded spec's dict and re-validate.

        Dumps the loaded spec first so unknown / unedited keys (``layout.features``,
        extra ``styling`` entries) ride along untouched, then overwrites only what the
        form owns.
        """
        assert self._spec is not None
        raw = self._spec.model_dump(mode="json")
        raw["id"] = self._id_edit.text().strip()
        raw["description"] = self._description_edit.text().strip()
        raw["recipe"] = self._recipe_combo.currentText()
        raw["output"] = {
            "format": self._format_combo.currentText(),
            "path": self._path_edit.text().strip(),
        }

        inputs = dict(raw.get("inputs") or {})
        inputs["groups"] = [
            {"name": name, "bank_id": bank_id} for name, bank_id in self._groups.rows()
        ]
        styling = dict(raw.get("styling") or {})
        for spec_field, widget in self._field_widgets:
            target = inputs if spec_field.section == "inputs" else styling
            target[spec_field.key] = _read_widget(spec_field, widget)
        raw["inputs"] = inputs
        raw["styling"] = styling or None

        return FigureSpec.model_validate(raw)

    # ---- per-recipe styling block ---------------------------------------- #

    def _rebuild_fields(self, spec: FigureSpec) -> None:
        """Rebuild the styling block for ``spec.recipe``, seeded from ``spec``'s values."""
        while self._styling_form.rowCount():
            self._styling_form.removeRow(0)
        self._field_widgets = []
        fields = RECIPE_FIELDS.get(spec.recipe, ())
        self._styling_box.setVisible(bool(fields))
        for spec_field in fields:
            widget = _build_widget(spec_field, _field_value(spec, spec_field))
            _connect_widget(spec_field, widget, self._emit)
            self._styling_form.addRow(spec_field.label, widget)
            self._field_widgets.append((spec_field, widget))

    def _select_recipe(self, recipe: str) -> None:
        index = self._recipe_combo.findText(recipe)
        if index < 0:  # a spec naming an unregistered recipe — keep it selectable, don't drop it
            self._recipe_combo.addItem(recipe)
            index = self._recipe_combo.findText(recipe)
        self._recipe_combo.setCurrentIndex(index)


class _GroupsTable(QtWidgets.QWidget):
    """A small name / bank_id table with add + remove, emitting :attr:`changed` on edits."""

    changed = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self._table = QtWidgets.QTableWidget(0, 2)
        self._table.setObjectName("figSpecGroups")
        self._table.setHorizontalHeaderLabels(["Name", "Bank id"])
        self._table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(lambda _item: self.changed.emit())

        add = QtWidgets.QPushButton("Add")
        remove = QtWidgets.QPushButton("Remove")
        add.clicked.connect(self._add_row)
        remove.clicked.connect(self._remove_selected)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)
        layout.addLayout(buttons)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        blocked = self._table.blockSignals(True)  # bulk populate without per-cell changed spam
        try:
            self._table.setRowCount(0)
            for name, bank_id in rows:
                self._append(name, bank_id)
        finally:
            self._table.blockSignals(blocked)

    def rows(self) -> list[tuple[str, str]]:
        out = []
        for row in range(self._table.rowCount()):
            name = self._table.item(row, 0)
            bank_id = self._table.item(row, 1)
            out.append((name.text() if name else "", bank_id.text() if bank_id else ""))
        return out

    def _append(self, name: str, bank_id: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(bank_id))

    def _add_row(self) -> None:
        self._append("", "")
        self.changed.emit()

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self._table.removeRow(row)
        self.changed.emit()


# --------------------------------------------------------------------------- #
# Field widget helpers — one per FieldSpec.kind
# --------------------------------------------------------------------------- #


def _field_value(spec: FigureSpec, spec_field: FieldSpec) -> Any:
    """The spec's current value for ``spec_field`` (or its default)."""
    if spec_field.section == "inputs":
        source = (spec.inputs.model_extra if spec.inputs else None) or {}
    else:
        source = spec.styling or {}
    return source.get(spec_field.key, spec_field.default)


def _build_widget(spec_field: FieldSpec, value: Any) -> QtWidgets.QWidget:
    if spec_field.kind == "choice":
        combo = QtWidgets.QComboBox()
        combo.addItems(spec_field.choices)
        combo.setCurrentText(str(value))
        return combo
    if spec_field.kind == "int":
        spin = QtWidgets.QSpinBox()
        spin.setRange(spec_field.minimum, spec_field.maximum)
        spin.setValue(int(value))
        return spin
    if spec_field.kind == "bool":
        check = QtWidgets.QCheckBox()
        check.setChecked(bool(value))
        return check
    line = QtWidgets.QLineEdit()
    line.setText(str(value))
    return line


def _read_widget(spec_field: FieldSpec, widget: QtWidgets.QWidget) -> Any:
    if spec_field.kind == "choice":
        assert isinstance(widget, QtWidgets.QComboBox)
        return widget.currentText()
    if spec_field.kind == "int":
        assert isinstance(widget, QtWidgets.QSpinBox)
        return widget.value()
    if spec_field.kind == "bool":
        assert isinstance(widget, QtWidgets.QCheckBox)
        return widget.isChecked()
    assert isinstance(widget, QtWidgets.QLineEdit)
    return widget.text()


def _connect_widget(spec_field: FieldSpec, widget: QtWidgets.QWidget, slot: Any) -> None:
    if isinstance(widget, QtWidgets.QComboBox):
        widget.currentTextChanged.connect(slot)
    elif isinstance(widget, QtWidgets.QSpinBox):
        widget.valueChanged.connect(slot)
    elif isinstance(widget, QtWidgets.QCheckBox):
        widget.toggled.connect(slot)
    elif isinstance(widget, QtWidgets.QLineEdit):
        widget.textEdited.connect(slot)
