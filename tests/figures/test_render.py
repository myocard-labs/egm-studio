"""Unit tests for figures.render dispatch + the charts.matplotlib registry."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib import RECIPES, register
from myocard_egm_studio.figures import (
    FigureDataNotLoadedError,
    UnknownRecipeError,
    render,
)

#: Sentinel passed as a recipe's prepared ``data``; the stub recipe ignores it.
_STUB_DATA = object()


def _spec(*, recipe: str, fmt: str = "png", path: str = "out.png") -> FigureSpec:
    """Build a minimal valid FigureSpec naming ``recipe`` (PNG so Agg renders it
    natively, no backend switch)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_test_render",
            "description": "render dispatch test spec",
            "recipe": recipe,
            "output": {"format": fmt, "path": path},
        }
    )


def _stub_recipe(data: object, spec: FigureSpec) -> Figure:
    """A throwaway recipe returning a real (Agg-backed) Figure for save tests.

    Takes the ``(data, spec)`` recipe signature and ignores ``data`` — these
    tests exercise the dispatch + save path, not the drawing."""
    fig = Figure()
    FigureCanvasAgg(fig)
    fig.add_subplot(1, 1, 1).plot([0, 1, 2], [0, 1, 0])
    return fig


@pytest.fixture
def registered_stub() -> Iterator[str]:
    """Register ``_stub_recipe`` under a unique name; clean up afterwards so the
    registry is left as the import-time set of real recipes."""
    name = "stub-test-recipe"
    RECIPES[name] = _stub_recipe
    try:
        yield name
    finally:
        RECIPES.pop(name, None)


def test_unknown_recipe_raises() -> None:
    """render() raises UnknownRecipeError naming the offending recipe and listing
    the registered recipes — recipe lookup happens before the data check."""
    with pytest.raises(UnknownRecipeError) as excinfo:
        render(_spec(recipe="definitely-not-a-recipe"), data=_STUB_DATA)
    assert excinfo.value.recipe == "definitely-not-a-recipe"
    assert "known recipes" in str(excinfo.value)


def test_missing_data_raises_not_loaded(registered_stub: str) -> None:
    """A registered recipe with ``data=None`` raises FigureDataNotLoadedError —
    spec-driven data loading lands in Block 7; until then callers pass data=."""
    with pytest.raises(FigureDataNotLoadedError) as excinfo:
        render(_spec(recipe=registered_stub))
    assert excinfo.value.recipe == registered_stub
    assert "Block 7" in str(excinfo.value)


def test_dispatches_to_registered_recipe(tmp_path: Path, registered_stub: str) -> None:
    """A registered recipe is invoked with the passed data and its Figure written
    to the spec's output path; render returns that path and the file exists."""
    out = tmp_path / "fig.png"
    result = render(_spec(recipe=registered_stub, path=str(out)), data=_STUB_DATA)
    assert result == out
    assert out.exists()


def test_output_path_override(tmp_path: Path, registered_stub: str) -> None:
    """The ``output_path`` argument (the CLI's -o flag) overrides the spec's
    own ``output.path``."""
    out = tmp_path / "override.png"
    result = render(
        _spec(recipe=registered_stub, path="ignored.png"),
        data=_STUB_DATA,
        output_path=out,
    )
    assert result == out
    assert out.exists()


def test_render_creates_missing_parent_dirs(tmp_path: Path, registered_stub: str) -> None:
    """render creates any missing parent directories of the output path rather
    than failing on a not-yet-existing folder."""
    out = tmp_path / "nested" / "deeper" / "fig.png"
    render(_spec(recipe=registered_stub, path=str(out)), data=_STUB_DATA)
    assert out.exists()


def test_register_rejects_duplicate() -> None:
    """register() refuses to bind two recipes to the same name — a duplicate is
    a programming error, not a silent overwrite."""
    name = "dup-test-recipe"
    try:
        register(name)(_stub_recipe)
        with pytest.raises(ValueError, match="already registered"):
            register(name)(_stub_recipe)
    finally:
        RECIPES.pop(name, None)


def test_render_refuses_existing_output(tmp_path: Path, registered_stub: str) -> None:
    """render refuses to clobber an existing output (FileExistsError) and does
    not call the recipe — the existence check happens before drawing."""
    out = tmp_path / "fig.png"
    out.write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="already exists"):
        render(_spec(recipe=registered_stub, path=str(out)), data=_STUB_DATA)
    assert out.read_bytes() == b"existing"  # untouched


def test_render_overwrite_replaces_existing(tmp_path: Path, registered_stub: str) -> None:
    """overwrite=True lets render replace an existing output."""
    out = tmp_path / "fig.png"
    out.write_bytes(b"existing")
    render(_spec(recipe=registered_stub, path=str(out)), data=_STUB_DATA, overwrite=True)
    assert out.read_bytes() != b"existing"  # a real PNG now
