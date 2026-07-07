"""Tests for the per-artifact action policy (view_model.phase_actions)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_contracts import Role

from myocard_egm_studio.view_model import phase_actions
from myocard_egm_studio.view_model.artifact_metadata import has_metadata_view
from myocard_egm_studio.view_model.phase_actions import (
    SHOW_METADATA,
    UNIVERSAL_ACTIONS,
    actions_for,
    info_actions,
    reveal_target,
    type_actions,
)

_UNIVERSAL_IDS = ("reveal_file", "copy_id")


def test_management_action_is_remove_from_phase() -> None:
    (remove,) = phase_actions.management_actions()
    assert remove.id == "remove_artifact"
    assert remove.label == "Remove from phase"
    assert remove.available


def test_input_bank_viewers() -> None:
    explore, feature_dist = type_actions(Role.training_bank)
    assert [explore.id, feature_dist.id] == ["explore_signal", "view_feature_distributions"]
    assert explore.available and feature_dist.available  # both wired to Flow A (B7.7)


def test_menu_label_relabels_only_the_additive_viewer() -> None:
    """With a bank loaded, View feature distributions becomes Add …; Explore signal
    (which always replaces) keeps its label (B7.8b-fix)."""
    explore, feature_dist = type_actions(Role.training_bank)
    assert phase_actions.menu_label(feature_dist, add_mode=False) == "View feature distributions"
    assert phase_actions.menu_label(feature_dist, add_mode=True) == "Add feature distribution"
    assert phase_actions.menu_label(explore, add_mode=True) == "Explore signal"


def test_prediction_bank_adds_ml_actions() -> None:
    actions = type_actions(Role.labeled_prediction_bank)
    assert [a.id for a in actions] == [
        "explore_signal",
        "view_feature_distributions",
        "view_ml_diagnostics",  # the "Compare with another bank" placeholder was pruned
    ]
    by_id = {a.id: a for a in actions}
    assert by_id["view_ml_diagnostics"].available is True  # B8f — feeds Flow B
    assert all(a.available for a in actions)  # no dead placeholders left
    # additive-aware: with a bank loaded, the ML-diagnostics viewer relabels to Add …
    assert (
        phase_actions.menu_label(by_id["view_ml_diagnostics"], add_mode=True)
        == "Add ML diagnostics"
    )


def test_noise_bank_viewers() -> None:
    (view_noise,) = type_actions(Role.noise_bank)  # curation-summary placeholder was removed
    assert view_noise.id == "view_noise" and view_noise.available is True  # wired B10g (.h5)
    assert "view_curation_summary" not in {a.id for a in actions_for(Role.noise_bank)}


def test_training_run_view_curves_is_wired() -> None:
    (action,) = type_actions(Role.training_run)
    assert action.id == "view_curves"
    assert action.available is True  # B8f — feeds the Flow B Training tab
    assert not action.note


def test_figure_actions_are_dynamic() -> None:
    from myocard_egm_studio.view_model.phase_actions import figure_actions

    not_generated = [a.id for a in figure_actions(output_exists=False)]
    assert not_generated == ["edit_spec", "generate_figure"]  # no View figure until rendered

    generated = {a.id: a.label for a in figure_actions(output_exists=True)}
    assert list(generated) == ["edit_spec", "view_figure", "generate_figure"]
    assert generated["generate_figure"] == "Regenerate figure"  # relabel once it exists
    assert all(a.available for a in figure_actions(output_exists=True))  # all live, no placeholders

    # the static default (non-dynamic callers) is the not-generated set
    assert type_actions(Role.figure) == figure_actions(output_exists=False)


def test_model_has_show_metadata_but_no_viewers() -> None:
    assert type_actions(Role.model) == ()  # the never-built model viewers were pruned
    # the model-metadata JSON is viewable, so the model gets Show metadata...
    assert "show_metadata" in {a.id for a in actions_for(Role.model)}
    assert info_actions(Role.model) == (SHOW_METADATA, *UNIVERSAL_ACTIONS)
    # ...but a paper (a directory) still has no file view — Reveal / Copy only
    assert info_actions(Role.paper) == UNIVERSAL_ACTIONS


def test_metadata_roles_lead_the_info_group() -> None:
    info = info_actions(Role.figure)
    assert [a.id for a in info] == ["show_metadata", *_UNIVERSAL_IDS]
    assert tuple(a.id for a in UNIVERSAL_ACTIONS) == _UNIVERSAL_IDS


def test_actions_for_is_viewers_then_info() -> None:
    ids = [a.id for a in actions_for(Role.training_bank)]
    assert ids == [
        "explore_signal",
        "view_feature_distributions",
        "show_metadata",
        "reveal_file",
        "copy_id",
    ]
    assert [a.id for a in actions_for(Role.paper)] == list(
        _UNIVERSAL_IDS
    )  # no viewers, no metadata


def test_metadata_roles_match_readers() -> None:
    # the roles offered Show metadata must be exactly those artifact_metadata can read
    readable = {role for role in Role if has_metadata_view(role)}
    assert readable == phase_actions._METADATA_ROLES


def test_reveal_target_dwims_file_vs_dir(tmp_path: Path) -> None:
    (tmp_path / "f.h5").write_bytes(b"")
    (tmp_path / "sub").mkdir()
    assert reveal_target(tmp_path, "f.h5") == tmp_path  # a file -> its folder
    assert reveal_target(tmp_path, "sub") == tmp_path / "sub"  # a dir -> itself
    assert reveal_target(tmp_path, "gone/x.h5") == tmp_path / "gone"  # missing -> its folder
