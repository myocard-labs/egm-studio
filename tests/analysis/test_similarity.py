"""Unit tests for analysis.similarity (per-feature nearest scaffold, ADR-020)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from myocard_egm_studio.analysis import similarity as sim


@pytest.fixture
def df() -> pd.DataFrame:
    """Four rows with one feature column + a binary label, for nearest-along-
    feature lookups (row order matters — results are positional indices)."""
    return pd.DataFrame(
        {
            "sample_entropy": [0.1, 0.5, 0.9, 0.55],
            "label": [0, 0, 1, 1],
        }
    )


def test_nearest_along_feature(df: pd.DataFrame) -> None:
    """nearest_along_feature returns the positional index of the row whose
    feature value is closest to the target — 0.52 is nearest to row 1 (0.5)."""
    assert sim.nearest_along_feature(df, feature="sample_entropy", target_value=0.52) == 1


def test_rank_order(df: pd.DataFrame) -> None:
    """rank_by_feature_distance orders rows by ascending |feature - target|;
    for target 0.52 the two closest are row 1 (0.5) then row 3 (0.55)."""
    ranked = sim.rank_by_feature_distance(df, feature="sample_entropy", target_value=0.52)
    assert list(ranked[:2]) == [1, 3]


def test_candidate_mask_restricts_to_subset(df: pd.DataFrame) -> None:
    """A candidate_mask limits the search to the masked rows: among the
    label==1 rows (0.9, 0.55) the nearest to 0.5 is row 3 (0.55). This is the
    hook Block 8 uses to restrict to the opposite label / a correct subset."""
    mask = (df["label"] == 1).to_numpy()
    assert (
        sim.nearest_along_feature(
            df, feature="sample_entropy", target_value=0.5, candidate_mask=mask
        )
        == 3
    )


def test_non_finite_feature_sorts_last() -> None:
    """A row with a non-finite feature value sorts to the end of the ranking
    (treated as infinitely far), never beating a finite candidate."""
    d = pd.DataFrame({"f": [np.nan, 1.0, 2.0]})
    ranked = sim.rank_by_feature_distance(d, feature="f", target_value=1.0)
    assert ranked[0] == 1
    assert ranked[-1] == 0


def test_empty_candidate_mask_raises(df: pd.DataFrame) -> None:
    """An all-False candidate_mask leaves no candidates, so nearest_along_feature
    raises rather than returning an arbitrary index."""
    mask = np.zeros(len(df), dtype=bool)
    with pytest.raises(ValueError, match="no candidate"):
        sim.nearest_along_feature(
            df, feature="sample_entropy", target_value=0.5, candidate_mask=mask
        )


def test_wrong_mask_shape_raises(df: pd.DataFrame) -> None:
    """A candidate_mask whose length doesn't match the frame's row count is a
    caller bug and raises (rather than silently mis-aligning)."""
    with pytest.raises(ValueError, match="candidate_mask"):
        sim.rank_by_feature_distance(
            df, feature="sample_entropy", target_value=0.5, candidate_mask=np.array([True, False])
        )


def test_missing_feature_raises(df: pd.DataFrame) -> None:
    """Requesting a feature column that isn't in the frame raises KeyError."""
    with pytest.raises(KeyError):
        sim.nearest_along_feature(df, feature="nope", target_value=0.5)
