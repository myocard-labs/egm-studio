"""matplotlib rendering backend — publication-quality static figures.

Home of the recipe registry that :func:`..figures.render.render` dispatches
into. A *recipe* is a callable keyed by a ``figure_spec.recipe`` string that
draws one figure and returns a ``matplotlib.figure.Figure``. Block 2 ships the
empty registry + the :func:`register` decorator; Block 3 fills it with the 8 P0
recipes from ``project/paper_figure_inventory.md`` (``prediction-histogram``,
``feature-distribution-overlay``, ...).

Import rule: this backend imports matplotlib (Agg backend, headless) but never
PySide6 or pyqtgraph — the interactive variants live in ``charts/pyqtgraph/``.
[architecture.md "Import boundaries", ADR-005]

The recipe signature is provisional at Block 2 (``recipe(spec) -> Figure``).
Block 3 wires the data-loading path (resolving ``inputs.groups`` bank ids
through the loaders) and may extend recipes to receive the loaded view-models
alongside the spec; that refinement is expected and tracked for the Block 11
doc sweep.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: A figure recipe: draws one figure from a typed spec, returns the Figure.
RecipeFn = Callable[["FigureSpec"], "Figure"]

#: Recipe name (the ``figure_spec.recipe`` value) -> recipe function.
#: Empty at Block 2; populated by Block 3 via :func:`register`.
RECIPES: dict[str, RecipeFn] = {}

__all__ = [
    "RECIPES",
    "RecipeFn",
    "register",
]


def register(name: str) -> Callable[[RecipeFn], RecipeFn]:
    """Decorator registering a matplotlib recipe under ``name``.

    ``name`` is the ``figure_spec.recipe`` value the recipe handles. Raises
    :class:`ValueError` on a duplicate registration so two recipes can't
    silently claim the same name.
    """

    def _decorator(fn: RecipeFn) -> RecipeFn:
        if name in RECIPES:
            raise ValueError(f"matplotlib recipe {name!r} is already registered.")
        RECIPES[name] = fn
        return fn

    return _decorator
