"""Per-trace detail — the feature + metadata values behind a selected trace (Block 7).

The signal-exploration detail pane pairs each selected trace's waveform with a
focused read of its numbers: the 11 egm-features (with amplitude-aware units) and
its metadata (label, source, split, and the producer's provenance keys). This is
pure — it projects the view-model DataFrame rows for the selected ``trace_idx``
into a display structure; the Qt table just renders it. Multiple selected traces
become side-by-side value columns (the seed of the B7.10 compare view).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from myocard_egm_studio.view_model.builder import FEATURE_COLUMNS, feature_units

# Plumbing identity columns never shown as metadata; features are listed separately.
_HIDDEN = frozenset({"trace_idx", "source_bank_id", "source_bank_type", "amp_type", "label"})
# Metadata columns shown first (the rest follow in frame order).
_METADATA_LEAD = ("label_name", "source", "split")


@dataclass(frozen=True)
class DetailRow:
    """One attribute across the selected traces: its label, per-trace values, unit."""

    label: str
    values: tuple[str, ...]
    unit: str = ""


@dataclass(frozen=True)
class TraceDetail:
    """The detail table: per-trace column headers + the feature and metadata rows."""

    headers: tuple[str, ...]
    features: tuple[DetailRow, ...]
    metadata: tuple[DetailRow, ...]


def trace_detail(frame: pd.DataFrame, trace_indices: Sequence[int]) -> TraceDetail:
    """Project ``frame`` rows for ``trace_indices`` into feature + metadata rows."""
    rows = _rows_for(frame, trace_indices)
    headers = tuple(f"#{index}" for index in trace_indices)
    units = feature_units(rows[0].get("amp_type") if rows else None)
    features = tuple(
        DetailRow(column, tuple(_fmt(row.get(column)) for row in rows), units.get(column, ""))
        for column in FEATURE_COLUMNS
        if column in frame.columns
    )
    metadata = tuple(
        DetailRow(column, tuple(_fmt(row.get(column)) for row in rows))
        for column in _metadata_columns(frame)
    )
    return TraceDetail(headers=headers, features=features, metadata=metadata)


def _rows_for(frame: pd.DataFrame, trace_indices: Sequence[int]) -> list[pd.Series]:
    by_idx = frame.set_index("trace_idx")
    return [by_idx.loc[index] for index in trace_indices if index in by_idx.index]


def _metadata_columns(frame: pd.DataFrame) -> list[str]:
    shown = [c for c in frame.columns if c not in _HIDDEN and c not in FEATURE_COLUMNS]
    lead = [c for c in _METADATA_LEAD if c in shown]
    return lead + [c for c in shown if c not in lead]


def _fmt(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):  # includes numpy floats
        return str(int(value)) if value.is_integer() else f"{value:g}"
    return str(value)
