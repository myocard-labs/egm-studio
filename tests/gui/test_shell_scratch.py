"""Tests for scratch mode + Promote-to-Phase wiring in the shell (B10e)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
from myocard_egm_data.phases import (
    MANIFEST_FILENAME,
    FigureSpec,
    load_figure_spec,
    load_observation,
)
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.save import observation_id, scratch_artifacts
from myocard_egm_studio.view_model import entries_by_id

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def _explore_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"row_id": [0], "source": ["lpred_a_2026-06-27"], "trace_idx": [0], "peak_to_peak": [1.0]}
    )


def _window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    window._scratch_dir = str(tmp_path / "scratch")  # a temp scratch, not the real app-data one
    window._refresh_scratch()
    return window


def _figure_spec() -> FigureSpec:
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_demo",
            "description": "d",
            "recipe": "prediction-histogram",
            "inputs": {"groups": [{"name": "g", "bank_id": "lpred_a_2026-06-27"}]},
            "output": {"format": "pdf", "path": "out.pdf"},
        }
    )


def test_scratch_list_hidden_until_something_is_saved(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    assert window._scratch_list.isHidden()  # empty scratch -> the GUI looks unchanged

    window._explore_df = _explore_frame()
    window._write_observation("Scratch note", "no phase open")

    assert not window._scratch_list.isHidden()  # now it appears
    arts = scratch_artifacts(window._scratch_dir)
    assert [a.id for a in arts] == [observation_id("Scratch note")]
    assert "to scratch" in window.statusBar().currentMessage()


def test_scratch_observation_parents_come_from_scratch(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("First", "prose")
    assert window._existing_observation_ids() == [observation_id("First")]  # scratch, no phase


def test_save_figure_with_no_phase_goes_to_scratch(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._save_figure_into_phase(_figure_spec())
    assert (Path(window._scratch_dir) / "figures" / "fig_demo.json").exists()
    assert "to scratch" in window.statusBar().currentMessage()


def test_promote_moves_a_scratch_artifact_into_the_phase(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Promote me", "prose")
    artifact = scratch_artifacts(window._scratch_dir)[0]

    phase = tmp_path / "phase"
    phase.mkdir()
    shutil.copy(_FIXTURE_DIR / MANIFEST_FILENAME, phase / MANIFEST_FILENAME)
    window._load_phase_into_tree(str(phase))

    window._promote_scratch(artifact)

    obs_id = observation_id("Promote me")
    assert (phase / "observations" / f"{obs_id}.json").exists()  # moved into the phase
    assert load_observation(phase / "observations" / f"{obs_id}.json").id == obs_id
    assert window._phase_manifest is not None
    assert obs_id in entries_by_id(window._phase_manifest)  # indexed
    assert scratch_artifacts(window._scratch_dir) == []  # gone from scratch
    assert window._scratch_list.isHidden()  # scratch empty -> hidden again
    assert "Promoted" in window.statusBar().currentMessage()


def test_promote_a_figure_derives_its_entry(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._save_figure_into_phase(_figure_spec())
    artifact = scratch_artifacts(window._scratch_dir)[0]

    phase = tmp_path / "phase"
    phase.mkdir()
    shutil.copy(_FIXTURE_DIR / MANIFEST_FILENAME, phase / MANIFEST_FILENAME)
    window._load_phase_into_tree(str(phase))

    window._promote_scratch(artifact)

    assert load_figure_spec(phase / "figures" / "fig_demo.json").id == "fig_demo"
    assert window._phase_manifest is not None and "fig_demo" in entries_by_id(
        window._phase_manifest
    )


def test_promote_without_a_phase_reports(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("No phase", "prose")
    artifact = scratch_artifacts(window._scratch_dir)[0]

    window._promote_scratch(artifact)  # no phase loaded

    assert "Open a phase" in window.statusBar().currentMessage()
    assert scratch_artifacts(window._scratch_dir) == [artifact]  # left in scratch


def test_delete_removes_the_scratch_file(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Delete me", "prose")
    artifact = scratch_artifacts(window._scratch_dir)[0]

    window._delete_scratch(artifact)

    assert not artifact.path.exists()
    assert scratch_artifacts(window._scratch_dir) == []
    assert window._scratch_list.isHidden()
    assert "Deleted" in window.statusBar().currentMessage()
