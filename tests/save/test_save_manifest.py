"""Tests for save.manifest — generic add / remove entries + write (B10a, B10d-0)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import FigureEntry, ObservationEntry, PhaseManifest, load_phase_dir

from myocard_egm_studio.save.manifest import (
    empty_manifest,
    remove_entry,
    save_manifest,
    with_entry,
)
from myocard_egm_studio.save.observation import build_observation, observation_entry


def _empty_manifest() -> PhaseManifest:
    return PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.0,
            "status": "in_progress",
            "phase_summary": "save-manifest test phase",
        }
    )


def _obs_entry(title: str) -> ObservationEntry:
    return observation_entry(build_observation(title=title, description="b", today="2026-07-04"))


def _fig_entry(fig_id: str) -> FigureEntry:
    return FigureEntry.model_validate(
        {
            "id": fig_id,
            "path": f"figures/{fig_id}.json",
            "produced_by_package": "egm-studio",
            "produced_by_version": "0.1.0",
            "consumes_banks": ["lpred_x_2026-06-27"],
            "usage_tag": "exploratory",
        }
    )


def test_empty_manifest_is_entry_less_in_progress(tmp_path: Path) -> None:
    manifest = empty_manifest(1.5)
    assert manifest.phase == 1.5
    assert manifest.status.value == "in_progress"
    assert manifest.observations is None and manifest.figures is None and manifest.egm_banks is None
    reloaded = load_phase_dir(save_manifest(manifest, tmp_path).parent)
    assert reloaded.phase == 1.5  # round-trips through the writer


def test_with_entry_appends() -> None:
    updated = with_entry(_empty_manifest(), "observations", _obs_entry("first"))
    assert [e.id for e in updated.observations or []] == ["obs_first_2026-07-04"]


def test_with_entry_replaces_same_id() -> None:
    manifest = with_entry(_empty_manifest(), "observations", _obs_entry("note"))
    again = with_entry(
        manifest,
        "observations",
        observation_entry(
            build_observation(title="note", description="edited", today="2026-07-04"),
            usage_notes="v2",
        ),
    )
    entries = again.observations or []
    assert len(entries) == 1  # replaced, not duplicated
    assert entries[0].usage_notes == "v2"


def test_with_entry_targets_the_named_section() -> None:
    updated = with_entry(_empty_manifest(), "figures", _fig_entry("fig_x"))
    assert [e.id for e in updated.figures or []] == ["fig_x"]
    assert not updated.observations  # a different section is untouched


def test_remove_entry_drops_the_matching_id() -> None:
    manifest = with_entry(_empty_manifest(), "figures", _fig_entry("fig_x"))
    manifest = with_entry(manifest, "figures", _fig_entry("fig_y"))
    pruned = remove_entry(manifest, "figures", "fig_x")
    assert [e.id for e in pruned.figures or []] == ["fig_y"]


def test_remove_entry_empties_the_section_to_none() -> None:
    manifest = with_entry(_empty_manifest(), "observations", _obs_entry("only"))
    pruned = remove_entry(manifest, "observations", "obs_only_2026-07-04")
    assert pruned.observations is None  # last one removed -> section cleared, not []


def test_save_manifest_round_trips(tmp_path: Path) -> None:
    manifest = with_entry(_empty_manifest(), "observations", _obs_entry("note"))
    written = save_manifest(manifest, tmp_path)
    assert written == tmp_path / "manifest.json"
    reloaded = load_phase_dir(tmp_path)
    assert [e.id for e in reloaded.observations or []] == ["obs_note_2026-07-04"]
