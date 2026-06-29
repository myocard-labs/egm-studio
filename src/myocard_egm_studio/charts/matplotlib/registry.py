"""Recipe registry for the matplotlib backend.

A *recipe* is a callable keyed by a ``figure_spec.recipe`` string that draws one
figure from its prepared ``data`` + the ``spec`` and returns a
``matplotlib.figure.Figure``. Recipes register themselves via :func:`register`
(the per-recipe modules are imported for side effect by the package
``__init__``); the headless :func:`...figures.render.render` dispatches through
:data:`RECIPES`.

Recipes take ``(data, spec)`` — pure plotting, no I/O. ``data`` is a
recipe-specific prepared input (``charts/matplotlib/inputs``); the renderer's
loading step (Block 7) builds it from a spec's bank ids, and tests build it in
memory.

The registry lives in its own module (not the package ``__init__``) so the
recipe modules can ``from .registry import register`` without importing the
``__init__`` that imports them — no circular import.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: A figure recipe: prepared ``data`` + the ``spec`` -> Figure.
RecipeFn = Callable[[Any, "FigureSpec"], "Figure"]

#: Recipe name (the ``figure_spec.recipe`` value) -> recipe function.
RECIPES: dict[str, RecipeFn] = {}

__all__ = ["RECIPES", "RecipeFn", "register"]


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
