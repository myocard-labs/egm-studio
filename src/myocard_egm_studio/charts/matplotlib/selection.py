"""Shared figure-spec ``layout.features`` selection.

Several recipes/loaders let a figure_spec curate which egm-features to use — which
panels ``feature-distribution-overlay`` draws, which columns feed the
``bar-chart-with-deltas`` distance — and they all parse ``layout.features`` the
same way. That parser lives here once so the two stay in lockstep.

It sits in ``charts/matplotlib`` because both the recipe (here) and the loader
(``figures/loaders``, which already imports this package's inputs) can reach it
without crossing an import boundary.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

__all__ = ["select_layout_features"]


def select_layout_features(spec: FigureSpec, available: Sequence[str]) -> list[str]:
    """The ``spec.layout["features"]`` subset of ``available``, validated.

    An explicit ordered subset is filtered to ``available`` (preserving the
    requested order); unknown names warn and are skipped; an all-unknown list
    errors; an absent key returns all of ``available`` (as a list, in order).
    """
    requested = (spec.layout or {}).get("features")
    if requested is None:
        return list(available)
    if not isinstance(requested, list):
        raise ValueError("layout.features must be a list of feature names.")
    present = set(available)
    selected = [f for f in requested if f in present]
    if not selected:  # all-unknown is an error, not a warn-and-continue
        raise ValueError(f"none of the requested layout.features are available: {sorted(present)}.")
    unknown = [f for f in requested if f not in present]
    if unknown:  # partial miss: keep the valid ones, but surface the typo
        warnings.warn(
            f"unknown layout.features {unknown}; available: {sorted(present)}. Skipping them.",
            stacklevel=2,
        )
    return selected
