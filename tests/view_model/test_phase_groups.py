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


def test_empty_manifest_still_has_ten_groups() -> None:
    empty = PhaseManifest.model_validate(
        {"schema_version": "1", "phase": 2.0, "status": "in_progress"}
    )
    groups = phase_artifact_groups(empty)
    assert len(groups) == 10
    assert all(g.count == 0 for g in groups)
