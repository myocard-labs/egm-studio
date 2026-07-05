"""Tests for the Save-observation dialog — title/description gating (Block 10c)."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.save_observation_dialog import SaveObservationDialog


def _save_button(dialog: SaveObservationDialog) -> QtWidgets.QPushButton:
    box = dialog.findChild(QtWidgets.QDialogButtonBox)
    assert isinstance(box, QtWidgets.QDialogButtonBox)
    button = box.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
    assert button is not None
    return button


def _title_edit(dialog: SaveObservationDialog) -> QtWidgets.QLineEdit:
    edit = dialog.findChild(QtWidgets.QLineEdit, "observationTitle")
    assert isinstance(edit, QtWidgets.QLineEdit)
    return edit


def _description_edit(dialog: SaveObservationDialog) -> QtWidgets.QPlainTextEdit:
    edit = dialog.findChild(QtWidgets.QPlainTextEdit, "observationDescription")
    assert isinstance(edit, QtWidgets.QPlainTextEdit)
    return edit


def test_save_disabled_until_title_and_description(qtbot: QtBot) -> None:
    dialog = SaveObservationDialog(summary="Will capture: 1 bank(s)")
    qtbot.addWidget(dialog)
    save = _save_button(dialog)
    assert not save.isEnabled()  # both fields empty

    _title_edit(dialog).setText("Late gain")
    assert not save.isEnabled()  # description still empty

    _description_edit(dialog).setPlainText("bipolar amplitude climbs toward the scar edge")
    assert save.isEnabled()  # both present


def test_title_and_description_are_stripped(qtbot: QtBot) -> None:
    dialog = SaveObservationDialog()
    qtbot.addWidget(dialog)
    _title_edit(dialog).setText("  Late gain  ")
    _description_edit(dialog).setPlainText("  prose  ")
    assert dialog.title() == "Late gain"
    assert dialog.description() == "prose"


def test_summary_text_is_displayed(qtbot: QtBot) -> None:
    summary = "Will capture: 2 bank(s), no filter, 0 trace(s) selected."
    dialog = SaveObservationDialog(summary=summary)
    qtbot.addWidget(dialog)
    shown = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
    assert any(summary in text for text in shown)


def _parent_list(dialog: SaveObservationDialog) -> QtWidgets.QListWidget:
    widget = dialog.findChild(QtWidgets.QListWidget, "observationParents")
    assert isinstance(widget, QtWidgets.QListWidget)
    return widget


def test_parents_reflect_checked_items(qtbot: QtBot) -> None:
    dialog = SaveObservationDialog(parent_observations=["obs_a_2026-06-27", "obs_b_2026-06-27"])
    qtbot.addWidget(dialog)
    assert dialog.parents() == []  # nothing checked initially
    item = _parent_list(dialog).item(1)
    assert item is not None
    item.setCheckState(QtCore.Qt.CheckState.Checked)
    assert dialog.parents() == ["obs_b_2026-06-27"]


def test_selected_parents_are_prechecked(qtbot: QtBot) -> None:
    dialog = SaveObservationDialog(
        parent_observations=["obs_a_2026-06-27", "obs_b_2026-06-27"],
        selected_parents=["obs_a_2026-06-27"],
    )
    qtbot.addWidget(dialog)
    assert dialog.parents() == ["obs_a_2026-06-27"]


def test_no_candidates_disables_the_parent_list(qtbot: QtBot) -> None:
    dialog = SaveObservationDialog(parent_observations=[])
    qtbot.addWidget(dialog)
    assert dialog.parents() == []
    assert not _parent_list(dialog).isEnabled()  # nothing to link to


def test_edit_mode_shows_id_and_prefills_without_summary(qtbot: QtBot) -> None:
    dialog = SaveObservationDialog(
        summary="should be hidden in edit mode",
        observation_id="obs_late_gain_2026-07-05",
        title="Late gain",
        description="prose body",
        parent_observations=["obs_a_2026-06-27"],
        selected_parents=["obs_a_2026-06-27"],
    )
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Edit observation"
    assert dialog.title() == "Late gain"
    assert dialog.description() == "prose body"
    assert dialog.parents() == ["obs_a_2026-06-27"]
    labels = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
    assert "obs_late_gain_2026-07-05" in labels  # id shown read-only
    assert "should be hidden in edit mode" not in labels  # capture summary dropped when editing
    assert _save_button(dialog).isEnabled()  # prefilled -> immediately saveable
