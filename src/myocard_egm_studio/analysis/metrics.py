"""ROC / AUROC + calibration metrics for the synthetic-val classifier figures.

Pure numpy / scipy, like :mod:`.distributions` — the math behind
``roc-curve-multi-line`` and ``calibration-reliability-diagram`` (the confusion
recipes follow). No sklearn: ROC is a sort over the predicted probabilities,
AUROC is a rank statistic, and a reliability curve is a binning — all small
enough to own here, which keeps the dependency surface lean and matches the
analysis layer's numpy/scipy-only rule.

Everything here is computed on **labeled** data (the synthetic held-out
validation set). IAFDB has no fibrosis ground truth, so none of these apply to
it [[feedback-iafdb-unlabeled-no-ml-validation]].

Binary (one-vs-rest) framing: ``positive_label`` picks the positive class, so
``y_true == positive_label`` is the binary truth and ``y_pred_prob`` is that
class's predicted probability (in our pipeline, ``PredictionGroup.probs``).
Mathematically ROC only needs a value that *ranks* the traces, so a logit would
serve too — but we always pass the probability, hence the concrete name.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats

__all__ = ["auroc", "expected_calibration_error", "reliability_curve", "roc_curve"]


def _binary_truth_and_prob(
    y_true: ArrayLike, y_pred_prob: ArrayLike, *, positive_label: int
) -> tuple[NDArray[np.bool_], NDArray[np.float64]]:
    """Coerce to (positive-class mask, float probabilities); require both classes present."""
    truth = np.asarray(y_true)
    pred_prob = np.asarray(y_pred_prob, dtype=np.float64)
    if truth.shape != pred_prob.shape:
        raise ValueError(
            f"y_true {truth.shape} and y_pred_prob {pred_prob.shape} must have the same shape."
        )
    positive = truth == positive_label
    n_pos = int(positive.sum())
    if n_pos == 0 or n_pos == positive.size:
        raise ValueError(
            "ROC / AUROC need both a positive and a negative class present; "
            f"positive_label={positive_label!r} gave {n_pos} of {positive.size}."
        )
    return positive, pred_prob


def roc_curve(
    y_true: ArrayLike, y_pred_prob: ArrayLike, *, positive_label: int = 1
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Receiver-operating-characteristic curve as ``(fpr, tpr)``.

    Thresholds sweep the distinct predicted probabilities from high to low; ties
    collapse to a single vertex, and the curve is anchored at ``(0, 0)``.
    ``positive_label`` selects the positive class (one-vs-rest), so this serves
    the binary v1 model and extends to a multi-class head. Raises
    :class:`ValueError` if only one class is present.
    """
    positive, pred_prob = _binary_truth_and_prob(y_true, y_pred_prob, positive_label=positive_label)
    order = np.argsort(-pred_prob, kind="mergesort")  # stable, descending probability
    pos_sorted = positive[order].astype(np.int64)
    prob_sorted = pred_prob[order]
    # One ROC vertex per distinct probability (collapse ties), plus the final point.
    distinct = np.where(np.diff(prob_sorted) != 0)[0]
    vertices = np.r_[distinct, prob_sorted.size - 1]
    tps = np.cumsum(pos_sorted)[vertices]
    fps = np.cumsum(1 - pos_sorted)[vertices]
    n_pos = int(positive.sum())
    n_neg = int(positive.size - n_pos)
    tpr = np.r_[0.0, tps / n_pos]
    fpr = np.r_[0.0, fps / n_neg]
    return fpr, tpr


def auroc(y_true: ArrayLike, y_pred_prob: ArrayLike, *, positive_label: int = 1) -> float:
    """Area under the ROC curve via the rank (Mann-Whitney U) identity.

    ``AUROC = P(a positive trace's predicted probability > a negative trace's)``,
    made tie-aware through average ranks — exact, and independent of how the
    curve samples thresholds. In ``[0, 1]``: 1 = perfect separation, 0.5 =
    chance, 0 = perfectly inverted.
    """
    positive, pred_prob = _binary_truth_and_prob(y_true, y_pred_prob, positive_label=positive_label)
    ranks = stats.rankdata(pred_prob)  # average ranks resolve tied probabilities
    n_pos = int(positive.sum())
    n_neg = int(positive.size - n_pos)
    rank_sum = float(ranks[positive].sum())
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def reliability_curve(
    y_true: ArrayLike,
    y_pred_prob: ArrayLike,
    *,
    positive_label: int = 1,
    n_bins: int = 10,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
    """Reliability-diagram bins as ``(mean_pred, obs_freq, count)``.

    Partitions ``[0, 1]`` into ``n_bins`` equal-width bins and, for each
    *non-empty* bin, returns the mean predicted probability, the observed
    positive fraction, and the sample count — the points a reliability diagram
    plots against the ``y = x`` perfect-calibration line. Empty bins are dropped
    (no point to draw). ``positive_label`` / single-class handling match
    :func:`roc_curve`.
    """
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins}.")
    positive, pred_prob = _binary_truth_and_prob(y_true, y_pred_prob, positive_label=positive_label)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    binning = np.clip(np.digitize(pred_prob, edges[1:-1]), 0, n_bins - 1)
    count = np.bincount(binning, minlength=n_bins)
    sum_pred = np.bincount(binning, weights=pred_prob, minlength=n_bins)
    sum_pos = np.bincount(binning, weights=positive.astype(np.float64), minlength=n_bins)
    nonempty = count > 0
    mean_pred = sum_pred[nonempty] / count[nonempty]
    obs_freq = sum_pos[nonempty] / count[nonempty]
    return mean_pred, obs_freq, count[nonempty].astype(np.int64)


def expected_calibration_error(
    y_true: ArrayLike,
    y_pred_prob: ArrayLike,
    *,
    positive_label: int = 1,
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error — the bin-count-weighted mean gap to ``y = x``.

    ``ECE = sum_b (n_b / N) * |obs_freq_b - mean_pred_b|`` over the reliability
    bins (:func:`reliability_curve`). 0 = perfectly calibrated; larger means the
    predicted probabilities drift further from the observed frequencies.
    """
    mean_pred, obs_freq, count = reliability_curve(
        y_true, y_pred_prob, positive_label=positive_label, n_bins=n_bins
    )
    total = int(count.sum())
    return float(np.sum(count / total * np.abs(obs_freq - mean_pred)))
