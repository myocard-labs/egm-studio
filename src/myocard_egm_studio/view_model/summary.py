"""Bank-summary view-model — the Flow A landing's stats (B7.7).

Pure and Qt-free: reduce the per-trace view-model frame to a small
:class:`BankSummary` (trace count, class balance, provenance) for the summary
panel. The 11-panel feature-distribution grid beside it is fed separately by
:func:`myocard_egm_studio.loaders.feature_group_from_frame`, which builds the
charts input from the same frame.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

__all__ = ["BankSummary", "bank_summary"]

#: Label used for traces without a class label (the IAFDB / unlabeled shape).
_UNLABELED = "unlabeled"


@dataclass(frozen=True)
class BankSummary:
    """Reduced bank stats for the Flow A summary landing.

    Attributes
    ----------
    n_traces
        Row count of the (unfiltered) view-model.
    class_balance
        ``(label_name, count)`` per class, ordered by descending count then
        name; a fully unlabeled bank reports a single ``("unlabeled", n)``.
    bank_ids / bank_types
        Distinct source bank id(s) + type(s) present — one each for a single
        bank, several once B7.8 loads multiple.
    amp_type
        The bank's amplitude convention (e.g. ``"mv"``), or None if absent.
    splits
        Distinct split tags present (train / val / test), ordered.
    """

    n_traces: int
    class_balance: tuple[tuple[str, int], ...]
    bank_ids: tuple[str, ...]
    bank_types: tuple[str, ...]
    amp_type: str | None
    splits: tuple[str, ...]


def bank_summary(frame: pd.DataFrame) -> BankSummary:
    """Reduce a per-trace view-model ``frame`` to its :class:`BankSummary`.

    Frame-only (no bank re-read): everything comes from the identity columns the
    builder emits, so returning to the summary costs nothing beyond the frame
    already in hand. A fully unlabeled bank collapses to a single ``unlabeled``
    class rather than raising.
    """
    n = len(frame.index)
    return BankSummary(
        n_traces=n,
        class_balance=_class_balance(frame) if n else (),
        bank_ids=_distinct(frame, "source_bank_id"),
        bank_types=_distinct(frame, "source_bank_type"),
        amp_type=_first(frame, "amp_type"),
        splits=_distinct(frame, "split"),
    )


def _class_balance(frame: pd.DataFrame) -> tuple[tuple[str, int], ...]:
    """``(label_name, count)`` per class, descending count then name; nulls -> unlabeled."""
    if "label_name" not in frame.columns:
        return ((_UNLABELED, len(frame.index)),)
    names = frame["label_name"].fillna(_UNLABELED).astype(str)
    items = [(str(name), int(count)) for name, count in names.value_counts().items()]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return tuple(items)


def _distinct(frame: pd.DataFrame, column: str) -> tuple[str, ...]:
    """Sorted distinct non-null string values of a column (empty if absent)."""
    if column not in frame.columns:
        return ()
    return tuple(sorted(str(v) for v in frame[column].dropna().unique()))


def _first(frame: pd.DataFrame, column: str) -> str | None:
    """First non-null value of a column as ``str``, or None."""
    if column not in frame.columns:
        return None
    non_null = frame[column].dropna()
    return str(non_null.iloc[0]) if not non_null.empty else None
