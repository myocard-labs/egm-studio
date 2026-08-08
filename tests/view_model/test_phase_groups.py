"""Tests for the phase-artifact view-model (view_model.phase_groups).

Loads the fixture phase through egm-data's load_phase_dir and projects it into
the ten role-based display groups, so this exercises the full seam: egm-data
reader -> egm-contracts role_of -> egm-studio grouping.
"""

from __future__ import annotations

from pathlib import Path

from myocard_egm_contracts import Role
from myocard_egm_data.phases import PhaseManifest, load_phase_dir

from myocard_egm_studio.view_model.phase_groups import phase_artifact_groups

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"

_EXPECTED_ROLES = [
    Role.training_bank,
    Role.pretraining_bank,
    Role.labeled_prediction_bank,
    Role.unlabeled_prediction_bank,
    Role.noise_bank,
    Role.training_run,
    Role.model,
    Role.observation,
    Role.figure,
    Role.paper,
]


def test_ten_groups_in_pipeline_order() -> None:
    groups = phase_artifact_groups(load_phase_dir(_FIXTURE_DIR))
    assert [g.role for g in groups] == _EXPECTED_ROLES


def test_group_counts_and_role_classification() -> None:
    groups = {g.role: g for g in phase_artifact_groups(load_phase_dir(_FIXTURE_DIR))}
    assert all(g.count == 1 for g in groups.values())  # fixture has one of each
    assert groups[Role.training_bank].rows[0].id.startswith("tbank_")
    assert groups[Role.pretraining_bank].rows[0].id.startswith("ptbank_")
    assert groups[Role.labeled_prediction_bank].rows[0].id.startswith("lpred_")
    assert groups[Role.unlabeled_prediction_bank].rows[0].id.startswith("upred_")
    assert groups[Role.figure].rows[0].id.startswith("fig_")


def test_row_details_capture_relationships_and_usage() -> None:
    groups = {g.role: g for g in phase_artifact_groups(load_phase_dir(_FIXTURE_DIR))}

    run_details = dict(groups[Role.training_run].rows[0].details)
    assert run_details["Trained on bank"] == "tbank_synthetic_courtemanche_v1_5_2026-06-25"
    assert run_details["Produced model"] == "model_egm_classifier_v1_5_2026-06-25"

    fig_details = dict(groups[Role.figure].rows[0].details)
    assert "upred_iafdb_v1_5_2026-06-25" in fig_details["Consumes banks"]
    assert fig_details["Usage tag"] == "in_paper_main"

    # Core pointer fields are not duplicated into details.
    assert "Id" not in run_details
    assert "Path" not in run_details


def test_a_stamped_entry_reads_package_then_version() -> None:
    groups = {g.role: g for g in phase_artifact_groups(load_phase_dir(_FIXTURE_DIR))}
    assert groups[Role.training_bank].rows[0].produced_by == "synthetic-egm-pipeline v0.3.0"


def _manifest_with(**sections: object) -> PhaseManifest:
    return PhaseManifest.model_validate(
        {"schema_version": "1", "phase": 1.5, "status": "in_progress", **sections}
    )


def test_an_entry_without_provenance_renders_rather_than_raising() -> None:
    """B19: ``produced_by_*`` are optional, and a curator-indexed artifact carries neither.

    This is the shape of *every* producer artifact indexed through the GUI — ``save.producer``
    omits the fields rather than stamping the old ``"unknown"`` / ``"0"`` sentinels. The
    fixture manifest stamps provenance on all ten entries, so nothing in the suite saw the
    absent case until it crashed the Phase tree on a real index.
    """
    manifest = _manifest_with(egm_banks=[{"id": "tbank_indexed_2026-08-08", "path": "banks/b.h5"}])

    row = phase_artifact_groups(manifest)[0].rows[0]

    assert row.produced_by == "not recorded"  # an absence, stated as one
    assert row.details == ()  # and nothing invented into the detail rows either


def test_a_half_stamped_provenance_shows_the_part_that_is_there() -> None:
    """Either field may be absent independently, so neither can be assumed present."""
    manifest = _manifest_with(
        egm_banks=[
            {
                "id": "tbank_indexed_2026-08-08",
                "path": "banks/b.h5",
                "produced_by_package": "synthetic-egm-pipeline",
            }
        ]
    )

    assert phase_artifact_groups(manifest)[0].rows[0].produced_by == "synthetic-egm-pipeline"


def test_empty_manifest_still_has_ten_groups() -> None:
    empty = PhaseManifest.model_validate(
        {"schema_version": "1", "phase": 2.0, "status": "in_progress"}
    )
    groups = phase_artifact_groups(empty)
    assert len(groups) == 10
    assert all(g.count == 0 for g in groups)
