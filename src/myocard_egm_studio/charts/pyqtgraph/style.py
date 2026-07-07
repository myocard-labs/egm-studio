"""Colours for the pyqtgraph chart backend (the GUI-embedded twin of
``charts/matplotlib/style``).

Group / series colours are the shared Okabe-Ito palette (``charts.palette``), so a
pyqtgraph chart matches its matplotlib figure. Background + foreground are supplied
per display context: the default is paper-like (white) for parity with the
exported figure; the GUI passes its theme colours when embedding a chart live.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PgChartStyle:
    """The background + foreground a pyqtgraph chart needs (group colours are the
    shared Okabe-Ito palette from :mod:`charts.palette`)."""

    background: str = "#ffffff"  # paper-like default (parity with the matplotlib figure)
    foreground: str = "#333333"


#: Paper-like default — used standalone / for the matplotlib-equivalence check.
DEFAULT_STYLE = PgChartStyle()
