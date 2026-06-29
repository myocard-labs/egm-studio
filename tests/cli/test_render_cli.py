"""End-to-end tests for the egm-studio-render CLI (load -> validate -> dispatch).

At Block 2 the recipe registry is empty, so the shipped examples/stub_spec.json
exercises the whole path and exits with the clear unknown-recipe error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    assert "feature-distribution-overlay" in err


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
