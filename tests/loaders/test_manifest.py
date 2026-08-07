"""Tests for loaders.manifest — resolving a phase folder to {artifact_id: path}."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from myocard_egm_data.banks import (
    ClassifierBank,
    ClassifierBankMetaData,
    ClassifierTrace,
    write_classifier_bank,
)
from myocard_egm_data.phases import PhaseManifest, load_phase_dir, write_phase_manifest

from myocard_egm_studio.loaders import bank_paths_from_phase, resolve_bank_paths
from myocard_egm_studio.view_model import entries_by_id

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def test_maps_every_artifact_relative_to_the_phase() -> None:
    paths = bank_paths_from_phase(_FIXTURE_DIR)
    entries = entries_by_id(load_phase_dir(_FIXTURE_DIR))
    assert set(paths) == set(entries)  # every manifest artifact id is resolved
    sample_id = next(iter(entries))
    assert paths[sample_id] == _FIXTURE_DIR / entries[sample_id].path


def test_resolve_bank_paths_searches_multiple_dirs(tmp_path: Path) -> None:
    """A scratch observation resolves its banks across [scratch, phase] (cross-scope, 2c)."""
    from myocard_egm_data.phases import EgmBankEntry

    from myocard_egm_studio.save import empty_manifest, save_manifest, with_entry

    scratch, phase = tmp_path / "scratch", tmp_path / "phase"
    scratch.mkdir()
    phase.mkdir()
    entry = EgmBankEntry.model_validate(
        {
            "id": "lpred_x_2026-06-27",
            "path": "bank.h5",
            "produced_by_package": "p",
            "produced_by_version": "v",
        }
    )
    save_manifest(with_entry(empty_manifest(1.0), "egm_banks", entry), phase)  # bank only in phase

    paths, missing = resolve_bank_paths([scratch, phase], ["lpred_x_2026-06-27"])

    assert missing == []
    assert paths == [phase / "bank.h5"]  # found by falling through to the second dir


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


def _phase_with_bank(tmp_path: Path, *, entry_id: str, bank_id: str) -> Path:
    """A phase folder with one egm bank on disk whose stamped ``bank_id`` may differ
    from its manifest ``entry_id`` (the id-drift case Open observation must tolerate)."""
    (tmp_path / "banks").mkdir()
    rng = np.random.default_rng(0)
    traces = [
        ClassifierTrace(
            bank_id="tbank_src_2026-06-27",
            signal=rng.standard_normal(64).astype(np.float32),
            freq_hz=1000.0,
            amp_type="mv",
            split=None,
            label_truth=i % 2,
            prediction=None,
            trace_metadata={},
        )
        for i in range(4)
    ]
    md = ClassifierBankMetaData(
        bank_id="tbank_src_2026-06-27", bank_type="synthetic", bank_path="x", bank_metadata={}
    )
    bank = ClassifierBank(banks=[md], traces=traces, labels={0: "h", 1: "f"}, id=bank_id)
    write_classifier_bank(bank, tmp_path / "banks" / "a.h5")
    manifest = PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.5,
            "status": "in_progress",
            "egm_banks": [
                {
                    "id": entry_id,
                    "path": "banks/a.h5",
                    "produced_by_package": "p",
                    "produced_by_version": "v",
                }
            ],
        }
    )
    write_phase_manifest(tmp_path / "manifest.json", manifest)
    return tmp_path


def test_resolve_bank_paths_matches_the_entry_id(tmp_path: Path) -> None:
    """The invariant case (bank.id == entry.id) resolves directly from the manifest map."""
    phase = _phase_with_bank(tmp_path, entry_id="tbank_a_2026-06-27", bank_id="tbank_a_2026-06-27")
    paths, missing = resolve_bank_paths(phase, ["tbank_a_2026-06-27"])
    assert [p.name for p in paths] == ["a.h5"]
    assert missing == []


def test_resolve_bank_paths_falls_back_to_the_stamped_id(tmp_path: Path) -> None:
    """When a saved observation's id is the bank's stamped id and it has drifted from the
    manifest entry id, resolution falls back to reading the bank's own id."""
    phase = _phase_with_bank(
        tmp_path, entry_id="tbank_entry_2026-06-27", bank_id="tbank_stamped_2026-06-27"
    )
    paths, missing = resolve_bank_paths(phase, ["tbank_stamped_2026-06-27"])
    assert [p.name for p in paths] == ["a.h5"]  # resolved despite the id drift
    assert missing == []


def test_resolve_bank_paths_reports_the_unresolvable(tmp_path: Path) -> None:
    phase = _phase_with_bank(tmp_path, entry_id="tbank_a_2026-06-27", bank_id="tbank_a_2026-06-27")
    paths, missing = resolve_bank_paths(phase, ["tbank_a_2026-06-27", "tbank_ghost_2026-06-27"])
    assert [p.name for p in paths] == ["a.h5"]
    assert missing == ["tbank_ghost_2026-06-27"]  # not in the phase at all
