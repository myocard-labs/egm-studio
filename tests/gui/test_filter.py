"""Tests for the composable filter widget (gui/widgets/filter)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import FilterPanel
from myocard_egm_studio.view_model.filtering import Condition, FilterColumn, FilterSpec

_COLUMNS = (
    FilterColumn("sample_entropy", numeric=True),
    FilterColumn("source", numeric=False, choices=("iafdb", "synthetic")),
)


def _panel(qtbot: QtBot) -> FilterPanel:
    panel = FilterPanel()
    qtbot.addWidget(panel)
    panel.set_columns(_COLUMNS)
    return panel


def test_empty_panel_spec_is_empty(qtbot: QtBot) -> None:
    assert _panel(qtbot).spec() == FilterSpec(conditions=(), combine="and")


def test_add_numeric_condition_emits_spec(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._add_row()  # first column (sample_entropy) is numeric; default op ">"
    row = panel._rows[0]
    with qtbot.waitSignal(panel.filterChanged) as blocker:
        row._line.setText("1.5")
    assert blocker.args[0].conditions == (Condition("sample_entropy", ">", "1.5"),)


def test_categorical_condition_uses_choices(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._add_row()
    row = panel._rows[0]
    row._column.setCurrentText("source")  # switch to categorical -> equality + value combo
    row._choice.setCurrentText("synthetic")
    assert panel.spec().conditions == (Condition("source", "==", "synthetic"),)


def test_incomplete_row_is_dropped(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._add_row()  # numeric row with a blank value
    assert panel.spec().conditions == ()  # not emitted until the value parses


def test_combinator_toggle_changes_combine(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    with qtbot.waitSignal(panel.filterChanged) as blocker:
        panel._combine.setCurrentIndex(1)  # "Match any"
    assert blocker.args[0].combine == "or"


def test_remove_condition(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._add_row()
    assert len(panel._rows) == 1
    panel._rows[0].removed.emit()  # simulate the remove button
    assert panel._rows == []
    assert panel.spec().conditions == ()
