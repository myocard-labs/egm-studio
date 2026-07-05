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


def test_ui_scale_defaults_then_roundtrips() -> None:
    assert preferences.load_ui_scale(1.0) == 1.0  # unset -> default
    preferences.save_ui_scale(1.5)
    assert preferences.load_ui_scale(1.0) == 1.5


def test_ui_scale_falls_back_on_nonnumeric_value() -> None:
    QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        preferences.ORG_NAME,
        preferences.APP_NAME,
    ).setValue("appearance/ui_scale", "huge")
    assert preferences.load_ui_scale(0.9) == 0.9


def test_plot_kind_defaults_then_roundtrips() -> None:
    assert preferences.load_plot_kind("kde") == "kde"  # unset -> default
    preferences.save_plot_kind("histogram")
    assert preferences.load_plot_kind("kde") == "histogram"


def test_plot_kind_falls_back_on_unknown_value() -> None:
    QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        preferences.ORG_NAME,
        preferences.APP_NAME,
    ).setValue("appearance/plot_kind", "violin")
    assert preferences.load_plot_kind("kde") == "kde"


def test_confusion_norm_defaults_then_roundtrips() -> None:
    assert preferences.load_confusion_norm("row") == "row"  # unset -> default
    preferences.save_confusion_norm("col")
    assert preferences.load_confusion_norm("row") == "col"


def test_confusion_norm_falls_back_on_unknown_value() -> None:
    QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        preferences.ORG_NAME,
        preferences.APP_NAME,
    ).setValue("ml/confusion_norm", "diagonal")
    assert preferences.load_confusion_norm("row") == "row"


def test_scatter_axes_default_then_roundtrips() -> None:
    assert preferences.load_scatter_axes(("peak_to_peak", "sample_entropy")) == (
        "peak_to_peak",
        "sample_entropy",
    )  # unset -> default pair
    preferences.save_scatter_axes("dominant_frequency", "fractal_dimension")
    assert preferences.load_scatter_axes(("a", "b")) == ("dominant_frequency", "fractal_dimension")


def test_scratch_dir_defaults_to_app_data_scratch() -> None:
    assert preferences.default_scratch_dir().endswith("scratch")
    assert preferences.load_scratch_dir().endswith("scratch")  # unset -> default


def test_scratch_dir_roundtrips() -> None:
    preferences.save_scratch_dir("/tmp/my-scratch")
    assert preferences.load_scratch_dir() == "/tmp/my-scratch"


def test_auto_add_deps_defaults_then_roundtrips() -> None:
    assert preferences.load_auto_add_deps(True) is True  # unset -> default
    preferences.save_auto_add_deps(False)
    assert preferences.load_auto_add_deps(True) is False


def test_auto_add_deps_parses_a_stringified_bool() -> None:
    QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        preferences.ORG_NAME,
        preferences.APP_NAME,
    ).setValue("save/auto_add_dependencies", "false")  # IniFormat round-trips bools as strings
    assert preferences.load_auto_add_deps(True) is False
