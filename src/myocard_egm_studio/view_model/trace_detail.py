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
from myocard_egm_studio.view_model.ml_outcomes import ML_COLUMNS

# Plumbing identity columns never shown as metadata; features + ML outcomes are listed separately.
_HIDDEN = frozenset(
    {"trace_idx", "row_id", "source_bank_id", "source_bank_type", "amp_type", "label"}
)
# Metadata columns shown first (the rest follow in frame order).
_METADATA_LEAD = ("label_name", "source", "split")
# ML-outcome columns whose per-trace change vs the source is meaningful (continuous).
_ML_NUMERIC = frozenset({"predicted_prob", "per_trace_loss", "calibration_residual"})


@dataclass(frozen=True)
class DetailRow:
    """One attribute across the selected traces: label, per-trace values, unit, deltas.

    ``deltas`` (feature rows only) is the signed change of each column vs the first
    (the compare's source / left-most trace) — ``""`` for the source column, unitless
    metadata, and non-comparable (NaN) cells. It powers the B7.10 compare-with-deltas.
    """

    label: str
    values: tuple[str, ...]
    unit: str = ""
    deltas: tuple[str, ...] = ()


@dataclass(frozen=True)
class TraceDetail:
    """The detail table: per-trace column headers + feature, ML-outcome, and metadata rows."""

    headers: tuple[str, ...]
    features: tuple[DetailRow, ...]
    metadata: tuple[DetailRow, ...]
    ml: tuple[DetailRow, ...] = ()  # model-output rows (empty for a raw, unevaluated bank)


def trace_detail(frame: pd.DataFrame, row_ids: Sequence[int]) -> TraceDetail:
    """Project ``frame`` rows for the selected ``row_ids`` into feature + ML + metadata rows.

    Rows are selected by the global ``row_id``; each column header still shows the
    row's own bank-relative ``trace_idx`` as ``#`` (so it matches the result list). The
    ML-outcome section (B8g) is present only for an evaluated bank (its columns exist).
    """
    rows = _rows_for(frame, row_ids)
    headers = tuple(f"#{int(row['trace_idx'])}" for row in rows)
    units = feature_units(rows[0].get("amp_type") if rows else None)
    features = tuple(
        _feature_row(column, rows, units.get(column, ""))
        for column in FEATURE_COLUMNS
        if column in frame.columns
    )
    ml = tuple(_ml_row(column, rows) for column in ML_COLUMNS if column in frame.columns)
    metadata = tuple(
        DetailRow(column, tuple(_fmt(row.get(column)) for row in rows))
        for column in _metadata_columns(frame)
    )
    return TraceDetail(headers=headers, features=features, metadata=metadata, ml=ml)


def _ml_row(column: str, rows: list[pd.Series]) -> DetailRow:
    """An ML-outcome row: values + deltas vs the source for the continuous columns only."""
    raw = [row.get(column) for row in rows]
    deltas = _deltas(raw) if column in _ML_NUMERIC else ()
    return DetailRow(column, tuple(_fmt(v) for v in raw), "", deltas)


def _feature_row(column: str, rows: list[pd.Series], unit: str) -> DetailRow:
    """A feature row: formatted per-trace values + each column's delta vs the first."""
    raw = [row.get(column) for row in rows]
    return DetailRow(column, tuple(_fmt(v) for v in raw), unit, _deltas(raw))


def _deltas(raw: list[Any]) -> tuple[str, ...]:
    """Signed change of each column vs the first; ``""`` for the first + non-finite cells."""
    if not raw:
        return ()
    base = raw[0]
    out = [""]  # the source column is the baseline — no delta
    for value in raw[1:]:
        if pd.isna(base) or pd.isna(value):
            out.append("")
        else:
            out.append(f"{float(value) - float(base):+g}")
    return tuple(out)


def _rows_for(frame: pd.DataFrame, row_ids: Sequence[int]) -> list[pd.Series]:
    by_id = frame.set_index("row_id")
    return [by_id.loc[row_id] for row_id in row_ids if row_id in by_id.index]


def _metadata_columns(frame: pd.DataFrame) -> list[str]:
    excluded = _HIDDEN | set(FEATURE_COLUMNS) | set(ML_COLUMNS)  # features + ML get own sections
    shown = [c for c in frame.columns if c not in excluded]
    lead = [c for c in _METADATA_LEAD if c in shown]
    return lead + [c for c in shown if c not in lead]


def _fmt(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):  # includes numpy floats
        return str(int(value)) if value.is_integer() else f"{value:g}"
    return str(value)
