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

from myocard_egm_studio.charts.inputs import FeatureGroup, ScatterSeries
from myocard_egm_studio.view_model import FEATURE_COLUMNS, ROW_ID, feature_units

__all__ = [
    "feature_group_from_frame",
    "feature_groups_by_source",
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


def _first(frame: pd.DataFrame, column: str) -> str | None:
    """First non-null value of a column as ``str``, or None."""
    if column not in frame.columns:
        return None
    non_null = frame[column].dropna()
    return str(non_null.iloc[0]) if not non_null.empty else None
