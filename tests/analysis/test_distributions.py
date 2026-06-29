"""Unit tests for the analysis.distributions primitives (no display)."""

from __future__ import annotations

import numpy as np
import pytest

from myocard_egm_studio.analysis import distributions as dist


def test_ks_distance_identical_is_zero() -> None:
    """A sample vs itself has KS distance 0 — the empirical CDFs coincide, so
    their maximum vertical gap is zero."""
    a = np.linspace(0.0, 1.0, 100)
    assert dist.ks_distance(a, a) == 0.0


def test_ks_distance_disjoint_is_one() -> None:
    """Disjoint supports give the maximal KS distance of 1: at any x in [0, 1)
    one sample's CDF has already reached 1.0 (all 0s) while the other is still
    0.0 (all 1s), so the CDF gap is the full 1.0."""
    assert dist.ks_distance(np.zeros(50), np.ones(50)) == pytest.approx(1.0)


def test_wasserstein_distance_is_the_shift() -> None:
    """Two constant samples a fixed distance apart have Wasserstein distance
    equal to that shift (3.0). Unlike the unitless KS statistic, Wasserstein is
    in data units — it's the average mass-movement to morph one distribution
    into the other."""
    assert dist.wasserstein_distance(np.zeros(100), np.full(100, 3.0)) == pytest.approx(3.0)


def test_empirical_cdf_sorts_and_reaches_one() -> None:
    """empirical_cdf returns the values sorted ascending alongside a strictly
    increasing step CDF that reaches exactly 1.0 at the largest value."""
    x, cdf = dist.empirical_cdf([3.0, 1.0, 2.0])
    assert list(x) == [1.0, 2.0, 3.0]
    assert cdf[-1] == pytest.approx(1.0)
    assert np.all(np.diff(cdf) > 0)


def test_histogram_counts_sum_to_n() -> None:
    """Bin counts sum to the number of (finite) input samples, and there is
    exactly one more bin edge than bin — the shape the prediction-histogram
    recipe relies on."""
    counts, edges = dist.histogram([0.1, 0.2, 0.9], bins=5, range=(0.0, 1.0))
    assert counts.sum() == 3
    assert len(edges) == len(counts) + 1


def test_kde_returns_grid_and_nonnegative_density() -> None:
    """kde evaluates the smooth density on an ``n_grid``-point grid and returns
    a non-negative density array of matching shape."""
    rng = np.random.default_rng(0)
    grid, density = dist.kde(rng.normal(size=200), n_grid=50)
    assert grid.shape == (50,)
    assert density.shape == (50,)
    assert np.all(density >= 0.0)


def test_kde_raises_on_degenerate_input() -> None:
    """kde raises on zero-variance data (every value 1.0) where the Gaussian
    KDE covariance is singular — exactly the saturated-prediction case the
    histogram path is meant to handle instead."""
    with pytest.raises(ValueError, match="distinct finite"):
        dist.kde(np.ones(100))


def test_non_finite_values_are_dropped() -> None:
    """NaN / inf entries are dropped before computing, so the result reflects
    only the finite values — here the finite parts ([1, 2] vs [1, 2]) are
    identical, giving KS distance 0."""
    a = np.array([1.0, np.nan, 2.0, np.inf])
    assert dist.ks_distance(a, [1.0, 2.0]) == pytest.approx(0.0)


def test_all_non_finite_raises() -> None:
    """If nothing finite survives the NaN/inf drop, the primitive raises rather
    than returning a meaningless number."""
    with pytest.raises(ValueError, match="no finite values"):
        dist.wasserstein_distance([np.nan, np.inf], [1.0, 2.0])
