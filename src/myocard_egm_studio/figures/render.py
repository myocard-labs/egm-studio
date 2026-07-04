"""``render(spec, *, data) -> Path`` — dispatch a FigureSpec to its recipe.

The keystone of the headless path: look up ``spec.recipe`` in the
``charts/matplotlib`` registry, call it with the prepared ``data`` to get a
``Figure``, write the file at ``spec.output.path`` (or an override) under the
paper style, return the path. The drawing lives in ``charts/``; the data prep
in ``analysis/``; this module is just the wiring.

``data`` is the recipe's prepared input (see ``charts/matplotlib/inputs``).
``data=None`` means "load it from the spec" — turning ``spec.inputs.groups``
bank ids into recipe data is the renderer's loading step, which lands with the
egm-data bank loaders in Block 7. Until then ``render`` with ``data=None``
raises :class:`FigureDataNotLoadedError`; callers pass ``data=`` explicitly
(the snapshot tests + notebook callers do).

Import boundary: matplotlib is reached only *through* a registered recipe (the
``Figure`` it returns) plus the shared style context, never PySide6 / pyqtgraph
— so this runs in CI + notebooks without a display. [ADR-005, architecture.md]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from myocard_egm_studio.charts.matplotlib import RECIPES
from myocard_egm_studio.charts.matplotlib.style import paper_style

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

    from myocard_egm_studio.charts.matplotlib.registry import RecipeFn

__all__ = [
    "FigureDataNotLoadedError",
    "UnknownRecipeError",
    "draw_figure",
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
        hint = "known recipes: " + ", ".join(known) if known else "no recipes are registered"
        super().__init__(f"unknown figure recipe {recipe!r}; {hint}.")


class FigureDataNotLoadedError(NotImplementedError):
    """``render`` was asked to load a spec's data, which isn't wired yet.

    Resolving a spec's ``inputs.groups`` bank ids into recipe data goes through
    the egm-data bank loaders + the phase manifest, both scheduled for Blocks
    6-7. Until then, build the recipe's data and pass it as
    ``render(spec, data=...)`` (the snapshot tests + notebook callers do).
    """

    def __init__(self, recipe: str) -> None:
        self.recipe = recipe
        super().__init__(
            f"render() can't yet load data for recipe {recipe!r} from a spec — "
            "spec data loading (bank_id -> bank) lands with the egm-data "
            "loaders in Block 7. Pass data= explicitly for now."
        )


def _recipe_for(spec: FigureSpec, data: Any) -> RecipeFn:
    """Validate + return the registered recipe for ``spec`` (shared lookup).

    Raises :class:`UnknownRecipeError` if the recipe isn't registered, or
    :class:`FigureDataNotLoadedError` if ``data`` is ``None`` — in that order, so a
    caller learns about a bad recipe before an unresolved data reference regardless
    of any later output guard.
    """
    recipe = RECIPES.get(spec.recipe)
    if recipe is None:
        raise UnknownRecipeError(spec.recipe, sorted(RECIPES))
    if data is None:
        raise FigureDataNotLoadedError(spec.recipe)
    return recipe


def draw_figure(spec: FigureSpec, data: Any) -> Figure:
    """Look up ``spec.recipe`` and draw the (styled) :class:`~matplotlib.figure.Figure`.

    The single recipe invocation both output paths share: :func:`render` (disk) and
    the GUI preview (:func:`figures.preview.preview_png`, Block 9). A recipe wraps its
    own drawing in ``paper_style()``, so the returned figure is already journal-styled;
    the caller decides how to serialize it (``savefig`` to a file, or to an in-memory
    PNG for the preview). Routing both through here guarantees the preview draws the
    *exact* figure the export writes.

    Raises :class:`UnknownRecipeError` / :class:`FigureDataNotLoadedError` (see
    :func:`_recipe_for`).
    """
    figure: Figure = _recipe_for(spec, data)(data, spec)
    return figure


def render(
    spec: FigureSpec,
    *,
    data: Any = None,
    output_path: Path | str | None = None,
    overwrite: bool = False,
) -> Path:
    """Render ``spec`` to disk and return the output :class:`~pathlib.Path`.

    Parameters
    ----------
    spec
        A validated :class:`FigureSpec` (load it via
        ``myocard_egm_data.phases.load_figure_spec`` per ADR-001).
    data
        The recipe's prepared input (see ``charts/matplotlib/inputs``). When
        ``None``, ``render`` would load it from ``spec`` — not wired until
        Block 7, so it raises :class:`FigureDataNotLoadedError`.
    output_path
        Optional override for ``spec.output.path`` (the CLI's ``-o`` flag).
    overwrite
        If False (default) and the resolved output path already exists, raise
        :class:`FileExistsError` *before* drawing, so a good figure isn't
        silently clobbered. (The CLI surfaces this as ``--overwrite`` and skips
        even earlier — before loading any data.)

    Raises
    ------
    UnknownRecipeError
        If ``spec.recipe`` is not in the matplotlib recipe registry.
    FigureDataNotLoadedError
        If ``data`` is ``None`` (spec-driven data loading lands in Block 7).
    FileExistsError
        If the resolved output path exists and ``overwrite`` is False.
    """
    # Validate the recipe + data first (Unknown/DataNotLoaded), then guard the output
    # *before* drawing so an existing file isn't silently clobbered and no work is
    # wasted, then draw + write.
    recipe = _recipe_for(spec, data)

    path = Path(output_path) if output_path is not None else Path(spec.output.path)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} already exists; pass overwrite=True (CLI: --overwrite) to replace."
        )

    figure = recipe(data, spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with paper_style():
        figure.savefig(path, format=spec.output.format.value)
    return path
