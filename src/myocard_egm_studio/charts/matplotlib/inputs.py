"""Prepared recipe inputs — the data contract between loaders and recipes.

A recipe is pure plotting: it takes one of these already-prepared inputs (never
a bank path or a raw HDF5 file) plus the FigureSpec, and returns a Figure. The
headless renderer's data-loading step (Block 7) is what turns a spec's
``inputs.groups`` bank ids into these structures; until that lands, tests and
callers build them in memory.

These live next to the recipes that consume them (not in egm-contracts) because
they're egm-studio-internal figure-data shapes, not a cross-repo schema. One
input type per recipe family; more land as Block 3 adds recipes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["PredictionGroup"]


@dataclass(frozen=True)
class PredictionGroup:
    """One named group of model output probabilities for ``prediction-histogram``.

    Attributes
    ----------
    name
        Legend / panel label (e.g. ``"Synthetic val"``, ``"IAFDB"``).
    probs
        ``(N,)`` predicted probability of the positive class, in ``[0, 1]``.
    labels
        Optional ``(N,)`` integer truth labels. When present the recipe facets
        the histogram by class; ``None`` (the IAFDB shape) draws one
        distribution with no class split.
    label_names
        Optional ``{int: str}`` map for the class legend (e.g.
        ``{0: "healthy", 1: "fibrotic"}``). Used only when ``labels`` is set.
    """

    name: str
    probs: NDArray[np.float64]
    labels: NDArray[np.int64] | None = None
    label_names: dict[int, str] | None = None
