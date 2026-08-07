"""Unit tests for combine_view_models (multi-bank concat + global row_id)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from myocard_egm_studio.view_model import ROW_ID, combine_view_models


def _frame(source: str, trace_idxs: list[int], extra: dict[str, Any] | None = None) -> pd.DataFrame:
    data: dict[str, object] = {
        "trace_idx": list(trace_idxs),
        "source": source,
        "sample_entropy": [float(i) for i in trace_idxs],
    }
    if extra:
        data.update(extra)
    return pd.DataFrame(data)


def test_row_id_is_unique_and_ordered() -> None:
    """Two banks concatenate in order; row_id is the global 0..total-1 key while
    trace_idx stays each bank's own index."""
    combined = combine_view_models([_frame("A", [0, 1, 2]), _frame("B", [0, 1])])
    assert list(combined[ROW_ID]) == [0, 1, 2, 3, 4]
    assert list(combined["trace_idx"]) == [0, 1, 2, 0, 1]
    assert list(combined["source"]) == ["A", "A", "A", "B", "B"]


def test_single_frame_gains_row_id() -> None:
    combined = combine_view_models([_frame("A", [0, 1, 2])])
    assert list(combined[ROW_ID]) == [0, 1, 2]
    assert list(combined["trace_idx"]) == [0, 1, 2]


def test_differing_metadata_columns_union() -> None:
    """Banks with different metadata keys union their columns; missing cells NaN."""
    a = _frame("A", [0, 1], extra={"patient_id": ["P0", "P1"]})
    b = _frame("B", [0], extra={"pair_index": [5]})
    combined = combine_view_models([a, b])
    assert {"patient_id", "pair_index"}.issubset(combined.columns)
    assert pd.isna(combined.loc[combined[ROW_ID] == 2, "patient_id"]).all()  # B lacks patient_id


def test_empty_input_yields_empty_frame_with_row_id() -> None:
    combined = combine_view_models([])
    assert list(combined.columns) == [ROW_ID]
    assert len(combined.index) == 0
