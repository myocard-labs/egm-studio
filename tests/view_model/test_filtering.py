"""Tests for the pure filter logic (view_model.filtering)."""

from __future__ import annotations

import pandas as pd
import pytest

from myocard_egm_studio.view_model.filtering import (
    Condition,
    FilterSpec,
    apply_filter,
    filter_columns,
)


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trace_idx": [0, 1, 2, 3],
            "source": ["synthetic", "synthetic", "iafdb", "iafdb"],
            "label_name": ["healthy", "fibrotic", "healthy", None],
            "sample_entropy": [0.5, 1.8, 2.1, float("nan")],
            "patient_id": ["P0", "P1", "P2", "P3"],
        }
    )


def _kept(df: pd.DataFrame, spec: FilterSpec) -> list[int]:
    return [int(idx) for idx in df[apply_filter(df, spec)]["trace_idx"]]


def test_empty_spec_matches_all() -> None:
    assert apply_filter(_df(), FilterSpec()).tolist() == [True, True, True, True]


def test_numeric_threshold_excludes_nan() -> None:
    assert _kept(_df(), FilterSpec((Condition("sample_entropy", ">", "1.5"),))) == [1, 2]


def test_categorical_equality() -> None:
    assert _kept(_df(), FilterSpec((Condition("source", "==", "synthetic"),))) == [0, 1]


def test_and_combines_conditions() -> None:
    spec = FilterSpec(
        (Condition("source", "==", "synthetic"), Condition("sample_entropy", ">", "1.0")), "and"
    )
    assert _kept(_df(), spec) == [1]


def test_or_combines_conditions() -> None:
    spec = FilterSpec(
        (Condition("source", "==", "iafdb"), Condition("sample_entropy", "<", "1.0")), "or"
    )
    assert _kept(_df(), spec) == [0, 2, 3]


def test_missing_values_never_match() -> None:
    # a None label_name (idx 3) is excluded by != as well as ==
    assert _kept(_df(), FilterSpec((Condition("label_name", "!=", "healthy"),))) == [1]


def test_and_present_keeps_rows_missing_the_field() -> None:
    # "and" excludes the NaN-entropy row (idx 3); "and_present" skips the condition for
    # it and keeps it — a field only some banks carry doesn't drop the banks that lack it
    spec = FilterSpec((Condition("sample_entropy", ">", "1.5"),), "and_present")
    assert _kept(_df(), spec) == [1, 2, 3]


def test_and_present_still_filters_rows_that_have_the_field() -> None:
    # a condition whose value *is* present still applies: only synthetic + entropy>1.5
    spec = FilterSpec(
        (Condition("source", "==", "synthetic"), Condition("sample_entropy", ">", "1.5")),
        "and_present",
    )
    assert _kept(_df(), spec) == [1]  # idx 3's NaN entropy is skipped, but its source fails


def test_bad_numeric_value_raises() -> None:
    with pytest.raises(ValueError):
        apply_filter(_df(), FilterSpec((Condition("sample_entropy", ">", "high"),)))


def test_unknown_column_raises() -> None:
    with pytest.raises(KeyError):
        apply_filter(_df(), FilterSpec((Condition("nope", "==", "x"),)))


def test_filter_columns_classifies_and_hides_plumbing() -> None:
    columns = {c.name: c for c in filter_columns(_df())}
    assert "trace_idx" not in columns  # a hidden plumbing column
    assert columns["sample_entropy"].numeric is True
    assert columns["sample_entropy"].ops == (">", ">=", "<", "<=", "==", "!=")
    assert columns["source"].numeric is False
    assert columns["source"].ops == ("==", "!=")
    assert columns["source"].choices == ("iafdb", "synthetic")  # sorted distinct values
    assert columns["label_name"].choices == ("fibrotic", "healthy")  # None dropped
