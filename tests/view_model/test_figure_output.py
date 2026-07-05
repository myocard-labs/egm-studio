"""Tests for view_model.figure_output — where a figure renders + whether it's there (B9)."""

from __future__ import annotations

import json
from pathlib import Path

from myocard_egm_data.phases import FigureSpec, load_phase_dir, write_figure_spec

from myocard_egm_studio.view_model.figure_output import (
    figure_output_exists_map,
    figure_output_path,
)


def _spec(*, output_path: str, spec_id: str = "fig_out_test") -> FigureSpec:
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": spec_id,
            "description": "figure output test spec",
            "recipe": "prediction-histogram",
            "inputs": {"groups": [{"name": "g", "bank_id": "lpred_x_2026-06-27"}]},
            "output": {"format": "pdf", "path": output_path},
        }
    )


def test_relative_output_resolves_against_the_spec_dir(tmp_path: Path) -> None:
    got = figure_output_path(_spec(output_path="out/fig.pdf"), tmp_path / "specs" / "s.json")
    assert got == tmp_path / "specs" / "out" / "fig.pdf"


def test_absolute_output_is_kept(tmp_path: Path) -> None:
    absolute = tmp_path / "elsewhere" / "fig.pdf"
    assert figure_output_path(_spec(output_path=str(absolute)), tmp_path / "s.json") == absolute


def test_no_spec_path_returns_output_as_is() -> None:
    assert figure_output_path(_spec(output_path="out/fig.pdf")) == Path("out/fig.pdf")


def _phase_with_one_figure(phase_dir: Path) -> None:
    """Write a minimal phase (manifest + one figure spec) under ``phase_dir``."""
    write_figure_spec(phase_dir / "f.json", _spec(output_path="out.pdf", spec_id="fig_x"))
    manifest = {
        "schema_version": "1",
        "phase": 1.0,
        "status": "in_progress",
        "phase_summary": "figure-output test phase",
        "figures": [
            {
                "id": "fig_x",
                "path": "f.json",
                "produced_by_package": "egm-studio",
                "produced_by_version": "v0.1.0",
                "consumes_banks": ["lpred_x_2026-06-27"],
                "usage_tag": "exploratory",
            }
        ],
    }
    (phase_dir / "manifest.json").write_text(json.dumps(manifest))


def test_exists_map_flips_when_the_image_appears(tmp_path: Path) -> None:
    _phase_with_one_figure(tmp_path)
    manifest = load_phase_dir(tmp_path)

    assert figure_output_exists_map(manifest, tmp_path) == {"fig_x": False}  # not rendered yet
    (tmp_path / "out.pdf").write_bytes(b"%PDF-1.4")  # render it
    assert figure_output_exists_map(manifest, tmp_path) == {"fig_x": True}
