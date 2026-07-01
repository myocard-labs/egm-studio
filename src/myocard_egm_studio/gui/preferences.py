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
