"""Persisted GUI preferences via Qt ``QSettings`` (seed of the ADR-017 save-state).

Currently one key — the selected theme — so the shell reopens in the theme the
user last chose (ADR-012's "user-preference theme key"). Backed by the platform
native per-user store, keyed on the org / app identity below (also set on the
QApplication in :mod:`.app`). More save-state keys (column widths, sidebar
collapse, ...) join here as ADR-017 is implemented.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore

from myocard_egm_studio.gui.theme import THEME_NAMES, ThemeName

ORG_NAME = "myocard-labs"
APP_NAME = "egm-studio"
_THEME_KEY = "appearance/theme"
_UI_SCALE_KEY = "appearance/ui_scale"
_PLOT_KIND_KEY = "appearance/plot_kind"
_PLOT_KINDS = ("kde", "histogram")
_SCATTER_X_KEY = "signal/scatter_x"
_SCATTER_Y_KEY = "signal/scatter_y"
_CONFUSION_NORM_KEY = "ml/confusion_norm"
_CONFUSION_NORMS = ("row", "col", "overall", "count")
_SCRATCH_DIR_KEY = "save/scratch_dir"
_AUTO_ADD_DEPS_KEY = "save/auto_add_dependencies"
_CACHE_CEILING_KEY = "cache/memory_ceiling_mb"


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


def load_confusion_norm(default: str) -> str:
    """Return the persisted confusion-matrix cell mode (row / col / overall / count)."""
    raw = _settings().value(_CONFUSION_NORM_KEY, default)
    return str(raw) if raw in _CONFUSION_NORMS else default


def save_confusion_norm(norm: str) -> None:
    """Persist the confusion-matrix cell mode (Flow B metrics) to restore on next launch."""
    _settings().setValue(_CONFUSION_NORM_KEY, norm)


def load_scatter_axes(default: tuple[str, str]) -> tuple[str, str]:
    """Return the persisted ``(x, y)`` scatter feature axes, or ``default`` if unset.

    The stored names are validated against the live feature set by the scatter
    widget (an unknown name falls back to a column), so this just restores the pair.
    """
    settings = _settings()
    default_x, default_y = default
    return str(settings.value(_SCATTER_X_KEY, default_x)), str(
        settings.value(_SCATTER_Y_KEY, default_y)
    )


def save_scatter_axes(x: str, y: str) -> None:
    """Persist the scatter feature axes (x, y) to restore on next launch."""
    settings = _settings()
    settings.setValue(_SCATTER_X_KEY, x)
    settings.setValue(_SCATTER_Y_KEY, y)


def default_scratch_dir() -> str:
    """The per-user default scratch folder — ``<app-data>/scratch`` (created lazily).

    Where observations / figure specs saved with no phase loaded land (ADR-017 scratch
    mode) until promoted into a phase. Overridable in Settings; the app-data root follows
    the org/app identity, so it is stable per user without any setup.
    """
    root = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppDataLocation
    )
    return str(Path(root) / "scratch")


def load_scratch_dir() -> str:
    """Return the persisted scratch folder, or :func:`default_scratch_dir` if unset."""
    raw = _settings().value(_SCRATCH_DIR_KEY, "")
    return str(raw) if raw else default_scratch_dir()


def save_scratch_dir(path: str) -> None:
    """Persist the scratch folder (Settings ▸ Scratch folder) to restore on next launch."""
    _settings().setValue(_SCRATCH_DIR_KEY, path)


def load_auto_add_deps(default: bool) -> bool:
    """Whether saving / promoting an artifact into a phase also pulls its dependencies (B10h-1b).

    Persisted as a bool, but IniFormat round-trips it as a string, so parse defensively.
    """
    raw = _settings().value(_AUTO_ADD_DEPS_KEY, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def save_auto_add_deps(value: bool) -> None:
    """Persist the auto-add-dependencies toggle (Settings) to restore on next launch."""
    _settings().setValue(_AUTO_ADD_DEPS_KEY, value)


def load_cache_ceiling_mb(default: int) -> int:
    """Return the persisted view-model cache ceiling (MB, Block 11), or ``default``.

    The in-RAM hot tier of the view-model cache is bounded by this; the shell converts
    it to bytes for the ``FrameStore``. Parsed defensively (IniFormat stores as a string)
    and floored at 1 MB — a non-positive / unparseable value falls back to ``default``.
    """
    raw = _settings().value(_CACHE_CEILING_KEY, default)
    try:
        value = int(float(str(raw)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def save_cache_ceiling_mb(value: int) -> None:
    """Persist the view-model cache ceiling in MB (Settings) to restore on next launch."""
    _settings().setValue(_CACHE_CEILING_KEY, int(value))
