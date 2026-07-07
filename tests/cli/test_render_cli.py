"""End-to-end tests for the egm-studio-render CLI (load -> validate -> dispatch).

The shipped examples/stub_spec.json names a recipe that isn't registered, so it
exercises the whole load -> validate -> dispatch path and exits with the clear
unknown-recipe error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from myocard_egm_data.phases import PhaseManifest, write_phase_manifest

from myocard_egm_studio.cli.render import main

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STUB_SPEC = _REPO_ROOT / "examples" / "stub_spec.json"


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """``--help`` prints the program usage and exits 0 (argparse convention)."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "egm-studio-render" in capsys.readouterr().out


def test_stub_spec_returns_unknown_recipe(capsys: pytest.CaptureFixture[str]) -> None:
    """The shipped stub spec validates but names an unregistered recipe, so the
    CLI runs the full load -> validate -> dispatch path and exits 3 with the
    unknown-recipe message — the Block 2 plumbing acceptance check."""
    rc = main([str(_STUB_SPEC)])
    assert rc == 3
    err = capsys.readouterr().err
    assert "unknown figure recipe" in err
    assert "unregistered-stub-recipe" in err


def test_missing_spec_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A nonexistent spec path exits 1 with a clear 'cannot read spec file'
    message (the OSError branch)."""
    rc = main([str(tmp_path / "does_not_exist.json")])
    assert rc == 1
    assert "cannot read spec file" in capsys.readouterr().err


def test_invalid_spec_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A spec that is valid JSON but missing required fields fails Pydantic
    validation and exits 2 (the invalid-spec branch)."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "1"}', encoding="utf-8")  # missing required fields
    rc = main([str(bad)])
    assert rc == 2
    assert "invalid figure spec" in capsys.readouterr().err


def test_malformed_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A spec file that isn't valid JSON exits 2 with a 'malformed' message (the
    JSONDecodeError / ValueError branch)."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    rc = main([str(bad)])
    assert rc == 2
    assert "malformed" in capsys.readouterr().err.lower()


# --- real-data rendering via --bank / --banks ---------------------------- #

_FIXTURE_PRED_ID = "lpred_studio_fixture_2026-06-28"


def _write_ph_spec(path: Path, *, bank_id: str, out: Path) -> None:
    """Write a minimal prediction-histogram figure_spec JSON to ``path``."""
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "id": "fig_cli_real_data",
                "description": "CLI real-data render test spec",
                "recipe": "prediction-histogram",
                "inputs": {"groups": [{"name": "Synthetic val", "bank_id": bank_id}]},
                "layout": {"mode": "panels"},
                "output": {"format": "png", "path": str(out)},
            }
        ),
        encoding="utf-8",
    )


def test_render_with_bank_flag(
    tiny_predictions_bank: ClassifierBank,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--bank ID=PATH resolves the spec's bank, renders real data, exits 0."""
    bank_path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, bank_path)
    spec_path = tmp_path / "spec.json"
    out = tmp_path / "fig.png"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=out)
    rc = main([str(spec_path), "--bank", f"{_FIXTURE_PRED_ID}={bank_path}"])
    assert rc == 0
    assert out.exists()
    assert "Wrote" in capsys.readouterr().out


def test_render_with_banks_json(tiny_predictions_bank: ClassifierBank, tmp_path: Path) -> None:
    """--banks MAP.json (the proto-manifest) resolves the bank and renders."""
    bank_path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, bank_path)
    out = tmp_path / "fig.png"
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=out)
    banks_json = tmp_path / "banks.json"
    banks_json.write_text(json.dumps({_FIXTURE_PRED_ID: str(bank_path)}), encoding="utf-8")
    rc = main([str(spec_path), "--banks", str(banks_json)])
    assert rc == 0
    assert out.exists()


def test_render_no_bank_map_exits_4(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A known recipe with no --bank/--banks exits 4 asking for a map."""
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=tmp_path / "fig.png")
    rc = main([str(spec_path)])
    assert rc == 4
    assert "--bank" in capsys.readouterr().err


def test_render_unmapped_bank_exits_5(
    tiny_predictions_bank: ClassifierBank,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A --bank for a different id than the spec needs exits 5, naming the gap."""
    bank_path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, bank_path)
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id="lpred_needed_2026-06-28", out=tmp_path / "fig.png")
    rc = main([str(spec_path), "--bank", f"lpred_other_2026-06-28={bank_path}"])
    assert rc == 5
    assert "lpred_needed_2026-06-28" in capsys.readouterr().err


def test_bank_flag_bad_format_exits_2(tmp_path: Path) -> None:
    """A --bank value without '=' is an argparse usage error (exit 2)."""
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id="lpred_x_2026-06-28", out=tmp_path / "fig.png")
    with pytest.raises(SystemExit) as excinfo:
        main([str(spec_path), "--bank", "no-equals-sign"])
    assert excinfo.value.code == 2


def test_render_skips_existing_output(
    tiny_predictions_bank: ClassifierBank,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An existing output is skipped (exit 0) without loading data or
    overwriting it — even with a valid --bank map supplied."""
    bank_path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, bank_path)
    out = tmp_path / "fig.png"
    out.write_bytes(b"SENTINEL")
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=out)
    rc = main([str(spec_path), "--bank", f"{_FIXTURE_PRED_ID}={bank_path}"])
    assert rc == 0
    assert "skipping" in capsys.readouterr().out.lower()
    assert out.read_bytes() == b"SENTINEL"  # untouched


def test_render_overwrite_replaces_existing(
    tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """--overwrite re-renders over an existing output (a real PNG replaces it)."""
    bank_path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, bank_path)
    out = tmp_path / "fig.png"
    out.write_bytes(b"SENTINEL")
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=out)
    rc = main([str(spec_path), "--bank", f"{_FIXTURE_PRED_ID}={bank_path}", "--overwrite"])
    assert rc == 0
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG header, not the sentinel


# --- real-data rendering via --phase (manifest resolution) --------------- #


def test_render_with_phase_manifest(
    tiny_predictions_bank: ClassifierBank,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--phase FOLDER resolves the spec's bank id through the manifest and renders."""
    phase = tmp_path / "phase_1_5"
    phase.mkdir()
    write_classifier_bank(tiny_predictions_bank, phase / "preds.h5")
    manifest = PhaseManifest.model_validate(
        {
            "schema_version": "1",
            "phase": 1.5,
            "status": "in_progress",
            "egm_banks": [
                {
                    "id": _FIXTURE_PRED_ID,
                    "path": "preds.h5",
                    "produced_by_package": "egm-classifier",
                    "produced_by_version": "v0.4.0",
                }
            ],
        }
    )
    write_phase_manifest(phase / "manifest.json", manifest)
    out = tmp_path / "fig.png"
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=out)
    rc = main([str(spec_path), "--phase", str(phase)])
    assert rc == 0
    assert out.exists()
    assert "Wrote" in capsys.readouterr().out


def test_bad_phase_folder_exits_2(tmp_path: Path) -> None:
    """--phase at a folder with no manifest.json is an argparse usage error (exit 2)."""
    spec_path = tmp_path / "spec.json"
    _write_ph_spec(spec_path, bank_id=_FIXTURE_PRED_ID, out=tmp_path / "fig.png")
    with pytest.raises(SystemExit) as excinfo:
        main([str(spec_path), "--phase", str(tmp_path / "no_such_phase")])
    assert excinfo.value.code == 2
