"""Tests for the ``prediction-histogram`` matplotlib recipe.

Two kinds of test:

- ``mpl_image_compare`` snapshots — pixel-compare the rendered figure against a
  baseline PNG. Baselines are generated locally and are *git-ignored*
  (``tests/charts/baseline/``), not committed — they only *compare* under
  ``pytest --mpl`` (the developer's visual-regression run, after regenerating
  them locally), while a plain ``pytest`` (CI) just executes them as smoke tests
  that the recipe renders without error on every supported Python. Regenerate
  with ``pytest tests/charts --mpl-generate-path=tests/charts/baseline``.
- Plain logic tests — assert structure (panel counts, raised errors) without
  depending on any baseline image.

Data is synthesised deterministically (fixed ``default_rng`` seeds) so the
baselines are reproducible.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.inputs import PredictionGroup
from myocard_egm_studio.charts.matplotlib.prediction_histogram import prediction_histogram

#: Loose RMS tolerance absorbing sub-pixel font/antialiasing differences across
#: matplotlib/freetype builds while still catching real plot changes (wrong
#: colors, missing series, wrong layout push RMS far higher).
_TOL = 20.0


def _spec(
    *, layout: dict[str, object] | None = None, styling: dict[str, object] | None = None
) -> FigureSpec:
    """Minimal valid ``prediction-histogram`` FigureSpec for the recipe under test."""
    payload: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_prediction_histogram_test",
        "description": "prediction-histogram recipe test spec",
        "recipe": "prediction-histogram",
        "output": {"format": "png", "path": "out.png"},
    }
    if layout is not None:
        payload["layout"] = layout
    if styling is not None:
        payload["styling"] = styling
    return FigureSpec.model_validate(payload)


def _labeled_group(name: str = "Synthetic val", *, n: int = 400, seed: int = 0) -> PredictionGroup:
    """A balanced 2-class group: healthy probs skew low, fibrotic skew high."""
    rng = np.random.default_rng(seed)
    labels = np.array([0] * (n // 2) + [1] * (n // 2), dtype=np.int64)
    probs = np.empty(n, dtype=np.float64)
    probs[labels == 0] = rng.beta(2.0, 5.0, size=int((labels == 0).sum()))
    probs[labels == 1] = rng.beta(5.0, 2.0, size=int((labels == 1).sum()))
    return PredictionGroup(
        name=name, probs=probs, labels=labels, label_names={0: "healthy", 1: "fibrotic"}
    )


def _unlabeled_group(name: str = "IAFDB", *, n: int = 300, seed: int = 1) -> PredictionGroup:
    """An unlabeled group with over-confident (high, near-saturated) probs."""
    rng = np.random.default_rng(seed)
    probs = rng.beta(8.0, 2.0, size=n).astype(np.float64)
    return PredictionGroup(name=name, probs=probs)


# --------------------------------------------------------------------------- #
# Snapshot tests (compare only under --mpl; smoke tests otherwise).
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_panels_synth_vs_iafdb() -> Figure:
    """Panels mode, the canonical Phase-1.5 figure: a labeled synthetic panel
    (per-class split) beside an unlabeled IAFDB panel (single distribution)."""
    data = [_labeled_group(), _unlabeled_group()]
    return prediction_histogram(data, _spec(layout={"mode": "panels"}))


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_overlay_two_groups() -> Figure:
    """Overlay mode: two groups' distributions as step outlines on one axis,
    distinguished by color + legend (the synthetic-vs-real comparison view)."""
    data = [_labeled_group(name="Synthetic"), _unlabeled_group(name="IAFDB")]
    return prediction_histogram(data, _spec(layout={"mode": "overlay"}))


# --------------------------------------------------------------------------- #
# Logic tests (no baseline image needed).
# --------------------------------------------------------------------------- #


def test_panels_one_axis_per_group() -> None:
    """Panels mode draws exactly one subplot per PredictionGroup."""
    data = [_labeled_group(), _unlabeled_group(), _labeled_group(name="Synthetic test")]
    fig = prediction_histogram(data, _spec(layout={"mode": "panels"}))
    assert len(fig.axes) == 3


def test_overlay_single_axis() -> None:
    """Overlay mode draws all groups on a single shared axis."""
    data = [_labeled_group(), _unlabeled_group()]
    fig = prediction_histogram(data, _spec(layout={"mode": "overlay"}))
    assert len(fig.axes) == 1


def test_defaults_to_panels() -> None:
    """An absent ``layout.mode`` defaults to panels (one axis per group)."""
    data = [_labeled_group(), _unlabeled_group()]
    fig = prediction_histogram(data, _spec())
    assert len(fig.axes) == 2


def test_empty_data_raises() -> None:
    """No groups is a caller error, not an empty figure."""
    with pytest.raises(ValueError, match="at least one PredictionGroup"):
        prediction_histogram([], _spec())


def test_unknown_mode_raises() -> None:
    """An unrecognised ``layout.mode`` raises with the valid choices."""
    with pytest.raises(ValueError, match="unknown layout mode"):
        prediction_histogram([_labeled_group()], _spec(layout={"mode": "violin"}))


def test_labeled_panel_facets_by_class() -> None:
    """A labeled group's panel carries one legend entry per present class."""
    fig = prediction_histogram([_labeled_group()], _spec(layout={"mode": "panels"}))
    legend = fig.axes[0].get_legend()
    assert legend is not None
    assert {t.get_text() for t in legend.get_texts()} == {"healthy", "fibrotic"}
