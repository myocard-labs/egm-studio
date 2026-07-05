"""Tests for save.capture — GUI state -> Observation view_state + traces (B10b)."""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.save.capture import capture_view_state, describe_filter, parse_filter
from myocard_egm_studio.view_model.filtering import Condition, FilterSpec


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": [10, 11, 12],
            "source": ["lpred_a_2026-06-27", "lpred_a_2026-06-27", "upred_b_2026-06-27"],
            "trace_idx": [0, 1, 0],
            "peak_to_peak": [1.0, 2.0, 3.0],
        }
    )


def test_describe_filter() -> None:
    assert describe_filter(None) is None
    assert describe_filter(FilterSpec(())) is None
    spec = FilterSpec((Condition("peak_to_peak", ">", "1"), Condition("source", "==", "v1")))
    assert describe_filter(spec) == "Match all: peak_to_peak > 1 AND source == v1"
    any_spec = FilterSpec((Condition("sample_entropy", ">", "1.5"),), combine="or")
    assert describe_filter(any_spec) == "Match any: sample_entropy > 1.5"  # single cond keeps type


def test_parse_filter_round_trips_every_combine() -> None:
    for spec in (
        FilterSpec((Condition("peak_to_peak", ">", "1.5"),)),
        FilterSpec((Condition("a", ">", "1"), Condition("source", "==", "v1")), combine="or"),
        FilterSpec((Condition("a", ">", "1"), Condition("b", "<", "2")), combine="and_present"),
    ):
        rendered = describe_filter(spec)
        assert parse_filter(rendered) == spec  # describe -> parse is an exact inverse


def test_parse_filter_rejects_the_unparseable() -> None:
    assert parse_filter(None) is None
    assert parse_filter("") is None
    assert parse_filter("peak_to_peak > 1.5") is None  # no match-type prefix -> can't reconstruct
    assert parse_filter("Bogus mode: a > 1") is None  # unknown match-type label
    assert parse_filter("Match all: just some words") is None  # 'some' is not a known operator


def test_capture_traces_and_positions_in_selection_order() -> None:
    spec = FilterSpec((Condition("peak_to_peak", ">", "0.5"),))
    view_state, traces = capture_view_state(_frame(), filter_spec=spec, selected_row_ids=[12, 10])

    assert [(t.bank, t.index) for t in traces] == [
        ("upred_b_2026-06-27", 0),  # row_id 12
        ("lpred_a_2026-06-27", 0),  # row_id 10
    ]
    assert view_state is not None
    dumped = view_state.model_dump()
    assert dumped["banks_loaded"] == ["lpred_a_2026-06-27", "upred_b_2026-06-27"]
    assert dumped["filter"] == "Match all: peak_to_peak > 0.5"
    assert dumped["selected_trace_indices_within_filter"] == [2, 0]  # positions within the frame


def test_capture_banks_loaded_even_without_a_selection() -> None:
    view_state, traces = capture_view_state(_frame())
    assert traces == []
    assert view_state is not None
    assert view_state.model_dump()["banks_loaded"] == ["lpred_a_2026-06-27", "upred_b_2026-06-27"]


def test_invalid_source_id_skips_the_traceref_but_keeps_the_position() -> None:
    frame = pd.DataFrame({"row_id": [1], "source": ["justafilestem"], "trace_idx": [0]})
    view_state, traces = capture_view_state(frame, selected_row_ids=[1])
    assert traces == []  # 'justafilestem' isn't a valid ArtifactId -> no concrete TraceRef
    assert view_state is not None
    dumped = view_state.model_dump()
    assert dumped["banks_loaded"] is None  # dropped there too
    assert dumped["selected_trace_indices_within_filter"] == [0]  # position still recorded


def test_nothing_to_capture_returns_none() -> None:
    frame = pd.DataFrame({"row_id": [1], "source": ["justafilestem"], "trace_idx": [0]})
    view_state, traces = capture_view_state(frame)  # no valid banks, no filter, no selection
    assert view_state is None
    assert traces == []
