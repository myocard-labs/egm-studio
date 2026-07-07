"""Headless figure-render layer — the thin dispatch over ``charts/matplotlib``.

``render(spec, *, data)`` is the single public entry point (importable from
notebooks / CI, and wrapped by the ``egm-studio-render`` CLI and — later — the
GUI's figure-prep view). It looks up the spec's recipe, draws it from the
prepared ``data``, and writes the file. No PySide6, no pyqtgraph: this path
runs without a display. [ADR-005, ADR-015, architecture.md "The three-layer
rendering split"]

Turning a spec's bank ids into that prepared ``data`` is the *loading step* — it
lives in the top-level :mod:`myocard_egm_studio.loaders` package
(``resolve_recipe_data`` + the phase-manifest resolver), so ``figures/`` stays
pure rendering.
"""

from __future__ import annotations

from myocard_egm_studio.figures.preview import PREVIEW_DPI, preview_png
from myocard_egm_studio.figures.render import (
    FigureDataNotLoadedError,
    UnknownRecipeError,
    draw_figure,
    render,
)

__all__ = [
    "PREVIEW_DPI",
    "FigureDataNotLoadedError",
    "UnknownRecipeError",
    "draw_figure",
    "preview_png",
    "render",
]
