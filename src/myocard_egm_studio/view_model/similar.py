"""Per-feature similarity wrappers over ``analysis.similarity`` (ADR-020).

These know the view-model's ``source`` / ``row_id`` / ML-outcome columns, so they
express the diagnostic in view-model terms while the ranking math stays in the pure
``analysis`` layer (per-feature only; ADR-020 defers a joint metric). All take a
source ``row_id`` and a feature and return matches keyed by the global ``row_id`` so
the detail view resolves them straight into the compare panes; candidates come from
whatever frame is passed (the current filter result), so any active filter is respected.

- :func:`similar_in_other_sources` (Flow A, B7.10): nearest in each *other* bank.
- :func:`nearest_correct_pair` (Flow B, B8): a misclassification + its most-similar
  correctly-classified opposite-label counterpart.
- :func:`within_class_neighborhood` (Flow B, B8): an outlier + its k-nearest in-class peers.
"""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.analysis.similarity import nearest_along_feature, rank_by_feature_distance
from myocard_egm_studio.view_model.combine import ROW_ID

_CORRECT = ("TP", "TN")  # correctness_bucket values for a correctly-classified trace
_MISCLASSIFIED = ("FP", "FN")


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


def nearest_correct_pair(frame: pd.DataFrame, source_row_id: int, feature: str) -> int | None:
    """``row_id`` of the correctly-classified opposite-label trace nearest a misclassification.

    The "why did the model get this one wrong when this similar trace it got right?"
    diagnostic (Flow B, B8): given a *misclassified* ``source_row_id`` (correctness_bucket
    FP / FN), find the nearest trace along ``feature`` that is both correctly classified
    (TP / TN) and of the opposite truth ``label``. ``None`` when the source isn't in
    ``frame``, isn't itself a misclassification, its feature value is missing, or no such
    candidate exists. Needs a labelled eval bank (``correctness_bucket`` + ``label``).
    """
    if not {ROW_ID, "correctness_bucket", "label", feature}.issubset(frame.columns):
        return None
    by_id = frame.set_index(ROW_ID)
    if source_row_id not in by_id.index:
        return None
    source = by_id.loc[source_row_id]
    if source["correctness_bucket"] not in _MISCLASSIFIED or pd.isna(source[feature]):
        return None
    mask = (
        frame["correctness_bucket"].isin(_CORRECT) & (frame["label"] != source["label"])
    ).to_numpy()
    try:
        position = nearest_along_feature(
            frame, feature=feature, target_value=float(source[feature]), candidate_mask=mask
        )
    except ValueError:
        return None  # no correctly-classified opposite-label candidate
    return int(frame[ROW_ID].to_numpy()[position])


def within_class_neighborhood(
    frame: pd.DataFrame, source_row_id: int, feature: str, *, k: int = 2
) -> list[int]:
    """``row_id``s of the ``k`` nearest same-truth-label traces to ``source_row_id``.

    An outlier vs its in-class peers (Flow B, B8): the ``k`` nearest traces along
    ``feature`` that share the source's truth ``label`` (the source itself excluded),
    closest first. Empty when the source isn't in ``frame``, its feature value / label
    is missing, or the frame lacks a ``label`` column.
    """
    if not {ROW_ID, "label", feature}.issubset(frame.columns):
        return []
    by_id = frame.set_index(ROW_ID)
    if source_row_id not in by_id.index:
        return []
    source = by_id.loc[source_row_id]
    if pd.isna(source[feature]) or pd.isna(source["label"]):
        return []
    mask = ((frame["label"] == source["label"]) & (frame[ROW_ID] != source_row_id)).to_numpy()
    ranked = rank_by_feature_distance(
        frame, feature=feature, target_value=float(source[feature]), candidate_mask=mask
    )
    row_ids = frame[ROW_ID].to_numpy()
    return [int(row_ids[position]) for position in ranked[:k]]
