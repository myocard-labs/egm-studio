"""Shared chart palette — the group / series colours both backends use.

Framework-free (no matplotlib, no pyqtgraph) so ``charts/matplotlib`` and
``charts/pyqtgraph`` import the *same* Okabe-Ito colours; that shared palette is
what makes a pyqtgraph chart match its matplotlib twin. Kept at the ``charts/``
level, below both backends, per the three-layer split.
"""

from __future__ import annotations

__all__ = ["OKABE_ITO", "color_for"]

#: Okabe-Ito colour-blind-safe qualitative palette (Okabe & Ito 2008). The order
#: is the project-standard group / series cycle; recipes index into it by group.
OKABE_ITO: tuple[str, ...] = (
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
    "#000000",  # black
)


def color_for(index: int) -> str:
    """The :data:`OKABE_ITO` colour for series / group ``index`` (cycles, wraps).

    The project-standard way recipes pick a per-series colour, so the palette
    indexing lives in one place rather than each recipe repeating
    ``OKABE_ITO[i % len(OKABE_ITO)]``.
    """
    return OKABE_ITO[index % len(OKABE_ITO)]
