"""Tests for artifact existence + format status (view_model.phase_status)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import EgmBankEntry, Observation, PhaseManifest, load_phase_dir

from myocard_egm_studio.save import (
    empty_manifest,
    observation_entry,
    save_observation,
    with_entry,
)
from myocard_egm_studio.view_model.phase_status import (
    ArtifactStatus,
    phase_status_report,
    phase_statuses,
)

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


def _observation_over(bank_id: str) -> Observation:
    """A valid observation whose only dependency is one loaded bank."""
    return Observation.model_validate(
        {
            "schema_version": "1",
            "id": "obs_note_2026-07-05",
            "date": "2026-07-05",
            "title": "note",
            "description": "d",
            "view_state": {"banks_loaded": [bank_id]},
        }
    )


def test_observation_unresolved_when_its_bank_is_not_in_the_phase(tmp_path: Path) -> None:
    obs = _observation_over("lpred_x_2026-06-27")
    save_observation(obs, tmp_path)  # a present, schema-valid observation file
    manifest = with_entry(empty_manifest(1.0), "observations", observation_entry(obs))

    # existence pass: just present; the dependency gap only shows on a full validate
    assert phase_status_report(manifest, tmp_path)[obs.id].status is ArtifactStatus.PRESENT
    report = phase_status_report(manifest, tmp_path, validate=True)[obs.id]
    assert report.status is ArtifactStatus.UNRESOLVED
    assert "lpred_x_2026-06-27" in report.detail  # the "why" names the missing id


def test_extra_ids_resolve_dependencies_cross_scope(tmp_path: Path) -> None:
    obs = _observation_over("lpred_x_2026-06-27")
    save_observation(obs, tmp_path)
    manifest = with_entry(empty_manifest(1.0), "observations", observation_entry(obs))
    # the bank isn't in this manifest, but supplying it via extra_ids (a loaded phase) resolves it
    resolved = phase_status_report(
        manifest, tmp_path, validate=True, extra_ids={"lpred_x_2026-06-27"}
    )
    assert resolved[obs.id].status is ArtifactStatus.OK
    # without extra_ids the same observation is unresolved (its bank is nowhere)
    alone = phase_status_report(manifest, tmp_path, validate=True)
    assert alone[obs.id].status is ArtifactStatus.UNRESOLVED


def test_observation_ok_once_its_bank_is_indexed(tmp_path: Path) -> None:
    obs = _observation_over("lpred_x_2026-06-27")
    save_observation(obs, tmp_path)
    manifest = with_entry(empty_manifest(1.0), "observations", observation_entry(obs))
    manifest = with_entry(
        manifest, "egm_banks", EgmBankEntry.model_validate(_base_bank("lpred_x_2026-06-27"))
    )
    # the bank need only be *indexed*; its own file can still be missing (that's its own row)
    assert (
        phase_status_report(manifest, tmp_path, validate=True)[obs.id].status is ArtifactStatus.OK
    )


def test_derived_bank_unresolved_without_its_source(tmp_path: Path) -> None:
    (tmp_path / "d.h5").write_bytes(b"")  # present; banks have no schema validator
    entry = EgmBankEntry.model_validate(
        {**_base_bank("lpred_a_2026-06-27"), "path": "d.h5", "source_bank": "lbank_src_2026-06-01"}
    )
    manifest = with_entry(empty_manifest(1.0), "egm_banks", entry)
    report = phase_status_report(manifest, tmp_path, validate=True)["lpred_a_2026-06-27"]
    assert report.status is ArtifactStatus.UNRESOLVED
    assert "lbank_src_2026-06-01" in report.detail


def _base_bank(bank_id: str) -> dict[str, str]:
    return {
        "id": bank_id,
        "path": f"{bank_id}.h5",
        "produced_by_package": "p",
        "produced_by_version": "v0",
    }
