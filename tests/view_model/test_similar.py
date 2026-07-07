"""Tests for the cross-bank similarity wrapper (view_model.similar, B7.10)."""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.view_model import (
    nearest_correct_pair,
    similar_in_other_sources,
    within_class_neighborhood,
)


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


def _ml_frame() -> pd.DataFrame:
    # row_id 0 is a misclassified fibrotic (FN); label 1 = fibrotic, 0 = healthy.
    return pd.DataFrame(
        {
            "row_id": [0, 1, 2, 3, 4, 5, 6],
            "label": [1, 0, 0, 0, 1, 1, 1],
            "correctness_bucket": ["FN", "TN", "TN", "FP", "TP", "TP", "FN"],
            "sample_entropy": [1.0, 1.1, 5.0, 1.05, 1.3, 1.05, 4.0],
        }
    )


def test_nearest_correct_pair_finds_correct_opposite_label() -> None:
    # source 0 (FN, label 1); nearest correctly-classified (TN) healthy is row 1 (1.1).
    # row 3 (1.05) is closer but FP (misclassified) so it's not a candidate.
    assert nearest_correct_pair(_ml_frame(), 0, "sample_entropy") == 1


def test_nearest_correct_pair_none_when_source_is_correct() -> None:
    assert nearest_correct_pair(_ml_frame(), 4, "sample_entropy") is None  # row 4 is TP


def test_nearest_correct_pair_none_without_ml_columns() -> None:
    bare = pd.DataFrame({"row_id": [0, 1], "sample_entropy": [1.0, 2.0]})
    assert nearest_correct_pair(bare, 0, "sample_entropy") is None


def test_within_class_neighborhood_returns_k_nearest_same_label() -> None:
    # source 0 (label 1); same-label peers by |x-1.0|: row5(0.05), row4(0.3), row6(3.0)
    assert within_class_neighborhood(_ml_frame(), 0, "sample_entropy", k=2) == [5, 4]


def test_within_class_neighborhood_excludes_source_and_other_labels() -> None:
    result = within_class_neighborhood(_ml_frame(), 0, "sample_entropy", k=5)
    assert result == [5, 4, 6]  # all label-1 peers, nearest first; source + label-0 excluded
