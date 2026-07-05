"""Capture the live GUI state into an Observation's optional reload fields (Block 10b).

An observation can carry a ``view_state`` (banks loaded + filter + sort + which traces
were selected) and a ``traces`` list, so the noticing can be reopened later. This turns
the current view-model frame + applied filter + selection into those egm-contracts models
— best-effort and Qt-free (pandas + FilterSpec in, contracts models out).

The frame's ``source`` column is the bank's stable id (``gui.sources`` defaults it to
``bank.id``). Both ``banks_loaded`` and ``TraceRef.bank`` are pattern-validated
ArtifactIds, so a source that isn't one (a raw bank keyed by its file stem) is skipped in
both — its trace's *position* is still recorded, just not a concrete reference.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from myocard_egm_data.phases import TraceRef, ViewState

from myocard_egm_studio.save.ids import validate_artifact_id
from myocard_egm_studio.view_model.combine import ROW_ID
from myocard_egm_studio.view_model.filtering import (
    CATEGORICAL_OPS,
    COMBINE_LABELS,
    NUMERIC_OPS,
    Condition,
    FilterSpec,
)

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["capture_view_state", "describe_filter", "parse_filter"]

_COMBINE_JOINER = {"and": " AND ", "or": " OR ", "and_present": " AND* "}
_COMBINE_BY_LABEL = {label: combine for combine, label in COMBINE_LABELS.items()}
_LABEL_SEP = ": "  # between the match-type label and the conditions body
_ALL_OPS = frozenset(NUMERIC_OPS) | frozenset(CATEGORICAL_OPS)


def describe_filter(spec: FilterSpec | None) -> str | None:
    """A one-line ``<match type>: col op value AND/OR …`` rendering (``None`` if empty).

    The match type (``Match all`` / ``Match any`` / ``Match all that exist``) is spelled
    out first so an observation records *how* the conditions combine even when there is a
    single condition (where no joiner would otherwise reveal it).
    """
    if spec is None or not spec.conditions:
        return None
    label = COMBINE_LABELS.get(spec.combine, COMBINE_LABELS["and"])
    joiner = _COMBINE_JOINER.get(spec.combine, " AND ")
    body = joiner.join(f"{c.column} {c.op} {c.value}" for c in spec.conditions)
    return f"{label}{_LABEL_SEP}{body}"


def _parse_condition(part: str) -> Condition | None:
    """Parse one ``column op value`` clause; ``None`` if the operator isn't recognised."""
    tokens = part.split(" ")
    if len(tokens) < 3 or tokens[1] not in _ALL_OPS:
        return None
    return Condition(column=tokens[0], op=tokens[1], value=" ".join(tokens[2:]))


def parse_filter(text: str | None) -> FilterSpec | None:
    """Best-effort inverse of :func:`describe_filter`: a spec, or ``None`` if not exact.

    ``view_state.filter`` is a human-readable string (egm-contracts has no structured
    filter field yet), so reloading it means re-parsing this module's own rendering. The
    leading ``<match type>: `` gives the combine mode; the rest splits on that mode's
    joiner. Only a spec that re-renders to *exactly* ``text`` is returned — an ambiguous
    value (or a string without the match-type prefix) yields ``None`` rather than a wrong
    filter, and the caller surfaces the raw text for the user to re-apply by hand.
    """
    if not text:
        return None
    label, sep, body = text.partition(_LABEL_SEP)
    combine = _COMBINE_BY_LABEL.get(label)
    if not sep or combine is None:
        return None
    joiner = _COMBINE_JOINER[combine]
    parts = body.split(joiner) if joiner in body else [body]
    conditions: list[Condition] = []
    for part in parts:
        condition = _parse_condition(part)
        if condition is None:
            return None
        conditions.append(condition)
    spec = FilterSpec(tuple(conditions), combine)
    return spec if describe_filter(spec) == text else None


def _valid_bank_id(value: object) -> bool:
    try:
        validate_artifact_id(str(value))
    except ValueError:
        return False
    return True


def capture_view_state(
    frame: pd.DataFrame,
    *,
    filter_spec: FilterSpec | None = None,
    sort: str | None = None,
    selected_row_ids: Sequence[int] = (),
) -> tuple[ViewState | None, list[TraceRef]]:
    """Build ``(view_state, traces)`` from the current (filtered) frame + selection.

    ``frame`` is the displayed view-model table; ``selected_row_ids`` are global
    ``row_id``s. Each selected row becomes a ``TraceRef(bank=source, index=trace_idx)``
    and its ordinal position within ``frame`` is recorded in the view state. Returns
    ``(None, [])`` when there is nothing to capture.
    """
    has_traces = {"source", "trace_idx", ROW_ID}.issubset(frame.columns)
    if not has_traces:
        return None, []

    banks_loaded = [s for s in dict.fromkeys(frame["source"]) if _valid_bank_id(s)]
    position_by_id = {row_id: i for i, row_id in enumerate(frame[ROW_ID])}
    by_id = frame.set_index(ROW_ID)

    traces: list[TraceRef] = []
    positions: list[int] = []
    for row_id in selected_row_ids:
        if row_id not in position_by_id:
            continue
        positions.append(position_by_id[row_id])  # position is recorded regardless
        row = by_id.loc[row_id]
        source = str(row["source"])
        if _valid_bank_id(source):  # a concrete TraceRef needs a valid ArtifactId bank
            traces.append(TraceRef(bank=source, index=int(row["trace_idx"])))

    filter_text = describe_filter(filter_spec)
    if not (banks_loaded or filter_text or sort or positions):
        return None, traces
    view_state = ViewState.model_validate(
        {
            "banks_loaded": banks_loaded or None,
            "filter": filter_text,
            "sort": sort,
            "selected_trace_indices_within_filter": positions or None,
        }
    )
    return view_state, traces
