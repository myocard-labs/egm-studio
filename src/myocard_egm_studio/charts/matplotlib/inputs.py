"""Prepared recipe inputs — the data contract between loaders and recipes.

A recipe is pure plotting: it takes one of these already-prepared inputs (never
a bank path or a raw HDF5 file) plus the FigureSpec, and returns a Figure. The
headless renderer's data-loading step (Block 7) is what turns a spec's
``inputs.groups`` bank ids into these structures; until that lands, tests and
callers build them in memory.

These live next to the recipes that consume them (not in egm-contracts) because
they're egm-studio-internal figure-data shapes, not a cross-repo schema. One
input type per recipe family; more land as Block 3 adds recipes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["BarChartData", "FeatureGroup", "PredictionGroup"]


@dataclass(frozen=True)
class PredictionGroup:
    """One named group of model output probabilities for ``prediction-histogram``.

    Attributes
    ----------
    name
        Legend / panel label (e.g. ``"Synthetic val"``, ``"IAFDB"``).
    probs
        ``(N,)`` predicted probability of the positive class, in ``[0, 1]``.
    labels
        Optional ``(N,)`` integer truth labels. When present the recipe facets
        the histogram by class; ``None`` (the IAFDB shape) draws one
        distribution with no class split.
    label_names
        Optional ``{int: str}`` map for the class legend (e.g.
        ``{0: "healthy", 1: "fibrotic"}``). Used only when ``labels`` is set.
    """

    name: str
    probs: NDArray[np.float64]
    labels: NDArray[np.int64] | None = None
    label_names: dict[int, str] | None = None


@dataclass(frozen=True)
class FeatureGroup:
    """One named group's per-feature value arrays for ``feature-distribution-overlay``.

    Attributes
    ----------
    name
        Legend / source label (e.g. ``"Synthetic v1.5"``, ``"IAFDB"``).
    values
        ``{feature_name: (N,) float array}`` — one entry per egm-features bundle
        column. Every group in a figure shares the same feature keys (the loader
        builds them from ``view_model.FEATURE_COLUMNS``); ``N`` may differ across
        groups (banks differ in size), which is why each panel is
        density-normalized rather than count-based.
    units
        Optional ``{feature_name: unit}`` for the subset of features that carry a
        unit (e.g. ``{"peak_to_peak": "mV", "spectral_centroid": "Hz"}``);
        features absent are unitless. The loader fills it via
        ``view_model.feature_units`` (so ``peak_to_peak`` tracks the bank's
        ``amp_type``) and the recipe labels each panel's x-axis from it.
    """

    name: str
    values: dict[str, NDArray[np.float64]]
    units: dict[str, str] | None = None


@dataclass(frozen=True)
class BarChartData:
    """A single bar series for the ``bar-chart-with-deltas`` recipe.

    Generic by design — the F-1.5.3 loader fills it with per-intervention
    aggregate sim-realism distances, but the same recipe is reused for counts,
    accuracies, etc. (one value per category).

    Attributes
    ----------
    categories
        One label per bar (e.g. the intervention / synthetic-variant names).
    values
        ``(K,)`` bar heights, aligned with ``categories``.
    errors
        Optional ``(K,)`` symmetric error-bar magnitudes, aligned with values.
    baseline_index
        Optional index into ``categories`` whose value is the delta reference.
        When set, the recipe draws a reference line at that value and annotates
        every other bar with its signed change from it (the "deltas").
    value_label
        y-axis label for the bar heights (e.g. ``"mean KS distance to IAFDB"``).
    """

    categories: list[str]
    values: NDArray[np.float64]
    errors: NDArray[np.float64] | None = None
    baseline_index: int | None = None
    value_label: str = ""
