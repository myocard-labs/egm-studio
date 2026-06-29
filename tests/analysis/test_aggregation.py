"""Unit tests for analysis.aggregation (between-group feature distance)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from myocard_egm_studio.analysis import aggregation as agg


@pytest.fixture
def df() -> pd.DataFrame:
    """Two groups (healthy / fibrotic) with *disjoint* per-feature ranges, so
    the between-group distances are easy to reason about."""
    return pd.DataFrame(
        {
            "label_name": ["healthy", "healthy", "fibrotic", "fibrotic"],
            "peak_to_peak": [1.0, 1.2, 2.0, 2.4],
            "sample_entropy": [0.5, 0.6, 1.5, 1.4],
        }
    )


def test_feature_distances_ks_and_aggregate(df: pd.DataFrame) -> None:
    """feature_distances returns one distance per requested feature; with the
    healthy/fibrotic ranges fully disjoint each KS distance is the maximal 1.0,
    and the unweighted aggregate_distance is just their plain mean."""
    a = df[df["label_name"] == "healthy"]
    b = df[df["label_name"] == "fibrotic"]
    distances = agg.feature_distances(
        a, b, feature_cols=["peak_to_peak", "sample_entropy"], metric="ks"
    )
    assert set(distances) == {"peak_to_peak", "sample_entropy"}
    assert distances["peak_to_peak"] == pytest.approx(1.0)
    assert agg.aggregate_distance(distances) == pytest.approx(np.mean(list(distances.values())))


def test_aggregate_distance_weighted() -> None:
    """aggregate_distance is a weight-normalized mean: putting the larger weight
    (3) on the smaller distance (1) and the smaller weight (1) on the larger
    distance (3) pulls the result to (3*1 + 1*3) / 4 = 1.5, below the simple
    average of 2.0."""
    distances = {"a": 1.0, "b": 3.0}
    expected = (3.0 * 1.0 + 1.0 * 3.0) / 4.0
    assert agg.aggregate_distance(distances, weights={"a": 3.0, "b": 1.0}) == pytest.approx(
        expected
    )


def test_feature_distances_rejects_unknown_metric(df: pd.DataFrame) -> None:
    """An unsupported metric name raises rather than silently falling back to a
    default."""
    with pytest.raises(ValueError, match="metric must be"):
        agg.feature_distances(df, df, feature_cols=["peak_to_peak"], metric="cosine")


def test_aggregate_distance_empty_raises() -> None:
    """Rolling up an empty distance map raises — there's nothing to average."""
    with pytest.raises(ValueError, match="empty"):
        agg.aggregate_distance({})


def test_aggregate_distance_zero_weights_raises() -> None:
    """Weights that sum to zero can't form a weighted mean (division by zero),
    so aggregate_distance raises."""
    with pytest.raises(ValueError, match="non-positive"):
        agg.aggregate_distance({"a": 1.0}, weights={"a": 0.0})
