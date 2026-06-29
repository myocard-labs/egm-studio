"""``render(spec) -> Path`` — dispatch a FigureSpec to its matplotlib recipe.

The keystone of the headless path: look up ``spec.recipe`` in the
``charts/matplotlib`` registry, call it to get a ``Figure``, write the file at
``spec.output.path`` (or an override), return the path. The drawing lives in
``charts/``; the data prep in ``analysis/``; this module is just the wiring.

Block 2 ships the dispatch + the clear empty-registry error. Block 3 registers
the P0 recipes and wires the data-loading step (resolving ``inputs.groups``
bank ids), which may add a loaded-data argument to the recipe call — that
refinement lands with the recipes.

Import boundary: matplotlib is reached only *through* a registered recipe (the
``Figure`` it returns), never imported here, and PySide6 / pyqtgraph never at
all — so this runs in CI + notebooks without a display. [ADR-005, architecture.md]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from myocard_egm_studio.charts.matplotlib import RECIPES

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

__all__ = [
    "UnknownRecipeError",
    "render",
]


class UnknownRecipeError(LookupError):
    """A FigureSpec named a recipe egm-studio has not registered.

    Carries the offending ``recipe`` name and the sorted list of ``known``
    recipes so the CLI can print an actionable message. Subclasses
    :class:`LookupError` (not :class:`KeyError`) so ``str(exc)`` stays clean.
    """

    def __init__(self, recipe: str, known: list[str]) -> None:
        self.recipe = recipe
        self.known = known
        hint = (
            "known recipes: " + ", ".join(known)
            if known
            else "no recipes are registered yet (Block 3 adds the P0 recipes)"
        )
        super().__init__(f"unknown figure recipe {recipe!r}; {hint}.")


def render(spec: FigureSpec, *, output_path: Path | str | None = None) -> Path:
    """Render ``spec`` to disk and return the output :class:`~pathlib.Path`.

    Parameters
    ----------
    spec
        A validated :class:`FigureSpec` (load it via
        ``myocard_egm_data.phases.load_figure_spec`` per ADR-001).
    output_path
        Optional override for ``spec.output.path`` (the CLI's ``-o`` flag).

    Raises
    ------
    UnknownRecipeError
        If ``spec.recipe`` is not in the matplotlib recipe registry. At Block 2
        the registry is empty, so this always raises — the plumbing is in
        place for Block 3 to fill.
    """
    recipe = RECIPES.get(spec.recipe)
    if recipe is None:
        raise UnknownRecipeError(spec.recipe, sorted(RECIPES))

    figure = recipe(spec)
    path = Path(output_path) if output_path is not None else Path(spec.output.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format=spec.output.format.value)
    return path
