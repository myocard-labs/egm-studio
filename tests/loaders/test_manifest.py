"""Tests for loaders.manifest — resolving a phase folder to {artifact_id: path}."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import PhaseManifest, load_phase_dir, write_phase_manifest

from myocard_egm_studio.loaders import bank_paths_from_phase
from myocard_egm_studio.view_model import entries_by_id

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def test_maps_every_artifact_relative_to_the_phase() -> None:
    paths = bank_paths_from_phase(_FIXTURE_DIR)
    entries = entries_by_id(load_phase_dir(_FIXTURE_DIR))
    assert set(paths) == set(entries)  # every manifest artifact id is resolved
    sample_id = next(iter(entries))
    assert paths[sample_id] == _FIXTURE_DIR / entries[sample_id].path


def test_absolute_path_in_manifest_wins(tmp_path: Path) -> None:
    absolute = tmp_path / "elsewhere" / "b.classifier.h5"
    manifest = PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.0,
            "status": "in_progress",
            "egm_banks": [
                {
                    "id": "tbank_abs_2026-01-01",
                    "path": str(absolute),
                    "produced_by_package": "p",
                    "produced_by_version": "v0",
                }
            ],
        }
    )
    write_phase_manifest(tmp_path / "manifest.json", manifest)
    paths = bank_paths_from_phase(tmp_path)
    assert paths["tbank_abs_2026-01-01"] == absolute  # absolute path is not re-rooted
