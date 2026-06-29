"""Publication figure styling — rcParams + palette for the matplotlib backend.

Two pieces both render paths share:

- :data:`PAPER_RCPARAMS` + :func:`paper_style` — matplotlib rcParams for
  journal-ready vector output: TrueType-embedded text in PDF/PS
  (``pdf.fonttype = 42``) and editable text in SVG (``svg.fonttype = "none"``),
  plus modest default sizes and de-cluttered spines. `paper_style()` is an
  ``rc_context`` manager, so the settings are *scoped* — never a process-global
  mutation that would leak into the GUI's Qt-embedded matplotlib canvas.
- :data:`OKABE_ITO` — the Okabe-Ito color-blind-safe qualitative palette
  (Okabe & Ito 2008), the project-standard group/series colors per ADR-012's
  paper-palette follow-up.

Recipes build their figure inside ``with paper_style():`` so the colors + sizes
bake into the artists; the headless renderer also wraps ``savefig`` in it so the
font-embedding rcParams apply at write time.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import matplotlib as mpl

__all__ = ["OKABE_ITO", "PAPER_RCPARAMS", "color_for", "paper_style"]

#: Okabe-Ito color-blind-safe qualitative palette (8 colors). The order is the
#: project-standard group/series cycle; recipes index into it by group.
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

#: rcParams for journal-ready figures. The font-embedding entries are the
#: load-bearing bit: pdf/ps fonttype 42 embeds TrueType (selectable, scalable
#: text in the compiled paper), and svg.fonttype "none" keeps SVG text as text
#: rather than outlined paths.
PAPER_RCPARAMS: dict[str, object] = {
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
}


def color_for(index: int) -> str:
    """The :data:`OKABE_ITO` color for series/group ``index`` (cycles, wraps).

    The project-standard way recipes pick a per-series color, so the palette
    indexing lives in one place across recipes rather than each repeating
    ``OKABE_ITO[i % len(OKABE_ITO)]``.
    """
    return OKABE_ITO[index % len(OKABE_ITO)]


@contextmanager
def paper_style() -> Iterator[None]:
    """Scoped ``rc_context`` applying :data:`PAPER_RCPARAMS`.

    Wrap figure construction in it (so the sizes / spines bake into the
    artists) and wrap ``savefig`` in it (so the font-embedding rcParams apply at
    write time). Scoped — never mutates the process-global rcParams.
    """
    # matplotlib >=3.8 ships py.typed; rc_context types its arg with a giant
    # Literal-keyed dict. We hold rcParams as a plain str->value mapping, so
    # cast at the boundary rather than enumerate every rcParam key.
    with mpl.rc_context(cast("dict[Any, Any]", PAPER_RCPARAMS)):
        yield
