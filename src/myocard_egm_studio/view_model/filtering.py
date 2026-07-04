"""Composable filtering over the per-trace view-model (Block 7, ADR-002).

The heart of the filter-by-feature-delta view pattern, kept pure so it is
unit-testable without Qt: a :class:`FilterSpec` is a flat list of
:class:`Condition` (column / operator / value) combined by one ``and`` / ``or``,
and :func:`apply_filter` turns it into a boolean row mask over a view-model
DataFrame. The Qt widget (``gui/widgets/filter.py``) edits a ``FilterSpec`` and
the result list applies it — the widget stays dumb.

:func:`filter_columns` describes which columns the UI offers and how (numeric ->
threshold ops; categorical -> equality against known values), hiding the
plumbing identity columns. Numeric ops on a categorical column (or vice versa)
are rejected by the operator set, so the widget can't build an invalid spec.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pandas.api.types import is_numeric_dtype

#: Operators offered per column kind. Categorical is equality only.
NUMERIC_OPS: tuple[str, ...] = (">", ">=", "<", "<=", "==", "!=")
CATEGORICAL_OPS: tuple[str, ...] = ("==", "!=")

#: View-model plumbing columns the filter never offers (identity wiring, not
#: analysis axes). label_name / source / split + the features + metadata remain.
_HIDDEN_COLUMNS = frozenset(
    {"trace_idx", "row_id", "source_bank_id", "source_bank_type", "amp_type", "label"}
)


@dataclass(frozen=True)
class FilterColumn:
    """A column the filter offers: numeric (thresholds) or categorical (equality)."""

    name: str
    numeric: bool
    choices: tuple[str, ...] = ()  # sorted distinct values, for a categorical column

    @property
    def ops(self) -> tuple[str, ...]:
        return NUMERIC_OPS if self.numeric else CATEGORICAL_OPS


@dataclass(frozen=True)
class Condition:
    """One ``column op value`` clause (value is raw text, coerced at apply time)."""

    column: str
    op: str
    value: str


@dataclass(frozen=True)
class FilterSpec:
    """A flat set of conditions combined by one ``and`` / ``or``."""

    conditions: tuple[Condition, ...] = ()
    combine: str = "and"  # "and" | "or"


def filter_columns(df: pd.DataFrame) -> list[FilterColumn]:
    """The columns the filter UI offers for ``df``, classified numeric / categorical.

    Numeric columns get threshold operators; non-numeric ones get equality against
    their sorted distinct values. Plumbing identity columns are hidden, and a
    categorical column with no non-null values is dropped (nothing to match).
    """
    columns: list[FilterColumn] = []
    for name in df.columns:
        if name in _HIDDEN_COLUMNS:
            continue
        series = df[name]
        if is_numeric_dtype(series):
            columns.append(FilterColumn(name, numeric=True))
            continue
        choices = tuple(sorted({str(v) for v in series.dropna().unique()}))
        if choices:
            columns.append(FilterColumn(name, numeric=False, choices=choices))
    return columns


def apply_filter(df: pd.DataFrame, spec: FilterSpec) -> pd.Series[bool]:
    """A boolean row mask for ``df``: every condition combined by ``spec.combine``.

    An empty spec matches every row. Missing values never match (a NaN feature or
    an unlabeled row is excluded by any condition on that column).
    """
    if not spec.conditions:
        return pd.Series(True, index=df.index)
    masks = [_condition_mask(df, condition) for condition in spec.conditions]
    combined = masks[0]
    for mask in masks[1:]:
        combined = combined | mask if spec.combine == "or" else combined & mask
    return combined


def _condition_mask(df: pd.DataFrame, condition: Condition) -> pd.Series[bool]:
    if condition.column not in df.columns:
        raise KeyError(f"filter column {condition.column!r} is not in the view-model")
    series = df[condition.column]
    if is_numeric_dtype(series):
        return _numeric_mask(series, condition.op, _as_float(condition))
    text = series.astype("string")
    if condition.op == "==":
        return (text == condition.value).fillna(False)
    if condition.op == "!=":
        return (text != condition.value).fillna(False)
    raise ValueError(
        f"operator {condition.op!r} needs a numeric column; {condition.column!r} is categorical"
    )


def _as_float(condition: Condition) -> float:
    try:
        return float(condition.value)
    except ValueError as exc:
        raise ValueError(
            f"non-numeric value {condition.value!r} for numeric column {condition.column!r}"
        ) from exc


def _numeric_mask(series: pd.Series[float], op: str, value: float) -> pd.Series[bool]:
    ops: dict[str, pd.Series[bool]] = {
        ">": series > value,
        ">=": series >= value,
        "<": series < value,
        "<=": series <= value,
        "==": series == value,
        "!=": series != value,
    }
    if op not in ops:
        raise ValueError(f"unknown operator {op!r}")
    return ops[op]
