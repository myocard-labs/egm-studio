"""Headless figure-render layer — the thin dispatch over ``charts/matplotlib``.

``render(spec)`` is the single public entry point (importable from notebooks /
CI, and wrapped by the ``egm-studio-render`` CLI and — later — the GUI's
figure-prep view). It looks up the spec's recipe, draws it, and writes the
file. No PySide6, no pyqtgraph: this path runs without a display. [ADR-005,
ADR-015, architecture.md "The three-layer rendering split"]
"""

from __future__ import annotations

from myocard_egm_studio.figures.render import UnknownRecipeError, render

__all__ = [
    "UnknownRecipeError",
    "render",
]
