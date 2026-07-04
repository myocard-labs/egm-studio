"""Model-output columns for an evaluated bank — the Flow B view-model join (Block 8).

When an *evaluated* ClassifierBank is loaded (every trace carries a ``prediction``),
Flow B needs per-trace ML outcomes alongside the features. This derives them;
:func:`..builder.build_view_model` appends them when the bank is evaluated, so the
filter / result list / similarity see ``predicted_prob`` etc. as ordinary columns.

Always set: ``predicted_prob`` (softmax P(positive)) + ``predicted_class``. Truth-
dependent (present only for traces carrying ``label_truth``, else NaN / None, so an
unlabeled IAFDB eval bank gets prob + class only): ``correctness_bucket`` (TP / TN /
FP / FN), ``per_trace_loss`` (binary cross-entropy), ``calibration_residual``
(``predicted_prob - truth``). A raw (unevaluated) bank yields ``None``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from myocard_egm_data.banks import ClassifierBank, ClassifierTrace

from myocard_egm_studio.analysis.metrics import positive_prob

#: The ML-outcome columns appended for an evaluated bank (the last three are
#: truth-dependent — filled only for a labelled eval bank).
ML_COLUMNS: tuple[str, ...] = (
    "predicted_prob",
    "predicted_class",
    "correctness_bucket",
    "per_trace_loss",
    "calibration_residual",
)

_EPS = 1e-7  # clamp probabilities off 0 / 1 so the log-loss stays finite


def ml_outcome_frame(bank: ClassifierBank, *, positive_label: int = 1) -> pd.DataFrame | None:
    """One row per trace of :data:`ML_COLUMNS`, or ``None`` if the bank isn't evaluated.

    ``None`` when any trace lacks a ``prediction`` (a raw bank — nothing to score).
    ``predicted_prob`` / ``predicted_class`` are always filled; the truth-dependent
    columns are NaN / None for a trace without ``label_truth``.
    """
    traces = bank.traces
    if not traces or any(trace.prediction is None for trace in traces):
        return None
    prob = np.array(
        [positive_prob(trace.prediction.pred_logits, positive_label) for trace in traces],  # type: ignore[union-attr]
        dtype=np.float64,
    )
    truth = np.array(
        [np.nan if trace.label_truth is None else float(trace.label_truth) for trace in traces]
    )
    clamped = np.clip(prob, _EPS, 1.0 - _EPS)
    return pd.DataFrame(
        {
            "predicted_prob": prob,
            "predicted_class": [trace.prediction.label_pred for trace in traces],  # type: ignore[union-attr]
            "correctness_bucket": [_bucket(trace, positive_label) for trace in traces],
            # binary cross-entropy; NaN propagates for an unlabeled (NaN-truth) trace
            "per_trace_loss": -(truth * np.log(clamped) + (1.0 - truth) * np.log(1.0 - clamped)),
            "calibration_residual": prob - truth,
        }
    )


def _bucket(trace: ClassifierTrace, positive_label: int) -> str | None:
    """TP / TN / FP / FN for a labelled trace; ``None`` when ``label_truth`` is absent."""
    if trace.label_truth is None or trace.prediction is None:
        return None
    truth_pos = trace.label_truth == positive_label
    pred_pos = trace.prediction.label_pred == positive_label
    if truth_pos:
        return "TP" if pred_pos else "FN"
    return "FP" if pred_pos else "TN"
