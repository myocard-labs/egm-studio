"""Tests for artifact existence + format status (view_model.phase_status)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import PhaseManifest, load_phase_dir

from myocard_egm_studio.view_model.phase_status import ArtifactStatus, phase_statuses

_FIXTURE_PHASE = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def _bank_manifest(bank_id: str, path: str) -> PhaseManifest:
    return PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.0,
            "status": "in_progress",
            "egm_banks": [
                {
                    "id": bank_id,
                    "path": path,
                    "produced_by_package": "p",
                    "produced_by_version": "v0",
                }
            ],
        }
    )


def test_existence_present_vs_missing(tmp_path: Path) -> None:
    (tmp_path / "there.h5").write_bytes(b"")
    manifest = PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.0,
            "status": "in_progress",
            "egm_banks": [
                {
                    "id": "tbank_here_2026-01-01",
                    "path": "there.h5",
                    "produced_by_package": "p",
                    "produced_by_version": "v0",
                },
                {
                    "id": "tbank_gone_2026-01-01",
                    "path": "nope.h5",
                    "produced_by_package": "p",
                    "produced_by_version": "v0",
                },
            ],
        }
    )
    statuses = phase_statuses(manifest, tmp_path)
    assert statuses["tbank_here_2026-01-01"] is ArtifactStatus.PRESENT  # exists, unvalidated
    assert statuses["tbank_gone_2026-01-01"] is ArtifactStatus.MISSING


def test_absolute_path_wins_over_base(tmp_path: Path) -> None:
    real = tmp_path / "abs.h5"
    real.write_bytes(b"")
    manifest = _bank_manifest("tbank_abs_2026-01-01", str(real))
    statuses = phase_statuses(manifest, tmp_path / "nonexistent_base")
    assert statuses["tbank_abs_2026-01-01"] is ArtifactStatus.PRESENT


def test_fixture_paths_report_missing() -> None:
    manifest = load_phase_dir(_FIXTURE_PHASE)  # illustrative paths, no real files behind them
    statuses = phase_statuses(manifest, _FIXTURE_PHASE)
    assert statuses
    assert all(status is ArtifactStatus.MISSING for status in statuses.values())


def test_validation_flags_bad_json_but_only_when_asked(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{}")  # present, but not a valid figure_spec
    manifest = PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.0,
            "status": "in_progress",
            "figures": [
                {
                    "id": "fig_bad",
                    "path": "bad.json",
                    "produced_by_package": "egm-studio",
                    "produced_by_version": "v0",
                }
            ],
        }
    )
    assert phase_statuses(manifest, tmp_path)["fig_bad"] is ArtifactStatus.PRESENT  # existence only
    assert phase_statuses(manifest, tmp_path, validate=True)["fig_bad"] is ArtifactStatus.INVALID


def test_bank_present_then_ok_after_validate(tmp_path: Path) -> None:
    (tmp_path / "b.h5").write_bytes(b"not really hdf5")  # garbage, but banks have no validator here
    manifest = _bank_manifest("tbank_b_2026-01-01", "b.h5")
    statuses = phase_statuses(manifest, tmp_path)
    assert statuses["tbank_b_2026-01-01"] is ArtifactStatus.PRESENT  # exists, unvalidated
    validated = phase_statuses(manifest, tmp_path, validate=True)
    # no validator for banks, so a full pass can only confirm existence -> OK, never INVALID
    assert validated["tbank_b_2026-01-01"] is ArtifactStatus.OK
