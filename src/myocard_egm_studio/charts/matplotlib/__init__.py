"""matplotlib rendering backend — publication-quality static figures.

The recipe registry (:mod:`.registry`) plus the per-recipe modules. Importing
this package runs each recipe module's :func:`.registry.register` decorator, so
:data:`.registry.RECIPES` is populated by the time
:func:`..figures.render.render` dispatches into it. Block 3 fills the registry
with the P0 recipes from ``project/paper_figure_inventory.md``
(``prediction-histogram`` first; the rest follow once the pattern is reviewed).

Import rule: this backend imports matplotlib (Agg backend, headless) but never
PySide6 or pyqtgraph — the interactive variants live in ``charts/pyqtgraph/``.
[architecture.md "Import boundaries", ADR-005]

Recipes take ``(data, spec)`` and return a Figure — pure plotting, no I/O.
``data`` is a recipe-specific prepared input (see ``charts/matplotlib/inputs``);
the renderer's loading step (Block 7) turns a spec's ``inputs.groups`` bank ids
into it, and tests build it in memory. Recipes draw inside
``style.paper_style()`` so the journal palette + sizes bake into the figure.
"""

from __future__ import annotations

# Recipe modules: imported for the side effect of running their @register
# decorators (populates RECIPES). F401 is per-file-ignored for __init__.
from myocard_egm_studio.charts.matplotlib import prediction_histogram
from myocard_egm_studio.charts.matplotlib.registry import RECIPES, RecipeFn, register

__all__ = [
    "RECIPES",
    "RecipeFn",
    "prediction_histogram",
    "register",
]
