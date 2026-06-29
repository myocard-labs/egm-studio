"""Per-feature similarity scaffolding (ADR-020).

v0.1 ships *per-feature* similarity only — "nearest trace along
``sample_entropy``", "along ``peak_to_peak``", etc. — computed by ranking
candidates by absolute distance along one feature axis. Cheap, transparent,
easy to validate. The joint multi-feature metric is deferred (ADR-020).

This module is the foundation primitive; the richer diagnostics that build on
it — nearest-correct-pair (a misclassified trace + its most-similar
correctly-classified opposite-label counterpart) and within-class-neighborhood
(an outlier + its k-nearest in-class peers) — land with Flow B in Block 8,
once ML-outcome columns join the view-model. Both reduce to
:func:`rank_by_feature_distance` over a ``candidate_mask``.

Indices returned are **positional** (``iloc``-style, ``0 .. n_rows-1``), not
the view-model's pandas index labels.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

__all__ = [
    "nearest_along_feature",
    "rank_by_feature_distance",
]


def rank_by_feature_distance(
    df: pd.DataFrame,
    *,
    feature: str,
    target_value: float,
    candidate_mask: NDArray[np.bool_] | None = None,
) -> NDArray[np.intp]:
    """Positional row indices of ``df`` ranked by ``|df[feature] - target_value|``.

    Ascending — closest first. ``candidate_mask`` is an optional boolean array
    over all rows; only ``True`` rows are ranked (the hook Block 8 uses to
    restrict to the opposite label or a correctly-classified subset). Rows with
    a non-finite feature value (or a non-finite ``target_value``) sort last.
    Ties break by ascending position (stable sort).
    """
    if feature not in df.columns:
        raise KeyError(f"feature {feature!r} not in view-model columns.")
    n = df.shape[0]
    values = df[feature].to_numpy(dtype=np.float64)
    dist = np.abs(values - float(target_value))
    dist = np.where(np.isfinite(dist), dist, np.inf)
    positions = np.arange(n, dtype=np.intp)
    if candidate_mask is not None:
        mask = np.asarray(candidate_mask, dtype=bool)
        if mask.shape != (n,):
            raise ValueError(
                f"candidate_mask must have shape ({n},) matching df rows; got {mask.shape}."
            )
        positions = positions[mask]
        dist = dist[mask]
    order = np.argsort(dist, kind="stable")
    return positions[order]


def nearest_along_feature(
    df: pd.DataFrame,
    *,
    feature: str,
    target_value: float,
    candidate_mask: NDArray[np.bool_] | None = None,
) -> int:
    """Positional index of the single nearest row along ``feature``.

    Convenience over ``rank_by_feature_distance(...)[0]``. Raises
    :class:`ValueError` when there are no candidate rows (empty ``df`` or an
    all-``False`` ``candidate_mask``).
    """
    ranked = rank_by_feature_distance(
        df, feature=feature, target_value=target_value, candidate_mask=candidate_mask
    )
    if ranked.size == 0:
        raise ValueError("no candidate rows to rank (empty df or all-False candidate_mask).")
    return int(ranked[0])
