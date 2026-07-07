"""Distribution + distance primitives for the analysis layer.

Pure statistics over 1-D samples — the data-prep substrate for the P0 figure
recipes:

- ``feature-distribution-overlay`` — per-panel :func:`kde` (or
  :func:`histogram`) plus a per-panel :func:`ks_distance` /
  :func:`wasserstein_distance` annotation.
- ``prediction-histogram`` — binned P(class) via :func:`histogram`. Use the
  histogram, not the KDE, for predicted-probability data: the saturated
  IAFDB case (every value ≈ 1.0) has singular KDE covariance, while a
  fixed-bin histogram stays well-defined.
- ``bar-chart-with-deltas`` — aggregate sim-vs-real distance built from
  per-feature :func:`wasserstein_distance` (assembled in :mod:`.aggregation`).

Every function coerces its input to a 1-D float array and drops non-finite
(NaN / inf) entries before computing — a degenerate trace that produced a NaN
feature shouldn't blow up a whole-bank distribution comparison. Functions
raise :class:`ValueError` when nothing finite remains.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats

__all__ = [
    "empirical_cdf",
    "histogram",
    "kde",
    "ks_distance",
    "wasserstein_distance",
]


def _finite_1d(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    """Coerce ``values`` to a 1-D float array, dropping non-finite entries."""
    arr = np.asarray(values, dtype=np.float64).ravel()
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError(f"{name} has no finite values to analyze.")
    return arr


def empirical_cdf(values: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Empirical CDF as ``(sorted_values, cdf)``.

    ``cdf[i] = (i + 1) / n`` is the fraction of samples ``<= sorted_values[i]``.
    The visual companion to :func:`ks_distance` (whose statistic is the max
    vertical gap between two such curves). Non-finite values are dropped.
    """
    x = np.sort(_finite_1d(values, name="values"))
    n = x.size
    cdf = np.arange(1, n + 1, dtype=np.float64) / n
    return x, cdf


def ks_distance(a: ArrayLike, b: ArrayLike) -> float:
    """Two-sample Kolmogorov-Smirnov statistic ``sup_x |F_a(x) - F_b(x)|``.

    In ``[0, 1]``: 0 = identical empirical distributions, 1 = disjoint
    supports. Unitless, so it compares across features with different scales.
    Thin wrapper over ``scipy.stats.ks_2samp`` returning the statistic only —
    for a figure annotation the distance is what matters, not the p-value.
    Non-finite values are dropped from each sample independently.
    """
    fa = _finite_1d(a, name="a")
    fb = _finite_1d(b, name="b")
    return float(stats.ks_2samp(fa, fb).statistic)


def wasserstein_distance(a: ArrayLike, b: ArrayLike) -> float:
    """1-D Wasserstein (earth-mover) distance between two samples.

    In the same units as the data (unlike the unitless KS statistic), which
    makes it the better default for the aggregate sim-realism distance in
    ``bar-chart-with-deltas`` once per-feature distances are normalized. Thin
    wrapper over ``scipy.stats.wasserstein_distance``. Non-finite values are
    dropped from each sample independently.
    """
    fa = _finite_1d(a, name="a")
    fb = _finite_1d(b, name="b")
    return float(stats.wasserstein_distance(fa, fb))


def histogram(
    values: ArrayLike,
    *,
    bins: int | ArrayLike = 50,
    range: tuple[float, float] | None = None,  # matches np.histogram's kwarg name
    density: bool = False,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Histogram counts + bin edges (``np.histogram`` wrapper).

    Returned as ``(counts, edges)`` with ``len(edges) == len(counts) + 1``.
    The primary primitive for ``prediction-histogram``: binning P(class) into
    fixed bins stays well-defined on the saturated IAFDB case (every value
    ≈ 1.0), where :func:`kde` would be singular. Pass an explicit
    ``range=(0.0, 1.0)`` for probability data so bins align across groups.
    Non-finite values are dropped.
    """
    x = _finite_1d(values, name="values")
    counts, edges = np.histogram(x, bins=bins, range=range, density=density)
    return counts.astype(np.float64), edges.astype(np.float64)


def kde(
    values: ArrayLike,
    *,
    grid: ArrayLike | None = None,
    n_grid: int = 200,
    bw_method: str | float | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Gaussian KDE evaluated on a grid; returns ``(grid, density)``.

    The smooth per-panel curve for ``feature-distribution-overlay``. When
    ``grid`` is None a linear grid of ``n_grid`` points spanning the data
    range is built. Raises :class:`ValueError` on degenerate input (fewer
    than 2 distinct finite values) where the Gaussian KDE covariance is
    singular — callers with saturated data (predicted probabilities pinned at
    1.0) should use :func:`histogram` instead. Non-finite values are dropped.
    """
    x = _finite_1d(values, name="values")
    if np.unique(x).size < 2:
        raise ValueError(
            "kde needs at least 2 distinct finite values (the Gaussian KDE "
            "covariance is singular otherwise); use histogram() for "
            "degenerate / saturated data such as pinned probabilities."
        )
    if grid is None:
        g = np.linspace(float(x.min()), float(x.max()), n_grid)
    else:
        g = _finite_1d(grid, name="grid")
    density = stats.gaussian_kde(x, bw_method=bw_method)(g)
    return g, np.asarray(density, dtype=np.float64)
