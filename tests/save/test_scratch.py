"""Tests for save.scratch — listing artifacts in the scratch folder (B10e)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_studio.save.scratch import scratch_artifacts


def test_scans_observations_and_figures_sorted(tmp_path: Path) -> None:
    (tmp_path / "observations").mkdir()
    (tmp_path / "figures").mkdir()
    (tmp_path / "observations" / "obs_b_2026-07-05.json").write_text("{}")
    (tmp_path / "observations" / "obs_a_2026-07-05.json").write_text("{}")
    (tmp_path / "figures" / "fig_z_2026-07-05.json").write_text("{}")

    found = scratch_artifacts(tmp_path)

    assert [(a.id, a.kind) for a in found] == [
        ("obs_a_2026-07-05", "observation"),  # observations first, sorted by id
        ("obs_b_2026-07-05", "observation"),
        ("fig_z_2026-07-05", "figure"),
    ]
    assert found[0].path == tmp_path / "observations" / "obs_a_2026-07-05.json"


def test_missing_or_empty_scratch_is_empty(tmp_path: Path) -> None:
    assert scratch_artifacts(tmp_path / "nonexistent") == []
    (tmp_path / "observations").mkdir()
    assert scratch_artifacts(tmp_path) == []  # empty subdir -> nothing
