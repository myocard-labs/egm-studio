"""Build charts inputs from an in-memory view-model frame.

The single place that turns the per-trace view-model (identity + metadata +
egm-features columns) into the per-source charts inputs the distribution + scatter
charts consume — the feature-only :class:`FeatureGroup` and the id-carrying
:class:`ScatterSeries`. Shared by the figure loader
(:func:`..figure_inputs.load_feature_groups`, which builds the frame from a bank)
and the GUI's Flow A views (B7.7 summary, B7.9 scatter, which already hold the
frame), so both produce identical inputs.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from myocard_egm_studio.analysis.metrics import confusion_matrix
from myocard_egm_studio.charts.inputs import (
    ConfusionCounts,
    FeatureGroup,
    PredictionGroup,
    ScatterSeries,
)
from myocard_egm_studio.view_model import FEATURE_COLUMNS, ROW_ID, feature_units

__all__ = [
    "confusion_by_source",
    "confusion_from_frame",
    "feature_group_from_frame",
    "feature_groups_by_source",
    "prediction_group_from_frame",
    "prediction_groups_by_source",
    "scatter_series_by_source",
    "scatter_series_from_frame",
]


def _iter_sources(frame: pd.DataFrame) -> Iterator[tuple[str | None, pd.DataFrame]]:
    """Yield ``(source name, sub-frame)`` per distinct ``source``, in load order.

    A frame with no ``source`` column yields one ``(None, frame)`` — the single
    unnamed group — and ``None`` lets each builder apply its own default label.
    Sub-frames keep the parent's index, so a per-source slice still carries the
    global ``row_id`` the scatter needs.
    """
    if "source" not in frame.columns:
        yield None, frame
        return
    for source in frame["source"].dropna().unique():
        yield str(source), frame[frame["source"] == source]


def feature_groups_by_source(frame: pd.DataFrame) -> list[FeatureGroup]:
    """Split a (possibly multi-bank) frame into one FeatureGroup per ``source``.

    One group per distinct ``source``, in first-appearance (load) order — so group
    *i* is the *i*-th loaded bank and lines up with ``color_for(i)`` used by the
    summary overlay + the loaded-banks roster (B7.8c). A frame with no ``source``
    column collapses to a single unnamed group; an empty frame yields no groups.
    """
    if not len(frame.index):
        return []
    return [feature_group_from_frame(sub, name=name) for name, sub in _iter_sources(frame)]


def scatter_series_by_source(frame: pd.DataFrame) -> list[ScatterSeries]:
    """Split a (combined) frame into one :class:`ScatterSeries` per ``source``.

    The scatter analog of :func:`feature_groups_by_source`: same per-source split +
    load order (so series *i* matches ``color_for(i)``), but each series also carries
    the per-point ``row_id`` for click -> trace. Fed the GUI's combined frame (so
    ``row_id`` is present); an empty frame yields no series.
    """
    if not len(frame.index):
        return []
    return [scatter_series_from_frame(sub, name=name) for name, sub in _iter_sources(frame)]


def feature_group_from_frame(frame: pd.DataFrame, *, name: str | None = None) -> FeatureGroup:
    """Pull the 11 ``FEATURE_COLUMNS`` out of ``frame`` as one named FeatureGroup.

    ``name`` labels the group (legend / provenance); it defaults to the frame's
    ``source`` column (stamped by ``build_view_model(source=...)``), else the
    source bank id, else ``"bank"``. Units track the bank's ``amp_type`` via
    :func:`myocard_egm_studio.view_model.feature_units`, so ``peak_to_peak`` reads
    as ``mV`` only for a raw-mV bank. The frame must carry the feature columns
    (built with ``with_features=True``).
    """
    values = {col: frame[col].to_numpy(dtype=np.float64) for col in FEATURE_COLUMNS}
    label = name or _first(frame, "source") or _first(frame, "source_bank_id") or "bank"
    return FeatureGroup(name=label, values=values, units=feature_units(_first(frame, "amp_type")))


def scatter_series_from_frame(frame: pd.DataFrame, *, name: str | None = None) -> ScatterSeries:
    """Pull the 11 features + the ``row_id`` out of ``frame`` as one ScatterSeries.

    Mirrors :func:`feature_group_from_frame` (same feature columns, same ``name`` /
    ``units`` resolution) but also carries ``row_id`` as the per-point id — falling
    back to the frame's index when the column is absent (a non-combined frame, whose
    index still equals its position). The widget's axis pickers select (x, y) later.
    """
    values = {col: frame[col].to_numpy(dtype=np.float64) for col in FEATURE_COLUMNS}
    ids = (frame[ROW_ID] if ROW_ID in frame.columns else frame.index).to_numpy(dtype=np.int64)
    label = name or _first(frame, "source") or _first(frame, "source_bank_id") or "bank"
    return ScatterSeries(
        name=label, values=values, ids=ids, units=feature_units(_first(frame, "amp_type"))
    )


def prediction_groups_by_source(frame: pd.DataFrame) -> list[PredictionGroup]:
    """Split an evaluated frame into one :class:`PredictionGroup` per ``source``.

    The output-distribution analog of :func:`feature_groups_by_source`: same
    per-source split + load order (so group *i* matches ``color_for(i)`` used by the
    overlay + roster), but each group carries the source's ``predicted_prob`` (the
    B8a ML column) rather than the feature arrays. Fed the GUI's combined frame; an
    empty frame yields no groups.
    """
    if not len(frame.index):
        return []
    return [prediction_group_from_frame(sub, name=name) for name, sub in _iter_sources(frame)]


def prediction_group_from_frame(frame: pd.DataFrame, *, name: str | None = None) -> PredictionGroup:
    """Pull ``predicted_prob`` (+ truth, when present) out of ``frame`` as a PredictionGroup.

    ``name`` resolves as in :func:`feature_group_from_frame` (source, else source bank
    id, else ``"bank"``). The frame must carry ``predicted_prob`` (the ML-outcome join,
    B8a) — the caller (Flow B) only builds these for an evaluated set. When every row
    also carries a truth ``label``, ``labels`` + ``label_names`` are filled (so the ROC /
    calibration metric charts, B8f, can score the group); an unlabelled source (the IAFDB
    shape) leaves them ``None`` — the Output overlay uses only ``probs`` regardless.
    """
    label = name or _first(frame, "source") or _first(frame, "source_bank_id") or "bank"
    probs = frame["predicted_prob"].to_numpy(dtype=np.float64)
    labels: NDArray[np.int64] | None = None
    label_names: dict[int, str] | None = None
    if "label" in frame.columns and len(frame.index) and frame["label"].notna().all():
        labels = frame["label"].to_numpy(dtype=np.int64)
        label_names = _label_names(frame) or None
    return PredictionGroup(name=label, probs=probs, labels=labels, label_names=label_names)


def confusion_by_source(frame: pd.DataFrame, *, positive_label: int = 1) -> list[ConfusionCounts]:
    """One :class:`ConfusionCounts` per labelled source, in load order.

    The metrics view tiles these as small multiples (one matrix per source). A source
    without truth (the IAFDB shape) is skipped — a confusion matrix needs ground truth.
    ``positive_label`` is accepted for signature parity with the other metric builders;
    the matrix itself is multi-class-agnostic (it counts every class present).
    """
    if not len(frame.index):
        return []
    built = (confusion_from_frame(sub, name=name) for name, sub in _iter_sources(frame))
    return [counts for counts in built if counts is not None]


def confusion_from_frame(frame: pd.DataFrame, *, name: str | None = None) -> ConfusionCounts | None:
    """A source's confusion matrix from its ``label`` (truth) + ``predicted_class`` columns.

    ``None`` when the frame lacks either column or carries no truth-labelled row (nothing
    to score). Row / column classes are the sorted union present; display names come from
    the frame's ``label_name`` map, falling back to the integer class.
    """
    if not {"label", "predicted_class"}.issubset(frame.columns):
        return None
    scored = frame.dropna(subset=["label", "predicted_class"])
    if scored.empty:
        return None
    y_true = scored["label"].to_numpy(dtype=np.int64)
    y_pred = scored["predicted_class"].to_numpy(dtype=np.int64)
    classes = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    matrix = confusion_matrix(y_true, y_pred, labels=classes)
    names = _label_names(scored)
    display = [names.get(cls, str(cls)) for cls in classes]
    label = name or _first(scored, "source") or _first(scored, "source_bank_id") or "bank"
    return ConfusionCounts(name=label, matrix=matrix, labels=display)


def _label_names(frame: pd.DataFrame) -> dict[int, str]:
    """``{label -> label_name}`` from the frame's distinct labelled rows (empty if absent)."""
    if not {"label", "label_name"}.issubset(frame.columns):
        return {}
    pairs = frame.dropna(subset=["label", "label_name"])[["label", "label_name"]].drop_duplicates()
    return {int(row.label): str(row.label_name) for row in pairs.itertuples(index=False)}


def _first(frame: pd.DataFrame, column: str) -> str | None:
    """First non-null value of a column as ``str``, or None."""
    if column not in frame.columns:
        return None
    non_null = frame[column].dropna()
    return str(non_null.iloc[0]) if not non_null.empty else None
