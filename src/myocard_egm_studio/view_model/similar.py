"""Find the nearest trace in each *other* bank along one feature (B7.10, ADR-020).

The view-model wrapper over ``analysis.similarity.nearest_along_feature``: it knows
the view-model's ``source`` + ``row_id`` columns, so it can answer "the IAFDB trace
most similar to this synthetic one" — per-feature only (ADR-020 defers a joint
metric). Given a source ``row_id`` and a feature, it returns the nearest trace in
each other ``source`` (one per bank, in load order), keyed by the global ``row_id``
so the detail view resolves them straight into the compare panes. Candidates come
from whatever frame is passed (the current filter result), so any active filter is
respected.
"""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.analysis.similarity import nearest_along_feature
from myocard_egm_studio.view_model.combine import ROW_ID


def similar_in_other_sources(frame: pd.DataFrame, source_row_id: int, feature: str) -> list[int]:
    """``row_id`` of the nearest trace to ``source_row_id`` in each other ``source``.

    One match per distinct ``source`` other than the source row's own, in
    first-appearance (load) order along ``feature`` (``|value - target|``). Empty when
    the source row isn't in ``frame``, its feature value is missing, or there are no
    other-source rows. Positional (``iloc``) results from the analysis primitive are
    mapped back to the global ``row_id``.
    """
    if ROW_ID not in frame.columns or "source" not in frame.columns or feature not in frame.columns:
        return []
    by_id = frame.set_index(ROW_ID)
    if source_row_id not in by_id.index:
        return []
    target = by_id.loc[source_row_id, feature]
    source = by_id.loc[source_row_id, "source"]
    if pd.isna(target):
        return []
    row_ids = frame[ROW_ID].to_numpy()
    others = [s for s in frame["source"].dropna().unique() if s != source]
    matches: list[int] = []
    for other in others:
        mask = (frame["source"] == other).to_numpy()
        try:
            position = nearest_along_feature(
                frame, feature=feature, target_value=float(target), candidate_mask=mask
            )
        except ValueError:
            continue  # no finite candidate in this source
        matches.append(int(row_ids[position]))
    return matches
