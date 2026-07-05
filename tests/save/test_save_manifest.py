"""Tests for save.manifest — add entries to a phase manifest + write it (B10a)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import FigureEntry, ObservationEntry, PhaseManifest, load_phase_dir

from myocard_egm_studio.save.manifest import save_manifest, with_figure, with_observation
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


def test_with_observation_appends() -> None:
    updated = with_observation(_empty_manifest(), _obs_entry("first"))
    assert [e.id for e in updated.observations or []] == ["obs_first_2026-07-04"]


def test_with_observation_replaces_same_id() -> None:
    manifest = with_observation(_empty_manifest(), _obs_entry("note"))
    again = with_observation(
        manifest,
        observation_entry(
            build_observation(title="note", description="edited", today="2026-07-04"),
            usage_notes="v2",
        ),
    )
    entries = again.observations or []
    assert len(entries) == 1  # replaced, not duplicated
    assert entries[0].usage_notes == "v2"


def test_with_figure_appends() -> None:
    entry = FigureEntry.model_validate(
        {
            "id": "fig_x",
            "path": "figure_specs/fig_x.json",
            "produced_by_package": "egm-studio",
            "produced_by_version": "0.1.0",
            "consumes_banks": ["lpred_x_2026-06-27"],
            "usage_tag": "exploratory",
        }
    )
    updated = with_figure(_empty_manifest(), entry)
    assert [e.id for e in updated.figures or []] == ["fig_x"]


def test_save_manifest_round_trips(tmp_path: Path) -> None:
    manifest = with_observation(_empty_manifest(), _obs_entry("note"))
    written = save_manifest(manifest, tmp_path)
    assert written == tmp_path / "manifest.json"
    reloaded = load_phase_dir(tmp_path)
    assert [e.id for e in reloaded.observations or []] == ["obs_note_2026-07-04"]
