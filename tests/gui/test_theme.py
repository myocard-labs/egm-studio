"""Theme system tests (ADR-012): stylesheet building, the View toggle, persistence."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui import preferences
from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.gui.theme import (
    DEFAULT_THEME,
    THEME_NAMES,
    apply_theme,
    build_stylesheet,
)
from myocard_egm_studio.gui.theme.palette import DARK, LIGHT, PALETTES, VIBRANT


def test_default_theme_is_dark_and_three_themes_ship() -> None:
    assert DEFAULT_THEME == "dark"
    assert THEME_NAMES == ("dark", "light", "vibrant")


def test_build_stylesheet_substitutes_every_token() -> None:
    for palette in (DARK, LIGHT, VIBRANT):
        qss = build_stylesheet(palette)
        assert palette.window_bg in qss
        assert palette.title in qss
        assert "$" not in qss  # no placeholder left unsubstituted


def test_build_stylesheet_differs_per_theme() -> None:
    sheets = {build_stylesheet(p) for p in (DARK, LIGHT, VIBRANT)}
    assert len(sheets) == 3


def test_apply_theme_sets_app_stylesheet(qapp: QtWidgets.QApplication) -> None:
    apply_theme(qapp, "vibrant")
    assert PALETTES["vibrant"].window_bg in qapp.styleSheet()
    apply_theme(qapp, "dark")
    assert PALETTES["dark"].window_bg in qapp.styleSheet()


def test_view_theme_toggle_applies_and_persists(qtbot: QtBot, qapp: QtWidgets.QApplication) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    action = window.findChild(QtGui.QAction, "themeAction_vibrant")
    assert action is not None
    action.trigger()
    assert PALETTES["vibrant"].window_bg in qapp.styleSheet()
    assert preferences.load_theme(DEFAULT_THEME) == "vibrant"  # persisted for next launch


def test_shell_ticks_persisted_theme_on_open(qtbot: QtBot) -> None:
    preferences.save_theme("light")
    window = MainWindow()
    qtbot.addWidget(window)

    action = window.findChild(QtGui.QAction, "themeAction_light")
    assert action is not None
    assert action.isChecked()
