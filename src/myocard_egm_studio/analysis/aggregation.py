"""Between-group feature-distribution distance.

Per-feature distribution distance between two groups' view-models — the
sim-vs-IAFDB comparison — via :func:`feature_distances`, then a single
weighted-mean roll-up via :func:`aggregate_distance`. Together they back the
``bar-chart-with-deltas`` recipe's per-intervention sim-realism number.

The per-group *value arrays* that the ``feature-distribution-overlay``
histogram recipe needs (split a view-model by a group column, return each
group's raw feature values to feed :func:`..distributions.kde` /
:func:`..distributions.histogram`) land here in Block 3, when that recipe is
built and the exact shape is pinned down.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from myocard_egm_studio.analysis import distributions

__all__ = [
    "aggregate_distance",
    "feature_distances",
]

#: Distance metrics :func:`feature_distances` knows how to compute.
_DISTANCE_METRICS = {
    "wasserstein": distributions.wasserstein_distance,
    "ks": distributions.ks_distance,
}


def feature_distances(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    metric: str = "wasserstein",
) -> dict[str, float]:
    """Per-feature distribution distance between two groups' view-models.

    ``metric`` is ``"wasserstein"`` (default; data-unit) or ``"ks"`` (unitless
    in ``[0, 1]``). Returns ``{feature: distance}`` in ``feature_cols`` order.
    Each column is reduced to its finite values independently inside the
    distance primitive.
    """
    dist_fn = _DISTANCE_METRICS.get(metric)
    if dist_fn is None:
        raise ValueError(f"metric must be one of {sorted(_DISTANCE_METRICS)}; got {metric!r}.")
    out: dict[str, float] = {}
    for col in feature_cols:
        if col not in df_a.columns or col not in df_b.columns:
            raise KeyError(f"feature {col!r} missing from one of the view-models.")
        out[col] = dist_fn(df_a[col].to_numpy(), df_b[col].to_numpy())
    return out


def aggregate_distance(
    distances: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
) -> float:
    """Roll a ``{feature: distance}`` map up into one weighted-mean scalar.

    Equal weights by default — the F-1.5.3 starting point; learned-importance
    weighting is an open inventory question. ``weights`` need not be
    normalized. Because raw Wasserstein distances carry per-feature units,
    callers comparing across heterogeneous features should normalize the
    per-feature distances first (or use the unitless ``"ks"`` metric).
    """
    if not distances:
        raise ValueError("distances is empty; nothing to aggregate.")
    keys = list(distances)
    vals = np.array([distances[k] for k in keys], dtype=np.float64)
    if weights is None:
        return float(vals.mean())
    w = np.array([weights.get(k, 0.0) for k in keys], dtype=np.float64)
    total = float(w.sum())
    if total <= 0.0:
        raise ValueError("weights sum to a non-positive value; can't take a weighted mean.")
    return float((vals * w).sum() / total)
