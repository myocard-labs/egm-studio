"""Shared figure-spec list selection (``layout.features``, ``layout.fields``, ...).

Several recipes/loaders let a figure_spec curate an ordered subset of some fixed
set — which egm-features ``feature-distribution-overlay`` panels / the
``bar-chart-with-deltas`` distance uses (``layout.features``), which provenance
fields the ``summary-table`` curation loader shows (``layout.fields``) — and they
all parse the list the same way: default to all, keep the requested order, warn
on unknown names, error if none match. That parser lives here once
(:func:`select_from_available`) so every call site stays in lockstep;
:func:`select_layout_features` is the thin ``layout.features`` reader.

It sits in ``charts/matplotlib`` because both the recipes (here) and the loaders
(``figures/loaders``, which already imports this package) can reach it without
crossing an import boundary.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

__all__ = ["select_from_available", "select_layout_features"]


def select_from_available(
    requested: object, available: Sequence[str], *, what: str, stacklevel: int = 2
) -> list[str]:
    """Ordered subset of ``available`` named by ``requested``; default to all.

    ``requested`` is the raw spec value: a list of names (filtered to
    ``available``, preserving the requested order), or ``None`` to take all of
    ``available`` in order. Unknown names warn and are skipped; an all-unknown
    list errors; a non-list, non-``None`` value errors. ``what`` names the config
    key for the messages (e.g. ``"layout.features"``); ``stacklevel`` is forwarded
    to the warning so it blames the caller's call site rather than this helper.
    """
    if requested is None:
        return list(available)
    if not isinstance(requested, list):
        raise ValueError(f"{what} must be a list.")
    present = set(available)
    selected = [x for x in requested if x in present]
    if not selected:  # all-unknown is an error, not a warn-and-continue
        raise ValueError(f"none of the requested {what} are available: {sorted(present)}.")
    unknown = [x for x in requested if x not in present]
    if unknown:  # partial miss: keep the valid ones, but surface the typo
        warnings.warn(
            f"unknown {what} {unknown}; available: {sorted(present)}. Skipping them.",
            stacklevel=stacklevel,
        )
    return selected


def select_layout_features(spec: FigureSpec, available: Sequence[str]) -> list[str]:
    """The ``spec.layout['features']`` subset of ``available``, validated.

    Thin :func:`select_from_available` reader for the ``layout.features`` key —
    used by ``feature-distribution-overlay`` (which panels) and the
    ``bar-chart-with-deltas`` distance loader (which feature columns).
    """
    return select_from_available(
        (spec.layout or {}).get("features"), available, what="layout.features", stacklevel=3
    )
