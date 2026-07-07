"""Tests for the Settings dialog — scratch folder + theme (Block 10e)."""

from __future__ import annotations

import pytest
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.settings_dialog import SettingsDialog

_THEMES = ("dark", "light", "vibrant")


def test_getters_return_the_edited_values(qtbot: QtBot) -> None:
    dialog = SettingsDialog(scratch_dir="/tmp/scratch", theme="light", themes=_THEMES)
    qtbot.addWidget(dialog)
    assert dialog.scratch_dir() == "/tmp/scratch"
    assert dialog.theme() == "light"  # combo preselects the current theme


def test_edits_are_read_back(qtbot: QtBot) -> None:
    dialog = SettingsDialog(scratch_dir="/tmp/a", theme="dark", themes=_THEMES)
    qtbot.addWidget(dialog)
    scratch = dialog.findChild(QtWidgets.QLineEdit, "scratchDir")
    combo = dialog.findChild(QtWidgets.QComboBox, "themeCombo")
    assert isinstance(scratch, QtWidgets.QLineEdit) and isinstance(combo, QtWidgets.QComboBox)
    scratch.setText("  /tmp/b  ")
    combo.setCurrentIndex(_THEMES.index("vibrant"))
    assert dialog.scratch_dir() == "/tmp/b"  # stripped
    assert dialog.theme() == "vibrant"


def test_auto_add_deps_defaults_checked_and_reads_back(qtbot: QtBot) -> None:
    dialog = SettingsDialog(scratch_dir="/tmp/a", theme="dark", themes=_THEMES)
    qtbot.addWidget(dialog)
    check = dialog.findChild(QtWidgets.QCheckBox, "autoAddDeps")
    assert isinstance(check, QtWidgets.QCheckBox)
    assert dialog.auto_add_deps() is True  # default on
    check.setChecked(False)
    assert dialog.auto_add_deps() is False


def test_auto_add_deps_reflects_the_passed_state(qtbot: QtBot) -> None:
    dialog = SettingsDialog(scratch_dir="/tmp/a", theme="dark", themes=_THEMES, auto_add_deps=False)
    qtbot.addWidget(dialog)
    assert dialog.auto_add_deps() is False


def test_cache_ceiling_reflects_and_reads_back(qtbot: QtBot) -> None:
    """The cache-ceiling spinbox preselects the passed MB and reads back edits (Block 11)."""
    dialog = SettingsDialog(theme="dark", themes=_THEMES, cache_ceiling_mb=2048)
    qtbot.addWidget(dialog)
    assert dialog.cache_ceiling_mb() == 2048
    spin = dialog.findChild(QtWidgets.QSpinBox, "cacheCeiling")
    assert isinstance(spin, QtWidgets.QSpinBox)
    spin.setValue(4096)
    assert dialog.cache_ceiling_mb() == 4096


def test_flush_button_emits_flush_requested(qtbot: QtBot) -> None:
    """Clicking Flush emits flushRequested — the shell clears the store (Block 11)."""
    dialog = SettingsDialog(theme="dark", themes=_THEMES)
    qtbot.addWidget(dialog)
    button = dialog.findChild(QtWidgets.QPushButton, "flushCache")
    assert isinstance(button, QtWidgets.QPushButton)
    with qtbot.waitSignal(dialog.flushRequested):
        button.click()


def test_browse_sets_the_scratch_field(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    dialog = SettingsDialog(scratch_dir="/tmp/a", theme="dark", themes=_THEMES)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **k: "/tmp/picked"
    )
    browse = dialog.findChild(QtWidgets.QPushButton, "scratchBrowse")
    assert isinstance(browse, QtWidgets.QPushButton)
    browse.click()
    assert dialog.scratch_dir() == "/tmp/picked"
