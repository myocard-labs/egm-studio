"""Dark / light / vibrant theming for the egm-studio shell (ADR-012).

Dark is the default; light and vibrant ship as ``View > Theme`` alternatives, and
the chosen theme is remembered across launches (see :mod:`..preferences`). A theme
is a :class:`~.palette.Palette` of colour + size tokens substituted into one
shared QSS template (:mod:`._qss`), so the themes never drift structurally — only
their palettes differ. :func:`apply_theme` swaps the whole application's
stylesheet in one call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from myocard_egm_studio.gui.theme._qss import build_stylesheet
from myocard_egm_studio.gui.theme.palette import PALETTES, ThemeName
from myocard_egm_studio.gui.theme.plots import PlotPalette, chart_style, plot_palette

if TYPE_CHECKING:
    from PySide6 import QtWidgets

#: Theme applied on first launch, before any user preference is saved (ADR-012).
DEFAULT_THEME: ThemeName = "dark"
#: Toggle order in the View > Theme menu.
THEME_NAMES: tuple[ThemeName, ...] = ("dark", "light", "vibrant")


def apply_theme(app: QtWidgets.QApplication, name: ThemeName) -> None:
    """Set ``app``'s stylesheet to the built QSS for the named theme."""
    app.setStyleSheet(build_stylesheet(PALETTES[name]))


__all__ = [
    "DEFAULT_THEME",
    "THEME_NAMES",
    "PlotPalette",
    "ThemeName",
    "apply_theme",
    "build_stylesheet",
    "chart_style",
    "plot_palette",
]
