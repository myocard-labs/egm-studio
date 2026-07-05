"""Tests for the shell's Settings wiring — scratch dir + theme sync (Block 10e)."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui import shell as shell_mod
from myocard_egm_studio.gui.shell import MainWindow


def test_settings_action_exists(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.findChild(QtGui.QAction, "openSettings") is not None


def test_set_theme_syncs_the_menu_checkmark(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._set_theme("light")
    assert window._current_theme == "light"
    light_action = window.findChild(QtGui.QAction, "themeAction_light")
    assert light_action is not None and light_action.isChecked()  # menu follows the change


def test_open_settings_persists_scratch_and_theme(qtbot: QtBot, monkeypatch: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    class _FakeDialog:
        def __init__(self, *args: object, **kwargs: object) -> None: ...
        def exec(self) -> int:
            return QtWidgets.QDialog.DialogCode.Accepted.value

        def scratch_dir(self) -> str:
            return "/tmp/new-scratch"

        def theme(self) -> str:
            return "vibrant"

    monkeypatch.setattr(shell_mod, "SettingsDialog", _FakeDialog)  # type: ignore[attr-defined]
    window._open_settings()

    assert window._scratch_dir == "/tmp/new-scratch"
    assert window._current_theme == "vibrant"  # applied via the shared _set_theme
