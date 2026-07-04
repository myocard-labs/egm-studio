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


def test_recalculate_applies_the_spec(qtbot: QtBot) -> None:
    """Editing no longer emits live; pressing Recalculate applies the composed spec."""
    panel = _panel(qtbot)
    panel._add_row()  # first column (sample_entropy) is numeric; default op ">"
    panel._rows[0]._line.setText("1.5")  # edits do not fire recalculateRequested
    with qtbot.waitSignal(panel.recalculateRequested) as blocker:
        panel._recalc_button.click()
    assert blocker.args[0].conditions == (Condition("sample_entropy", ">", "1.5"),)


def test_recalculate_disabled_until_dirty_then_after_apply(qtbot: QtBot) -> None:
    """Recalculate enables only while the edited spec differs from the applied one."""
    panel = _panel(qtbot)
    assert not panel._recalc_button.isEnabled()  # a fresh load has nothing to apply
    panel._add_row()
    panel._rows[0]._line.setText("1.5")  # a real condition -> dirty
    assert panel._recalc_button.isEnabled()
    panel._recalc_button.click()  # apply
    assert not panel._recalc_button.isEnabled()  # shown result now matches the spec


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


def test_recalculate_carries_the_combinator(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._add_row()
    panel._rows[0]._line.setText("1.5")
    panel._combine.setCurrentIndex(1)  # "Match any"
    with qtbot.waitSignal(panel.recalculateRequested) as blocker:
        panel._recalc_button.click()
    assert blocker.args[0].combine == "or"


def test_match_all_that_exist_maps_to_and_present(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._combine.setCurrentText("Match all that exist")
    assert panel.spec().combine == "and_present"


def test_remove_condition(qtbot: QtBot) -> None:
    panel = _panel(qtbot)
    panel._add_row()
    assert len(panel._rows) == 1
    panel._rows[0].removed.emit()  # simulate the remove button
    assert panel._rows == []
    assert panel.spec().conditions == ()
