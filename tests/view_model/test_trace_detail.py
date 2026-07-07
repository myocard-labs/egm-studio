"""Tests for the pure per-trace detail projection (view_model.trace_detail)."""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.view_model.builder import FEATURE_COLUMNS
from myocard_egm_studio.view_model.trace_detail import trace_detail


def _df() -> pd.DataFrame:
    # row_id distinct from trace_idx: rows are selected by row_id, but the header
    # shows the per-bank trace_idx (as it would across two loaded banks, B7.8).
    base = {
        "source_bank_id": "b",
        "source_bank_type": "synthetic",
        "amp_type": "mv",
        "label": 1,
        "label_name": "fibrotic",
        "source": "Synthetic",
        "split": "train",
        "patient_id": "P01",
        **dict.fromkeys(FEATURE_COLUMNS, 1.0),
    }
    r0 = {**base, "row_id": 10, "trace_idx": 0, "sample_entropy": 1.5, "peak_to_peak": 2.0}
    r1 = {
        **base,
        "row_id": 11,
        "trace_idx": 1,
        "sample_entropy": 0.5,
        "peak_to_peak": 3.0,
        "label_name": "healthy",
    }
    return pd.DataFrame([r0, r1])


def test_headers_and_section_membership() -> None:
    detail = trace_detail(_df(), [10, 11])  # select by row_id
    assert detail.headers == ("#0", "#1")  # header shows the per-bank trace_idx
    assert len(detail.features) == len(FEATURE_COLUMNS)
    meta_labels = [row.label for row in detail.metadata]
    assert {"label_name", "source", "split", "patient_id"}.issubset(meta_labels)
    # plumbing (incl. row_id) hidden
    assert not {"trace_idx", "row_id", "amp_type", "label"} & set(meta_labels)


def test_feature_values_and_amplitude_unit() -> None:
    by_label = {row.label: row for row in trace_detail(_df(), [10, 11]).features}
    assert by_label["sample_entropy"].values == ("1.5", "0.5")  # one value per selected trace
    assert by_label["peak_to_peak"].unit == "mV"  # amp_type "mv" -> peak_to_peak in mV
    assert by_label["sample_entropy"].unit == ""  # entropy is unitless


def test_feature_deltas_vs_the_source_column() -> None:
    """Feature rows carry each column's signed delta vs the first (source) column."""
    by_label = {row.label: row for row in trace_detail(_df(), [10, 11]).features}
    entropy = by_label["sample_entropy"]  # 1.5 (source) then 0.5
    assert entropy.deltas == ("", "-1")  # source has no delta; #1 is 0.5 - 1.5 = -1
    assert by_label["peak_to_peak"].deltas == ("", "+1")  # 3.0 - 2.0 = +1


def test_single_trace_has_no_deltas() -> None:
    (entropy,) = [r for r in trace_detail(_df(), [10]).features if r.label == "sample_entropy"]
    assert entropy.deltas == ("",)  # a lone source column: nothing to compare against


def test_metadata_lead_order() -> None:
    labels = [row.label for row in trace_detail(_df(), [10]).metadata]
    assert labels[:3] == ["label_name", "source", "split"]


def test_single_trace_metadata_values() -> None:
    by_label = {row.label: row for row in trace_detail(_df(), [11]).metadata}
    assert by_label["label_name"].values == ("healthy",)
    assert by_label["patient_id"].values == ("P01",)


def _evaluated_df() -> pd.DataFrame:
    df = _df()
    df["predicted_prob"] = [0.9, 0.2]
    df["predicted_class"] = [1, 0]
    df["correctness_bucket"] = ["TP", "TN"]
    df["per_trace_loss"] = [0.1, 0.3]
    df["calibration_residual"] = [-0.1, 0.2]
    return df


def test_ml_section_present_and_excluded_from_metadata() -> None:
    detail = trace_detail(_evaluated_df(), [10, 11])
    assert [row.label for row in detail.ml] == [
        "predicted_prob",
        "predicted_class",
        "correctness_bucket",
        "per_trace_loss",
        "calibration_residual",
    ]
    # the ML columns live in the Model section, not folded into Metadata
    assert not {"predicted_prob", "correctness_bucket"} & {r.label for r in detail.metadata}


def test_ml_numeric_rows_carry_deltas_categorical_do_not() -> None:
    by_label = {row.label: row for row in trace_detail(_evaluated_df(), [10, 11]).ml}
    assert by_label["predicted_prob"].deltas == ("", "-0.7")  # 0.2 - 0.9
    assert by_label["correctness_bucket"].deltas == ()  # a bucket has no delta
    assert by_label["predicted_class"].deltas == ()  # a discrete class has no delta


def test_ml_section_empty_without_prediction_columns() -> None:
    assert trace_detail(_df(), [10]).ml == ()
