"""Tests for the cross-bank similarity wrapper (view_model.similar, B7.10)."""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.view_model import similar_in_other_sources


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": [0, 1, 2, 3, 4],
            "source": ["synthetic", "synthetic", "iafdb", "iafdb", "noise"],
            "sample_entropy": [1.0, 5.0, 1.2, 4.0, 0.9],
        }
    )


def test_nearest_in_each_other_source() -> None:
    # source = row_id 0 (synthetic, 1.0); nearest iafdb is row 2 (1.2), nearest noise is row 4
    # (0.9) — one match per other source, in load order (iafdb, then noise).
    assert similar_in_other_sources(_frame(), 0, "sample_entropy") == [2, 4]


def test_own_source_is_never_a_match() -> None:
    # the other synthetic row (row 1) is excluded even though it exists
    assert 1 not in similar_in_other_sources(_frame(), 0, "sample_entropy")


def test_missing_row_or_feature_returns_empty() -> None:
    assert similar_in_other_sources(_frame(), 99, "sample_entropy") == []  # no such row_id
    assert similar_in_other_sources(_frame(), 0, "nope") == []  # no such feature


def test_single_source_has_no_matches() -> None:
    one_bank = _frame().iloc[0:2]  # both synthetic
    assert similar_in_other_sources(one_bank, 0, "sample_entropy") == []


def test_missing_source_value_returns_empty() -> None:
    frame = _frame()
    frame.loc[frame["row_id"] == 0, "sample_entropy"] = float("nan")
    assert similar_in_other_sources(frame, 0, "sample_entropy") == []
