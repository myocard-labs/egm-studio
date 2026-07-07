"""``preview_png(spec, *, data) -> bytes`` — an in-memory raster of a figure spec.

The GUI twin of :func:`figures.render.render` (Block 9, Flow C). Where ``render``
writes a vector file to disk, ``preview_png`` rasterizes the *same* figure to a PNG
in memory for the live preview panel — routed through the shared
:func:`figures.render.draw_figure`, and serialized through the *same* ``savefig`` +
``paper_style`` pipeline the export uses. So the preview the user tunes against is
pixel-faithful to the PDF they will export (only raster-vs-vector + the preview DPI
differ); the ``paper_style`` ``bbox="tight"`` even matches the export's framing.

Kept out of the Qt layer on purpose: this is headless matplotlib (Agg), importable in
notebooks + tests without a display. The widget side (``gui/widgets/figure_preview``)
just turns the returned bytes into a ``QPixmap``. [ADR-005, ADR-019]
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt

from myocard_egm_studio.charts.matplotlib.style import paper_style
from myocard_egm_studio.figures.render import draw_figure

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: On-screen preview raster density. Lower than the export's 300 (PAPER_RCPARAMS
#: ``savefig.dpi``) — the preview is scaled to fit a panel, so 150 is crisp enough
#: and keeps each re-render quick. Fidelity comes from ``paper_style`` (layout +
#: sizes + tight bbox), not the DPI.
PREVIEW_DPI = 150

__all__ = ["PREVIEW_DPI", "preview_png"]


def preview_png(spec: FigureSpec, *, data: Any, dpi: int = PREVIEW_DPI) -> bytes:
    """Render ``spec`` to PNG bytes in memory (the live-preview raster).

    Parameters
    ----------
    spec
        A validated :class:`FigureSpec` (same input as :func:`render`).
    data
        The recipe's prepared input (see ``charts/matplotlib/inputs``); resolve it
        from the spec's bank ids via ``loaders.resolve_recipe_data``.
    dpi
        Raster density; defaults to :data:`PREVIEW_DPI`.

    Raises
    ------
    UnknownRecipeError
        If ``spec.recipe`` is not registered.
    FigureDataNotLoadedError
        If ``data`` is ``None``.
    """
    figure = draw_figure(spec, data)
    buffer = io.BytesIO()
    try:
        with paper_style():
            figure.savefig(buffer, format="png", dpi=dpi)
    finally:
        plt.close(figure)  # recipes build via pyplot — close so previews don't leak figures
    return buffer.getvalue()
