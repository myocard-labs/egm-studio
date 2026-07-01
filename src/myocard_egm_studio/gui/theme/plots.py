"""Theme-derived colours for the pyqtgraph plots (ADR-012).

The QSS themes style the shell chrome, but pyqtgraph plots aren't QSS-styled, so
they read their colours from the same :class:`~.palette.Palette` here.
:func:`plot_palette` maps a theme to the few colours a trace plot needs; the trace
widgets apply it and restyle on theme change.
"""

from __future__ import annotations

from dataclasses import dataclass

from myocard_egm_studio.gui.theme.palette import PALETTES, ThemeName


@dataclass(frozen=True)
class PlotPalette:
    """The colours a pyqtgraph trace plot needs, derived from a theme Palette."""

    background: str  # plot area (the GraphicsLayoutWidget background)
    foreground: str  # axes, ticks, tick labels, plot title
    trace: str  # the signal pen


def plot_palette(theme: ThemeName) -> PlotPalette:
    """Map a theme to its pyqtgraph plot colours (trace = the theme accent)."""
    p = PALETTES[theme]
    return PlotPalette(background=p.surface, foreground=p.text_muted, trace=p.accent)
