"""Tests for the QSettings-backed theme preference (persistence)."""

from __future__ import annotations

from PySide6 import QtCore

from myocard_egm_studio.gui import preferences


def test_load_theme_returns_default_when_unset() -> None:
    assert preferences.load_theme("dark") == "dark"


def test_save_then_load_roundtrips() -> None:
    preferences.save_theme("vibrant")
    assert preferences.load_theme("dark") == "vibrant"


def test_load_theme_falls_back_on_unrecognised_value() -> None:
    QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        preferences.ORG_NAME,
        preferences.APP_NAME,
    ).setValue("appearance/theme", "chartreuse")
    assert preferences.load_theme("light") == "light"
