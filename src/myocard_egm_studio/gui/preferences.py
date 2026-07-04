"""Persisted GUI preferences via Qt ``QSettings`` (seed of the ADR-017 save-state).

Currently one key — the selected theme — so the shell reopens in the theme the
user last chose (ADR-012's "user-preference theme key"). Backed by the platform
native per-user store, keyed on the org / app identity below (also set on the
QApplication in :mod:`.app`). More save-state keys (column widths, sidebar
collapse, ...) join here as ADR-017 is implemented.
"""

from __future__ import annotations

from PySide6 import QtCore

from myocard_egm_studio.gui.theme import THEME_NAMES, ThemeName

ORG_NAME = "myocard-labs"
APP_NAME = "egm-studio"
_THEME_KEY = "appearance/theme"
_UI_SCALE_KEY = "appearance/ui_scale"
_PLOT_KIND_KEY = "appearance/plot_kind"
_PLOT_KINDS = ("kde", "histogram")


def _settings() -> QtCore.QSettings:
    """A QSettings handle for the app's per-user store (IniFormat, user scope)."""
    return QtCore.QSettings(
        QtCore.QSettings.Format.IniFormat,
        QtCore.QSettings.Scope.UserScope,
        ORG_NAME,
        APP_NAME,
    )


def load_theme(default: ThemeName) -> ThemeName:
    """Return the persisted theme, or ``default`` if unset / unrecognised."""
    raw = _settings().value(_THEME_KEY, default)
    for name in THEME_NAMES:
        if raw == name:
            return name
    return default


def save_theme(name: ThemeName) -> None:
    """Persist ``name`` as the theme to restore on next launch."""
    _settings().setValue(_THEME_KEY, name)


def load_ui_scale(default: float) -> float:
    """Return the persisted ADR-018 panel scale factor, or ``default`` if unset."""
    raw = _settings().value(_UI_SCALE_KEY, default)
    try:
        return float(str(raw))  # QSettings.value returns object; IniFormat stores as str
    except (TypeError, ValueError):
        return default


def save_ui_scale(value: float) -> None:
    """Persist the panel scale factor (ADR-018) to restore on next launch."""
    _settings().setValue(_UI_SCALE_KEY, float(value))


def load_plot_kind(default: str) -> str:
    """Return the persisted summary plot kind (``kde`` / ``histogram``), or ``default``."""
    raw = _settings().value(_PLOT_KIND_KEY, default)
    return str(raw) if raw in _PLOT_KINDS else default


def save_plot_kind(kind: str) -> None:
    """Persist the summary plot kind (KDE / histogram) to restore on next launch."""
    _settings().setValue(_PLOT_KIND_KEY, kind)
