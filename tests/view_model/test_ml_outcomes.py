"""Tests for the ML-outcome view-model join (view_model.ml_outcomes, B8a)."""

from __future__ import annotations

import pytest
from myocard_egm_data.banks import ClassifierBank

from myocard_egm_studio.analysis.metrics import positive_prob
from myocard_egm_studio.view_model import ML_COLUMNS, build_view_model, ml_outcome_frame


def test_raw_bank_has_no_ml_outcomes(tiny_classifier_bank: ClassifierBank) -> None:
    assert ml_outcome_frame(tiny_classifier_bank) is None  # no predictions -> not evaluated


def test_labeled_eval_bank_fills_every_column(tiny_predictions_bank: ClassifierBank) -> None:
    df = ml_outcome_frame(tiny_predictions_bank)
    assert df is not None
    assert list(df.columns) == list(ML_COLUMNS)
    assert len(df) == tiny_predictions_bank.n_traces
    assert ((df["predicted_prob"] >= 0.0) & (df["predicted_prob"] <= 1.0)).all()
    assert set(df["correctness_bucket"]).issubset({"TP", "TN", "FP", "FN"})
    assert df["per_trace_loss"].notna().all()  # truth present -> finite loss
    assert df["calibration_residual"].notna().all()


def test_unlabeled_eval_bank_is_prob_and_class_only(
    tiny_unlabeled_predictions_bank: ClassifierBank,
) -> None:
    df = ml_outcome_frame(tiny_unlabeled_predictions_bank)
    assert df is not None
    assert df["predicted_prob"].notna().all()  # prob is always defined
    assert df["correctness_bucket"].isna().all()  # no truth -> None
    assert df["per_trace_loss"].isna().all()  # truth-dependent -> NaN
    assert df["calibration_residual"].isna().all()


def test_bucket_matches_truth_vs_prediction(tiny_predictions_bank: ClassifierBank) -> None:
    df = ml_outcome_frame(tiny_predictions_bank)
    assert df is not None
    for trace, bucket in zip(tiny_predictions_bank.traces, df["correctness_bucket"], strict=True):
        assert trace.prediction is not None
        truth_pos = trace.label_truth == 1
        pred_pos = trace.prediction.label_pred == 1
        expected = ("TP" if pred_pos else "FN") if truth_pos else ("FP" if pred_pos else "TN")
        assert bucket == expected


def test_predicted_prob_is_the_softmax_positive_prob(
    tiny_predictions_bank: ClassifierBank,
) -> None:
    df = ml_outcome_frame(tiny_predictions_bank)
    assert df is not None
    trace = tiny_predictions_bank.traces[0]
    assert trace.prediction is not None
    assert df["predicted_prob"].iloc[0] == pytest.approx(
        positive_prob(trace.prediction.pred_logits, 1)
    )


def test_build_view_model_appends_ml_columns_for_an_evaluated_bank(
    tiny_predictions_bank: ClassifierBank,
) -> None:
    frame = build_view_model(tiny_predictions_bank, with_features=False)
    assert set(ML_COLUMNS).issubset(frame.columns)


def test_build_view_model_omits_ml_columns_for_a_raw_bank(
    tiny_classifier_bank: ClassifierBank,
) -> None:
    frame = build_view_model(tiny_classifier_bank, with_features=False)
    assert not (set(ML_COLUMNS) & set(frame.columns))
