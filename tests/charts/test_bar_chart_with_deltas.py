"""Tests for the ``bar-chart-with-deltas`` matplotlib recipe.

A snapshot (bars + baseline reference line + delta annotations) plus logic tests
over small in-memory BarChartData — no baseline image needed for the latter.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.inputs import BarChartData
from myocard_egm_studio.charts.matplotlib.bar_chart_with_deltas import bar_chart_with_deltas

_TOL = 20.0


def _spec() -> FigureSpec:
    """Minimal valid bar-chart-with-deltas FigureSpec (the recipe is data-driven)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_bar_chart_test",
            "description": "bar-chart-with-deltas recipe test spec",
            "recipe": "bar-chart-with-deltas",
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _bar_data(*, baseline: str | None = None, errors: np.ndarray | None = None) -> BarChartData:
    categories = ["clean", "+noise", "density-lo", "density-hi"]
    values = np.array([0.30, 0.18, 0.25, 0.22], dtype=np.float64)
    baseline_index = categories.index(baseline) if baseline is not None else None
    return BarChartData(
        categories=categories,
        values=values,
        errors=errors,
        baseline_index=baseline_index,
        value_label="mean KS distance to IAFDB",
    )


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_bars_with_baseline_deltas() -> Figure:
    """Bars + baseline reference line + signed per-bar deltas — the F-1.5.3 shape."""
    return bar_chart_with_deltas(_bar_data(baseline="clean"), _spec())


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def test_one_bar_per_category() -> None:
    """One bar (Rectangle patch) is drawn per category."""
    fig = bar_chart_with_deltas(_bar_data(), _spec())
    assert len(fig.axes[0].patches) == 4


def test_empty_categories_raises() -> None:
    """No categories is a caller error."""
    with pytest.raises(ValueError, match="at least one category"):
        bar_chart_with_deltas(BarChartData(categories=[], values=np.array([])), _spec())


def test_values_shape_mismatch_raises() -> None:
    """values must align one-to-one with categories."""
    with pytest.raises(ValueError, match="does not match"):
        bar_chart_with_deltas(BarChartData(categories=["a", "b"], values=np.array([1.0])), _spec())


def test_errors_shape_mismatch_raises() -> None:
    """errors, when given, must align with values."""
    with pytest.raises(ValueError, match="errors must align"):
        bar_chart_with_deltas(
            BarChartData(
                categories=["a", "b"], values=np.array([1.0, 2.0]), errors=np.array([0.1])
            ),
            _spec(),
        )


def test_baseline_index_out_of_range_raises() -> None:
    """A baseline_index past the category count is rejected."""
    with pytest.raises(ValueError, match="out of range"):
        bar_chart_with_deltas(
            BarChartData(categories=["a"], values=np.array([1.0]), baseline_index=3), _spec()
        )


def test_baseline_deltas_annotated() -> None:
    """With a baseline, the baseline bar is labeled and the rest carry signed deltas."""
    fig = bar_chart_with_deltas(_bar_data(baseline="clean"), _spec())
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert "baseline" in texts
    assert any(t.startswith(("+", "-")) for t in texts)  # signed deltas like "-0.12"


def test_no_baseline_means_no_delta_text() -> None:
    """Without a baseline, no baseline/delta annotations are drawn."""
    fig = bar_chart_with_deltas(_bar_data(baseline=None), _spec())
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert "baseline" not in texts
