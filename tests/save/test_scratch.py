"""Tests for save.scratch — the scratch area as a real (migrating) manifest (B10h-2a)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.save import (
    build_observation,
    load_scratch,
    save_figure_spec,
    save_observation,
    scratch_manifest_path,
)


def _figure() -> FigureSpec:
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_demo_2026-07-05",
            "description": "d",
            "recipe": "prediction-histogram",
            "inputs": {"groups": [{"name": "g", "bank_id": "lpred_a_2026-06-27"}]},
            "output": {"format": "pdf", "path": "out.pdf"},
        }
    )


def test_empty_scratch_has_no_entries_and_writes_nothing(tmp_path: Path) -> None:
    manifest = load_scratch(tmp_path / "nope")
    assert not manifest.observations and not manifest.figures
    assert not scratch_manifest_path(tmp_path / "nope").exists()  # nothing persisted for empty


def test_migrates_loose_files_and_persists_a_manifest(tmp_path: Path) -> None:
    save_observation(build_observation(title="note", description="d", today="2026-07-05"), tmp_path)
    save_figure_spec(_figure(), tmp_path)
    assert not scratch_manifest_path(tmp_path).exists()  # pre-manifest (the old flat model)

    manifest = load_scratch(tmp_path)

    assert [e.id for e in manifest.observations or []] == ["obs_note_2026-07-05"]
    assert [e.id for e in manifest.figures or []] == ["fig_demo_2026-07-05"]
    assert scratch_manifest_path(tmp_path).exists()  # the one-time migration is persisted


def test_an_existing_manifest_is_the_source_of_truth(tmp_path: Path) -> None:
    save_observation(build_observation(title="a", description="d", today="2026-07-05"), tmp_path)
    load_scratch(tmp_path)  # writes the manifest from the first file
    # a second loose file appears with no manifest update -> the manifest still wins
    save_observation(build_observation(title="b", description="d", today="2026-07-05"), tmp_path)
    assert [e.id for e in load_scratch(tmp_path).observations or []] == ["obs_a_2026-07-05"]
