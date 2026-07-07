"""Tests for analysis/metrics — ROC curve + AUROC.

Checked against hand-computable cases (a 4-point set whose AUROC is 0.75, plus
the perfect / inverted / chance extremes) rather than a reference library, since
the point of metrics.py is to not depend on one. Where a curve and its AUROC are
cross-checked, the area is integrated by hand (np.trapz is deprecated under
numpy 2.x and filterwarnings=error would trip on it).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from myocard_egm_studio.analysis import metrics


def _auc_from_curve(fpr: np.ndarray, tpr: np.ndarray) -> float:
    """Trapezoidal area under the returned (fpr, tpr) — no np.trapz dependency."""
    return float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2.0))


# --------------------------------------------------------------------------- #
# AUROC
# --------------------------------------------------------------------------- #


def test_auroc_known_value() -> None:
    """The canonical 4-point example: AUROC = 0.75."""
    y_true = np.array([0, 0, 1, 1])
    y_pred_prob = np.array([0.1, 0.4, 0.35, 0.8])
    assert metrics.auroc(y_true, y_pred_prob) == pytest.approx(0.75)


def test_auroc_perfect_separation() -> None:
    """Every positive scores above every negative -> 1.0."""
    y_true = np.array([0, 0, 1, 1])
    y_pred_prob = np.array([0.1, 0.2, 0.8, 0.9])
    assert metrics.auroc(y_true, y_pred_prob) == pytest.approx(1.0)


def test_auroc_perfectly_inverted() -> None:
    """Scores rank the classes exactly backwards -> 0.0."""
    y_true = np.array([0, 0, 1, 1])
    y_pred_prob = np.array([0.9, 0.8, 0.2, 0.1])
    assert metrics.auroc(y_true, y_pred_prob) == pytest.approx(0.0)


def test_auroc_all_tied_is_chance() -> None:
    """Identical scores carry no ranking information -> 0.5 (tie-aware ranks)."""
    y_true = np.array([0, 1, 0, 1])
    y_pred_prob = np.array([0.5, 0.5, 0.5, 0.5])
    assert metrics.auroc(y_true, y_pred_prob) == pytest.approx(0.5)


def test_auroc_positive_label_other_than_one() -> None:
    """positive_label picks the positive class (one-vs-rest)."""
    y_true = np.array([0, 1, 2, 2])  # class 2 is positive ...
    y_pred_prob = np.array([0.1, 0.2, 0.8, 0.9])  # ... and scores highest -> perfect
    assert metrics.auroc(y_true, y_pred_prob, positive_label=2) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# ROC curve
# --------------------------------------------------------------------------- #


def test_roc_curve_perfect_passes_through_top_left() -> None:
    """Perfect separation: TPR reaches 1 while FPR is still 0; anchored at (0,0)."""
    y_true = np.array([0, 0, 1, 1])
    y_pred_prob = np.array([0.1, 0.2, 0.8, 0.9])
    fpr, tpr = metrics.roc_curve(y_true, y_pred_prob)
    assert (fpr[0], tpr[0]) == (0.0, 0.0)
    assert fpr[-1] == pytest.approx(1.0)
    assert tpr[-1] == pytest.approx(1.0)
    assert np.any((fpr == 0.0) & (tpr == 1.0))  # the (0, 1) corner
    assert _auc_from_curve(fpr, tpr) == pytest.approx(metrics.auroc(y_true, y_pred_prob))


def test_roc_curve_monotone_and_matches_auroc() -> None:
    """FPR and TPR are non-decreasing, and the curve's area equals the rank AUROC."""
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, size=200)
    y_pred_prob = rng.random(200)
    fpr, tpr = metrics.roc_curve(y_true, y_pred_prob)
    assert np.all(np.diff(fpr) >= 0)
    assert np.all(np.diff(tpr) >= 0)
    assert _auc_from_curve(fpr, tpr) == pytest.approx(metrics.auroc(y_true, y_pred_prob))


def test_roc_curve_collapses_tied_scores() -> None:
    """Tied scores share a single swept vertex (plus the (0,0) anchor)."""
    y_true = np.array([0, 1, 0, 1])
    y_pred_prob = np.array([0.5, 0.5, 0.5, 0.5])
    fpr, tpr = metrics.roc_curve(y_true, y_pred_prob)
    assert fpr.size == 2
    assert tpr.size == 2


# --------------------------------------------------------------------------- #
# Guards (shared by both)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fn", [metrics.auroc, metrics.roc_curve])
def test_single_class_raises(fn: Callable[..., object]) -> None:
    """No negatives (or no positives) is undefined -> ValueError, for both."""
    with pytest.raises(ValueError, match="both"):
        fn(np.array([1, 1, 1]), np.array([0.2, 0.5, 0.9]))


@pytest.mark.parametrize("fn", [metrics.auroc, metrics.roc_curve])
def test_shape_mismatch_raises(fn: Callable[..., object]) -> None:
    """y_true and y_pred_prob must align."""
    with pytest.raises(ValueError, match="same shape"):
        fn(np.array([0, 1]), np.array([0.5]))


# --------------------------------------------------------------------------- #
# Reliability curve + ECE
# --------------------------------------------------------------------------- #

# Two populated bins (mid-bin probs 0.25 and 0.75), both classes present.
_TWO_BIN_PROB = np.array([0.25] * 100 + [0.75] * 100)


def test_reliability_curve_bins_and_counts() -> None:
    """Non-empty bins only, with mean predicted prob + observed positive fraction."""
    # 0.25 bin: 0 positive; 0.75 bin: all positive.
    y_true = np.array([0] * 100 + [1] * 100)
    mean_pred, obs_freq, count = metrics.reliability_curve(y_true, _TWO_BIN_PROB, n_bins=10)
    assert mean_pred.tolist() == pytest.approx([0.25, 0.75])
    assert obs_freq.tolist() == pytest.approx([0.0, 1.0])
    assert count.tolist() == [100, 100]  # the other 8 bins are dropped
    assert int(count.sum()) == y_true.size


def test_ece_known_value() -> None:
    """Both bins miss the diagonal by 0.25, weighted equally -> ECE = 0.25."""
    y_true = np.array([0] * 100 + [1] * 100)
    assert metrics.expected_calibration_error(y_true, _TWO_BIN_PROB, n_bins=10) == pytest.approx(
        0.25
    )


def test_ece_zero_when_calibrated() -> None:
    """Observed fraction matches the predicted prob in every bin -> ECE = 0."""
    # 0.25 bin: 25/100 positive; 0.75 bin: 75/100 positive.
    y_true = np.array([1] * 25 + [0] * 75 + [1] * 75 + [0] * 25)
    assert metrics.expected_calibration_error(y_true, _TWO_BIN_PROB, n_bins=10) == pytest.approx(
        0.0
    )


def test_reliability_curve_respects_n_bins() -> None:
    """Coarser binning merges the two populations into one bin."""
    y_true = np.array([0] * 100 + [1] * 100)
    mean_pred, _, count = metrics.reliability_curve(y_true, _TWO_BIN_PROB, n_bins=1)
    assert count.tolist() == [200]
    assert mean_pred.tolist() == pytest.approx([0.5])  # (0.25*100 + 0.75*100) / 200


def test_reliability_curve_bad_n_bins_raises() -> None:
    """n_bins must be >= 1."""
    with pytest.raises(ValueError, match="n_bins"):
        metrics.reliability_curve(np.array([0, 1]), np.array([0.2, 0.8]), n_bins=0)


@pytest.mark.parametrize("fn", [metrics.reliability_curve, metrics.expected_calibration_error])
def test_calibration_single_class_raises(fn: Callable[..., object]) -> None:
    """Calibration reuses the both-classes guard."""
    with pytest.raises(ValueError, match="both"):
        fn(np.array([0, 0, 0]), np.array([0.2, 0.5, 0.9]))


# --------------------------------------------------------------------------- #
# Confusion matrix + positive_prob
# --------------------------------------------------------------------------- #


def test_confusion_matrix_counts() -> None:
    """M[i, j] = # true labels[i] predicted labels[j] (rows=true, cols=pred)."""
    matrix = metrics.confusion_matrix([1, 1, 0, 0, 1], [1, 0, 0, 1, 1], labels=[0, 1])
    assert matrix.tolist() == [[1, 1], [1, 2]]  # true0: TN,FP=1,1 ; true1: FN,TP=1,2


def test_confusion_matrix_default_labels_are_the_sorted_union() -> None:
    matrix = metrics.confusion_matrix([2, 0], [0, 2])
    assert matrix.shape == (2, 2)  # classes {0, 2}
    assert matrix.tolist() == [[0, 1], [1, 0]]  # each misclassified as the other


def test_confusion_matrix_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same shape"):
        metrics.confusion_matrix([1, 0], [1])


def test_positive_prob_softmax() -> None:
    assert metrics.positive_prob({0: 0.0, 1: 0.0}, 1) == pytest.approx(0.5)  # equal logits
    assert metrics.positive_prob({0: 0.0, 1: 100.0}, 1) == pytest.approx(1.0)  # class 1 dominates


def test_positive_prob_missing_class_raises() -> None:
    with pytest.raises(ValueError, match="not among"):
        metrics.positive_prob({0: 1.0}, 1)
