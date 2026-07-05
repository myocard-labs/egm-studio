"""Tests for save.observation — build + write an Observation (B10a)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import References, TraceRef, ViewState, load_observation

from myocard_egm_studio.save.observation import (
    build_observation,
    observation_entry,
    observation_path,
    references_from,
    save_observation,
    update_observation,
)


def test_build_observation_generates_id_and_date() -> None:
    obs = build_observation(title="AF near LSPV", description="Noticed X.", today="2026-07-04")
    assert obs.id == "obs_af_near_lspv_2026-07-04"
    assert obs.date.isoformat() == "2026-07-04"
    assert obs.title == "AF near LSPV"
    assert obs.description == "Noticed X."
    assert obs.traces is None and obs.view_state is None  # optional, omitted


def test_build_observation_carries_traces_and_view_state() -> None:
    obs = build_observation(
        title="note",
        description="body",
        view_state=ViewState.model_validate(
            {"banks_loaded": ["lpred_x_2026-06-27"], "filter": "peak_to_peak > 1"}
        ),
        traces=[TraceRef(bank="lpred_x_2026-06-27", index=3)],
        references=References.model_validate({"models": ["model_v1_baseline_bin_1_2026-06-27"]}),
        today="2026-07-04",
    )
    assert [t.index for t in obs.traces or []] == [3]
    assert obs.view_state is not None
    assert obs.view_state.model_dump()["banks_loaded"] == ["lpred_x_2026-06-27"]
    assert obs.references is not None
    assert obs.references.model_dump()["models"] == ["model_v1_baseline_bin_1_2026-06-27"]


def test_references_from_builds_parent_links() -> None:
    assert references_from() is None  # nothing to link -> no references block
    refs = references_from(observations=["obs_saturation_iafdb_2026-06-26"])
    assert refs is not None
    dumped = refs.model_dump()
    assert dumped["observations"] == ["obs_saturation_iafdb_2026-06-26"]
    assert dumped["models"] is None  # models omitted when not given


def test_update_observation_keeps_id_date_and_reload_state() -> None:
    original = build_observation(
        title="First",
        description="first prose",
        view_state=ViewState.model_validate({"banks_loaded": ["lpred_x_2026-06-27"]}),
        traces=[TraceRef(bank="lpred_x_2026-06-27", index=2)],
        today="2026-07-04",
    )
    edited = update_observation(
        original,
        title="First (revised)",
        description="second prose",
        references=references_from(observations=["obs_saturation_iafdb_2026-06-26"]),
    )
    assert edited.id == original.id  # stable key preserved
    assert edited.date == original.date
    assert edited.title == "First (revised)" and edited.description == "second prose"
    assert edited.view_state == original.view_state  # reload state untouched
    assert [t.index for t in edited.traces or []] == [2]
    assert edited.references is not None
    assert edited.references.model_dump()["observations"] == ["obs_saturation_iafdb_2026-06-26"]


def test_update_observation_can_clear_parent_links() -> None:
    original = build_observation(
        title="Has parents",
        description="p",
        references=references_from(observations=["obs_a_2026-06-27"]),
        today="2026-07-04",
    )
    edited = update_observation(original, title="Has parents", description="p", references=None)
    assert edited.references is None  # cleared


def test_save_observation_round_trips(tmp_path: Path) -> None:
    obs = build_observation(title="my note", description="body", today="2026-07-04")
    written = save_observation(obs, tmp_path)
    assert written == observation_path(obs, tmp_path)
    assert written == tmp_path / "observations" / "obs_my_note_2026-07-04.json"
    assert load_observation(written) == obs


def test_observation_entry_points_at_the_file(tmp_path: Path) -> None:
    obs = build_observation(title="my note", description="body", today="2026-07-04")
    entry = observation_entry(obs, usage_notes="from Flow A")
    assert entry.id == obs.id
    assert entry.path == "observations/obs_my_note_2026-07-04.json"  # relative to the phase dir
    assert entry.produced_by_package == "egm-studio"
    assert entry.usage_tag is not None and entry.usage_tag.value == "exploratory"
    assert entry.usage_notes == "from Flow A"
