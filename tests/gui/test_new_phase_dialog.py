"""Tests for the New-phase dialog — phase number + destination folder (Block 10e)."""

from __future__ import annotations

import pytest
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.new_phase_dialog import NewPhaseDialog


def test_getters_return_the_entered_values(qtbot: QtBot) -> None:
    dialog = NewPhaseDialog(phase=2.0)
    qtbot.addWidget(dialog)
    spin = dialog.findChild(QtWidgets.QDoubleSpinBox, "phaseNumber")
    folder = dialog.findChild(QtWidgets.QLineEdit, "phaseFolder")
    assert isinstance(spin, QtWidgets.QDoubleSpinBox) and isinstance(folder, QtWidgets.QLineEdit)
    spin.setValue(1.5)  # half-phases allowed
    folder.setText("  /tmp/phase_1_5  ")
    assert dialog.phase() == 1.5
    assert dialog.folder() == "/tmp/phase_1_5"  # stripped


def test_create_is_disabled_until_a_folder_is_chosen(qtbot: QtBot) -> None:
    dialog = NewPhaseDialog()
    qtbot.addWidget(dialog)
    buttons = dialog.findChild(QtWidgets.QDialogButtonBox)
    assert isinstance(buttons, QtWidgets.QDialogButtonBox)
    create = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    assert create is not None and create.text() == "Create"
    assert not create.isEnabled()  # no folder yet

    folder = dialog.findChild(QtWidgets.QLineEdit, "phaseFolder")
    assert isinstance(folder, QtWidgets.QLineEdit)
    folder.setText("/tmp/phase_1")
    assert create.isEnabled()


def test_browse_sets_the_folder_field(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    dialog = NewPhaseDialog()
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **k: "/tmp/picked_phase"
    )
    browse = dialog.findChild(QtWidgets.QPushButton, "phaseFolderBrowse")
    assert isinstance(browse, QtWidgets.QPushButton)
    browse.click()
    assert dialog.folder() == "/tmp/picked_phase"
