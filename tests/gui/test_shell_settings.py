"""Tests for the shell's Settings wiring — scratch dir + theme sync (Block 10e)."""

from __future__ import annotations

import pandas as pd
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui import shell as shell_mod
from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.view_model import view_model_key


class _FakeSignal:
    """A no-op stand-in for a Qt signal, so a fake dialog can be `.connect`-ed."""

    def connect(self, _callback: object) -> None: ...


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


def test_open_settings_persists_scratch_theme_and_cache(qtbot: QtBot, monkeypatch: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    class _FakeDialog:
        flushRequested = _FakeSignal()

        def __init__(self, *args: object, **kwargs: object) -> None: ...
        def exec(self) -> int:
            return QtWidgets.QDialog.DialogCode.Accepted.value

        def scratch_dir(self) -> str:
            return "/tmp/new-scratch"

        def theme(self) -> str:
            return "vibrant"

        def auto_add_deps(self) -> bool:
            return False

        def cache_ceiling_mb(self) -> int:
            return 512

    monkeypatch.setattr(shell_mod, "SettingsDialog", _FakeDialog)  # type: ignore[attr-defined]
    window._open_settings()

    assert window._scratch_dir == "/tmp/new-scratch"
    assert window._current_theme == "vibrant"  # applied via the shared _set_theme
    assert window._auto_add_deps is False  # the toggle is read back + applied (B10h-1b)
    assert window._cache_ceiling_mb == 512  # the cache ceiling is read back + persisted
    assert window._frame_store._ceiling == 512 * 1024 * 1024  # applied to the store (Block 11)


def test_flush_cache_clears_the_frame_store(qtbot: QtBot) -> None:
    """Settings ▸ Flush cache now empties the view-model store (Block 11)."""
    window = MainWindow()
    qtbot.addWidget(window)
    key = view_model_key(bank_id="tbank_x_2026-07-06", source="S")
    window._frame_store.get_or_compute(key, lambda: pd.DataFrame({"a": [1, 2, 3]}))
    assert len(window._frame_store) == 1
    window._flush_cache(window)  # the QMessageBox is stubbed non-blocking in the gui suite
    assert len(window._frame_store) == 0
