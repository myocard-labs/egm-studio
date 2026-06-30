"""Tests for the ``trace-pair-gallery`` matplotlib recipe.

A snapshot (a 3-row Nx2 gallery) plus logic over an in-memory TracePairGallery.
The similarity matching + raw-signal extraction live in the loader (tested in
tests/figures/test_loaders.py); here we check the recipe's grid layout, column
titles, and per-row annotations.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.inputs import TracePair, TracePairGallery
from myocard_egm_studio.charts.matplotlib.trace_pair_gallery import trace_pair_gallery

_TOL = 20.0


def _spec() -> FigureSpec:
    """Minimal valid trace-pair-gallery FigureSpec (the recipe is data-driven)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_trace_pair_gallery_test",
            "description": "trace-pair-gallery recipe test spec",
            "recipe": "trace-pair-gallery",
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _gallery(n: int = 3, *, seed: int = 0) -> TracePairGallery:
    """An N-row gallery of synthetic damped-sinusoid waveform pairs."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, 1.0, 200)
    pairs: list[TracePair] = []
    for r in range(n):
        wave = np.exp(-3.0 * t) * np.sin(2 * np.pi * (5 + r) * t)
        left = (wave + 0.05 * rng.standard_normal(t.size)).astype(np.float64)
        right = (wave + 0.05 * rng.standard_normal(t.size)).astype(np.float64)
        pairs.append(TracePair(left=left, right=right, annotation=f"feat {r}.0"))
    return TracePairGallery(
        pairs=pairs,
        left_title="Synthetic",
        right_title="IAFDB",
        left_fs_hz=1000.0,
        right_fs_hz=1000.0,
    )


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_three_row_gallery() -> Figure:
    """A 3x2 gallery of paired traces — the F-1.5.7 shape."""
    return trace_pair_gallery(_gallery(3), _spec())


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def test_grid_shape_is_n_by_2() -> None:
    """N pairs -> an Nx2 grid = 2N axes."""
    fig = trace_pair_gallery(_gallery(4), _spec())
    assert len(fig.axes) == 8


def test_single_pair_still_indexes_grid() -> None:
    """n == 1 still works (squeeze=False keeps the axes 2-D)."""
    fig = trace_pair_gallery(_gallery(1), _spec())
    assert len(fig.axes) == 2


def test_column_titles_on_top_row() -> None:
    """The top-row panels carry the source / pool column titles."""
    fig = trace_pair_gallery(_gallery(2), _spec())
    assert {"Synthetic", "IAFDB"} <= {ax.get_title() for ax in fig.axes}


def test_row_annotations_present() -> None:
    """Each row's left panel carries its annotation text."""
    fig = trace_pair_gallery(_gallery(3), _spec())
    texts = {t.get_text() for ax in fig.axes for t in ax.texts}
    assert {"feat 0.0", "feat 1.0", "feat 2.0"} <= texts


def test_empty_raises() -> None:
    """A gallery with no pairs is a caller error."""
    with pytest.raises(ValueError, match="at least one TracePair"):
        trace_pair_gallery(TracePairGallery(pairs=[]), _spec())
