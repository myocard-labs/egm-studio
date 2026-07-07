"""Combine per-bank view-model frames into one multi-bank table (B7.8).

The GUI can load several banks at once; each is a per-trace view-model frame
(:func:`build_view_model`) whose ``trace_idx`` runs 0..N-1. Concatenating banks
collides ``trace_idx`` across them, so :func:`combine_view_models` stamps a unique
global ``row_id`` (:data:`ROW_ID`) — the key the GUI's result list + detail select
on — while ``trace_idx`` stays each bank's own index (shown as ``#``). The GUI runs
*every* loaded set through this (even a single bank) so that contract always has a
present, unique key; the figure path keeps using the raw per-bank frames.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

__all__ = ["ROW_ID", "combine_view_models"]

#: Global, unique-per-loaded-set row identity the GUI selection + detail key on.
ROW_ID = "row_id"


def combine_view_models(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate per-bank view-model ``frames`` and stamp a global ``row_id``.

    Rows keep source order (bank 0's rows, then bank 1's, ...), so ``row_id``
    (0..total-1) aligns with a traces list concatenated in the same order — the
    view resolves a selected ``row_id`` straight into that list. Differing bank
    metadata columns union (missing cells become NaN). One frame is handled too —
    it just gains ``row_id`` == its position; empty input yields an empty frame
    carrying the ``row_id`` column.
    """
    if not frames:
        return pd.DataFrame({ROW_ID: pd.Series([], dtype="int64")})
    combined = pd.concat(frames, ignore_index=True)
    combined[ROW_ID] = range(len(combined.index))
    return combined
