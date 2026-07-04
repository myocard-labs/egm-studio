"""Per-trace detail — the feature + metadata values behind a selected trace (Block 7).

The signal-exploration detail pane pairs each selected trace's waveform with a
focused read of its numbers: the 11 egm-features (with amplitude-aware units) and
its metadata (label, source, split, and the producer's provenance keys). This is
pure — it projects the view-model DataFrame rows for the selected ``row_id`` (the
multi-bank global key, B7.8) into a display structure; the Qt table just renders
it. Multiple selected traces become side-by-side value columns (the seed of the
B7.10 compare view).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from myocard_egm_studio.view_model.builder import FEATURE_COLUMNS, feature_units

# Plumbing identity columns never shown as metadata; features are listed separately.
_HIDDEN = frozenset(
    {"trace_idx", "row_id", "source_bank_id", "source_bank_type", "amp_type", "label"}
)
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


def trace_detail(frame: pd.DataFrame, row_ids: Sequence[int]) -> TraceDetail:
    """Project ``frame`` rows for the selected ``row_ids`` into feature + metadata rows.

    Rows are selected by the global ``row_id``; each column header still shows the
    row's own bank-relative ``trace_idx`` as ``#`` (so it matches the result list).
    """
    rows = _rows_for(frame, row_ids)
    headers = tuple(f"#{int(row['trace_idx'])}" for row in rows)
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


def _rows_for(frame: pd.DataFrame, row_ids: Sequence[int]) -> list[pd.Series]:
    by_id = frame.set_index("row_id")
    return [by_id.loc[row_id] for row_id in row_ids if row_id in by_id.index]


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
