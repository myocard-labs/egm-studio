"""Tests for save.figure — write a figure spec into a phase + derive its entry (B10d)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import FigureSpec, load_figure_spec

from myocard_egm_studio.save.figure import (
    FIGURES_DIR,
    figure_entry,
    figure_spec_path,
    save_figure_spec,
)


def _spec(**overrides: object) -> FigureSpec:
    raw: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_feat_dist",
        "description": "d",
        "recipe": "feature-distribution-overlay",
        "inputs": {
            "groups": [
                {"name": "S", "bank_id": "lpred_synth_2026-06-29"},
                {"name": "I", "bank_id": "lpred_iafdb_2026-06-29"},
            ]
        },
        "output": {"format": "pdf", "path": "x.pdf"},
    }
    raw.update(overrides)
    return FigureSpec.model_validate(raw)


def test_figure_entry_derives_banks_and_observations() -> None:
    entry = figure_entry(_spec(illustrates_observations=["obs_high_entropy_2026-06-25"]))
    assert entry.id == "fig_feat_dist"
    assert entry.path == "figures/fig_feat_dist.json"  # canonical, relative to the phase
    assert [b.root for b in entry.consumes_banks or []] == [
        "lpred_synth_2026-06-29",
        "lpred_iafdb_2026-06-29",
    ]
    assert [o.root for o in entry.consumes_observations or []] == ["obs_high_entropy_2026-06-25"]
    assert entry.usage_tag is not None and entry.usage_tag.value == "exploratory"


def test_figure_entry_dedups_bank_ids() -> None:
    spec = _spec(
        inputs={
            "groups": [
                {"name": "a", "bank_id": "lpred_x_2026-06-27"},
                {"name": "b", "bank_id": "lpred_x_2026-06-27"},
            ]
        }
    )
    assert [b.root for b in figure_entry(spec).consumes_banks or []] == ["lpred_x_2026-06-27"]


def test_figure_entry_omits_empty_relationship_fields() -> None:
    entry = figure_entry(_spec())  # no illustrates_observations
    assert entry.consumes_observations is None
    assert entry.consumes_banks is not None  # groups are still present


def test_save_figure_spec_round_trips(tmp_path: Path) -> None:
    spec = _spec()
    written = save_figure_spec(spec, tmp_path)
    assert written == figure_spec_path(spec, tmp_path)
    assert written == tmp_path / FIGURES_DIR / "fig_feat_dist.json"
    assert load_figure_spec(written).id == "fig_feat_dist"
