"""Unit tests for figures.preview — the in-memory PNG raster of a figure spec (B9)."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib import RECIPES
from myocard_egm_studio.figures import (
    FigureDataNotLoadedError,
    UnknownRecipeError,
    draw_figure,
    preview_png,
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_STUB_DATA = object()


def _spec(*, recipe: str) -> FigureSpec:
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_test_preview",
            "description": "preview raster test spec",
            "recipe": recipe,
            "output": {"format": "pdf", "path": "out/fig.pdf"},
        }
    )


def _stub_recipe(data: object, spec: FigureSpec) -> Figure:
    fig = Figure()
    FigureCanvasAgg(fig)
    fig.add_subplot(1, 1, 1).plot([0, 1, 2], [0, 1, 0])
    return fig


@pytest.fixture
def registered_stub() -> Iterator[str]:
    name = "stub-preview-recipe"
    RECIPES[name] = _stub_recipe
    try:
        yield name
    finally:
        RECIPES.pop(name, None)


def test_preview_png_returns_a_valid_png(registered_stub: str) -> None:
    """preview_png rasterizes the recipe to decodable PNG bytes (no file touched)."""
    data = preview_png(_spec(recipe=registered_stub), data=_STUB_DATA)
    assert data[:8] == _PNG_SIGNATURE
    from matplotlib import image as mimage

    array = mimage.imread(io.BytesIO(data), format="png")
    assert array.shape[0] > 0 and array.shape[1] > 0  # a real, non-empty raster


def test_preview_png_honours_dpi(registered_stub: str) -> None:
    """A higher DPI yields a larger raster (same figure, denser pixels)."""
    from matplotlib import image as mimage

    small = mimage.imread(
        io.BytesIO(preview_png(_spec(recipe=registered_stub), data=_STUB_DATA, dpi=75))
    )
    large = mimage.imread(
        io.BytesIO(preview_png(_spec(recipe=registered_stub), data=_STUB_DATA, dpi=200))
    )
    assert large.shape[0] > small.shape[0]


def test_preview_png_unknown_recipe_raises() -> None:
    """An unregistered recipe raises UnknownRecipeError (same lookup as render)."""
    with pytest.raises(UnknownRecipeError) as excinfo:
        preview_png(_spec(recipe="definitely-not-a-recipe"), data=_STUB_DATA)
    assert excinfo.value.recipe == "definitely-not-a-recipe"


def test_preview_png_missing_data_raises(registered_stub: str) -> None:
    """data=None raises FigureDataNotLoadedError — the preview needs prepared data too."""
    with pytest.raises(FigureDataNotLoadedError):
        preview_png(_spec(recipe=registered_stub), data=None)


def test_draw_figure_returns_the_recipe_figure(registered_stub: str) -> None:
    """draw_figure is the shared recipe invocation both render + preview route through."""
    figure = draw_figure(_spec(recipe=registered_stub), _STUB_DATA)
    assert isinstance(figure, Figure)
