"""Tests for the scratch area (real manifest) + Promote/Delete wiring in the shell (B10h-2a)."""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from myocard_egm_data.phases import (
    MANIFEST_FILENAME,
    EgmBankEntry,
    FigureSpec,
    Observation,
    load_figure_spec,
    load_observation,
)
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.gui.widgets.phase_tree import ARTIFACT_ID_ROLE, STATUS_ROLE
from myocard_egm_studio.save import (
    load_scratch,
    observation_entry,
    observation_id,
    save_manifest,
    save_observation,
    with_entry,
)
from myocard_egm_studio.view_model import entries_by_id
from myocard_egm_studio.view_model.phase_status import ArtifactStatus

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def _explore_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"row_id": [0], "source": ["lpred_a_2026-06-27"], "trace_idx": [0], "peak_to_peak": [1.0]}
    )


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


def _window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    window._scratch_dir = str(tmp_path / "scratch")  # a temp scratch, not the real app-data one
    window._refresh_scratch()
    return window


def _scratch_ids(window: MainWindow) -> list[str]:
    return list(entries_by_id(load_scratch(window._scratch_dir)))


def _scratch_item_status(window: MainWindow, artifact_id: str) -> ArtifactStatus | None:
    tree = window._scratch_tree
    for i in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(i)
        assert group is not None
        for j in range(group.childCount()):
            item = group.child(j)
            assert item is not None
            if item.data(0, ARTIFACT_ID_ROLE) == artifact_id:
                status = item.data(0, STATUS_ROLE)
                return status if isinstance(status, ArtifactStatus) else None
    return None


def _open_phase(window: MainWindow, tmp_path: Path) -> Path:
    phase = tmp_path / "phase"
    phase.mkdir()
    shutil.copy(_FIXTURE_DIR / MANIFEST_FILENAME, phase / MANIFEST_FILENAME)
    window._load_phase_into_tree(str(phase))
    return phase


def test_scratch_hidden_until_something_is_saved(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    assert window._scratch_pane.isHidden()  # empty scratch -> the GUI looks unchanged

    window._explore_df = _explore_frame()
    window._write_observation("Scratch note", "no phase open")

    assert not window._scratch_pane.isHidden()  # now the scratch tree appears
    assert _scratch_ids(window) == [observation_id("Scratch note")]  # indexed in its manifest
    assert "to scratch" in window.statusBar().currentMessage()


def test_scratch_observation_parents_come_from_scratch(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("First", "prose")
    assert window._existing_observation_ids() == [observation_id("First")]  # scratch, no phase


def test_save_figure_with_no_phase_goes_to_scratch(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._save_figure(_figure_spec())
    assert (Path(window._scratch_dir) / "figures" / "fig_demo.json").exists()
    assert "fig_demo" in _scratch_ids(window)  # indexed in the scratch manifest
    assert "to scratch" in window.statusBar().currentMessage()


def test_save_figure_to_scratch_even_with_a_phase_open(qtbot: QtBot, tmp_path: Path) -> None:
    """The gap 2d closes: an explicit "Add to scratch" writes to scratch, phase or not."""
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    window._save_figure(_figure_spec(), "scratch")
    assert "fig_demo" in _scratch_ids(window)  # in scratch...
    assert window._phase_manifest is not None
    assert "fig_demo" not in entries_by_id(window._phase_manifest)  # ...not swept into the phase


def test_save_observation_to_scratch_even_with_a_phase_open(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Scratch note", "prose", target="scratch")
    obs_id = observation_id("Scratch note")
    assert obs_id in _scratch_ids(window)  # into scratch...
    assert window._phase_manifest is not None
    assert obs_id not in entries_by_id(window._phase_manifest)  # ...not the loaded phase


def test_save_observation_to_phase_target_lands_in_the_phase(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Phase note", "prose", target="phase")
    obs_id = observation_id("Phase note")
    assert window._phase_manifest is not None
    assert obs_id in entries_by_id(window._phase_manifest)  # into the phase...
    assert obs_id not in _scratch_ids(window)  # ...not scratch


def test_phase_save_targets_track_whether_a_phase_is_open(qtbot: QtBot, tmp_path: Path) -> None:
    """Every "…to phase" target (Load bank/run, Save observation/figure) enables only with a
    phase — the shared aboutToShow sync over ``_phase_target_actions`` (2b/2d)."""
    window = _window(qtbot, tmp_path)
    window._sync_phase_targets()
    assert window._phase_target_actions  # bank + run + observation + figure targets
    assert all(not action.isEnabled() for action in window._phase_target_actions)  # no phase
    _open_phase(window, tmp_path)
    window._sync_phase_targets()
    assert all(action.isEnabled() for action in window._phase_target_actions)  # now a phase


def test_promote_moves_an_observation_into_the_phase(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Promote me", "prose")
    obs_id = observation_id("Promote me")
    phase = _open_phase(window, tmp_path)

    window._promote_scratch(obs_id)

    assert load_observation(phase / "observations" / f"{obs_id}.json").id == obs_id  # in the phase
    assert window._phase_manifest is not None and obs_id in entries_by_id(window._phase_manifest)
    assert _scratch_ids(window) == []  # gone from the scratch manifest
    assert not (Path(window._scratch_dir) / "observations" / f"{obs_id}.json").exists()  # + file
    assert window._scratch_pane.isHidden()  # scratch empty -> hidden again
    assert "Promoted" in window.statusBar().currentMessage()


def test_promote_a_figure_derives_its_entry(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._save_figure(_figure_spec())
    phase = _open_phase(window, tmp_path)

    window._promote_scratch("fig_demo")

    assert load_figure_spec(phase / "figures" / "fig_demo.json").id == "fig_demo"
    assert window._phase_manifest is not None and "fig_demo" in entries_by_id(
        window._phase_manifest
    )
    assert _scratch_ids(window) == []


def test_promote_without_a_phase_reports(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("No phase", "prose")
    obs_id = observation_id("No phase")

    window._promote_scratch(obs_id)  # no phase loaded

    assert "Open a phase" in window.statusBar().currentMessage()
    assert _scratch_ids(window) == [obs_id]  # left in scratch


def _stage_scratch_bank(window: MainWindow, bank_id: str) -> None:
    """Index a present bank into scratch so an observation over it resolves (cross-scope)."""
    path = Path(window._scratch_dir) / f"{bank_id}.h5"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    entry = EgmBankEntry.model_validate(
        {
            "id": bank_id,
            "path": str(path),
            "produced_by_package": "unknown",
            "produced_by_version": "0",
        }
    )
    save_manifest(
        with_entry(load_scratch(window._scratch_dir), "egm_banks", entry), window._scratch_dir
    )
    window._refresh_scratch()


def test_validate_marks_the_scratch_tree(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Well formed", "prose")  # over bank lpred_a_2026-06-27
    obs_id = observation_id("Well formed")
    _stage_scratch_bank(window, "lpred_a_2026-06-27")  # its bank is also in scratch -> resolves
    assert _scratch_item_status(window, obs_id) is ArtifactStatus.PRESENT  # unvalidated grey ring

    window._validate_phase()  # validates scratch even with no phase loaded

    assert window._scratch_validated is True
    assert (
        _scratch_item_status(window, obs_id) is ArtifactStatus.OK
    )  # well-formed + resolved -> green
    assert "scratch" in window.statusBar().currentMessage()


def test_scratch_validation_survives_a_later_save(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("First", "prose")
    _stage_scratch_bank(window, "lpred_a_2026-06-27")
    window._validate_phase()
    assert window._scratch_validated is True

    window._write_observation("Second", "prose")  # a fresh save must not wipe the marks

    assert _scratch_item_status(window, observation_id("First")) is ArtifactStatus.OK
    assert _scratch_item_status(window, observation_id("Second")) is ArtifactStatus.OK


def _stage_scratch_observation(window: MainWindow, obs_id: str, banks: list[str]) -> None:
    """Save an observation (referencing ``banks``) into the scratch area + index it."""
    obs = Observation.model_validate(
        {
            "schema_version": "1",
            "id": obs_id,
            "date": "2026-07-05",
            "title": obs_id,
            "description": "d",
            "view_state": {"banks_loaded": banks},
        }
    )
    save_observation(obs, window._scratch_dir)
    save_manifest(
        with_entry(load_scratch(window._scratch_dir), "observations", observation_entry(obs)),
        window._scratch_dir,
    )
    window._refresh_scratch()


def test_scratch_observation_resolves_against_the_loaded_phase(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)  # the fixture phase carries real bank ids
    assert window._phase_manifest is not None
    phase_bank = next(e.id for e in (window._phase_manifest.egm_banks or []))
    _stage_scratch_observation(window, "obs_cross_scope_2026-07-05", [phase_bank])

    window._validate_phase()  # scratch resolves against scratch + the loaded phase

    # the observation's bank lives in the loaded phase -> resolved, not unresolved
    assert _scratch_item_status(window, "obs_cross_scope_2026-07-05") is ArtifactStatus.OK


def test_scratch_observation_unresolved_when_its_bank_is_nowhere(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    _stage_scratch_observation(window, "obs_dangling_2026-07-05", ["lpred_absent_2026-06-27"])

    window._validate_phase()

    # the bank is in neither scratch nor the phase -> amber unresolved
    assert _scratch_item_status(window, "obs_dangling_2026-07-05") is ArtifactStatus.UNRESOLVED


def test_scratch_menu_includes_viewers_and_promote(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Note", "prose")
    labels = [
        a.text() for a in window._scratch_tree._artifact_menu(observation_id("Note")).actions()
    ]
    assert "Promote to phase" in labels  # scratch-specific action
    assert "Open observation" in labels  # the viewers are back on (2c-B)


def test_all_bank_paths_span_scratch_and_phase(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    assert window._phase_manifest is not None
    phase_bank = next(e.id for e in (window._phase_manifest.egm_banks or []))
    _stage_scratch_bank(window, "lpred_scratch_2026-06-27")

    paths = window._all_bank_paths()

    assert "lpred_scratch_2026-06-27" in paths  # a scratch bank...
    assert (
        phase_bank in paths
    )  # ...and a phase bank -> Flow C previews figures from either (item 3)


def test_open_scratch_observation_reloads_banks_cross_scope(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    assert window._phase_manifest is not None
    phase_bank = next(e.id for e in (window._phase_manifest.egm_banks or []))
    _stage_scratch_observation(window, "obs_open_me_2026-07-05", [phase_bank])

    seen_ids: list[str] = []
    seen_scope: list[Path] = []

    def fake_reload(ids: Sequence[str], scope_dirs: Sequence[Path]) -> tuple[int, int]:
        seen_ids.extend(ids)
        seen_scope.extend(scope_dirs)
        window._explore_df = _explore_frame()
        return 1, 0

    monkeypatch.setattr(window, "_reload_banks", fake_reload)
    monkeypatch.setattr(window._explore_view.result_list, "select_row_ids", lambda _ids: None)

    window._on_scratch_action("open_observation", "obs_open_me_2026-07-05")

    assert seen_ids == [phase_bank]  # the scratch observation's bank
    assert Path(window._scratch_dir) in seen_scope and window._phase_dir in seen_scope


def _bank_file(bank: ClassifierBank, tmp_path: Path, bank_id: str, name: str = "bank.h5") -> Path:
    path = tmp_path / name
    write_classifier_bank(dataclasses.replace(bank, id=bank_id), path)
    return path


def test_load_bank_to_scratch_indexes_it(
    qtbot: QtBot, tmp_path: Path, tiny_classifier_bank: ClassifierBank
) -> None:
    window = _window(qtbot, tmp_path)
    path = _bank_file(tiny_classifier_bank, tmp_path, "tbank_loaded_2026-06-27")
    window._index_producer(str(path), kind="bank", target="scratch")
    assert "tbank_loaded_2026-06-27" in _scratch_ids(window)  # a bank now sits in the scratch tree
    assert not window._scratch_pane.isHidden()


def test_load_bank_to_phase_indexes_into_the_phase(
    qtbot: QtBot, tmp_path: Path, tiny_classifier_bank: ClassifierBank
) -> None:
    window = _window(qtbot, tmp_path)
    _open_phase(window, tmp_path)
    path = _bank_file(tiny_classifier_bank, tmp_path, "tbank_loaded_2026-06-27")
    window._index_producer(str(path), kind="bank", target="phase")
    assert window._phase_manifest is not None
    assert "tbank_loaded_2026-06-27" in entries_by_id(window._phase_manifest)


def test_load_banks_submenu_indexes_each_pick(
    qtbot: QtBot,
    tmp_path: Path,
    tiny_classifier_bank: ClassifierBank,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(qtbot, tmp_path)
    path = _bank_file(tiny_classifier_bank, tmp_path, "tbank_wired_2026-06-27")
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(path)], "")
    )
    monkeypatch.setattr(window, "_open_bank_explore", lambda *a, **k: None)  # skip the Flow A load
    window._load_banks("scratch")
    assert "tbank_wired_2026-06-27" in _scratch_ids(window)  # the submenu wired indexing through


def test_promote_a_producer_reindexes_without_moving_the_file(
    qtbot: QtBot, tmp_path: Path, tiny_classifier_bank: ClassifierBank
) -> None:
    window = _window(qtbot, tmp_path)
    path = _bank_file(tiny_classifier_bank, tmp_path, "tbank_loaded_2026-06-27")
    window._index_producer(str(path), kind="bank", target="scratch")
    _open_phase(window, tmp_path)

    window._promote_scratch("tbank_loaded_2026-06-27")

    assert window._phase_manifest is not None
    assert "tbank_loaded_2026-06-27" in entries_by_id(window._phase_manifest)  # now in the phase
    assert "tbank_loaded_2026-06-27" not in _scratch_ids(window)  # gone from scratch
    assert path.exists()  # a producer entry is a pointer -> its file is NOT moved


def test_delete_removes_the_scratch_artifact(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._explore_df = _explore_frame()
    window._write_observation("Delete me", "prose")
    obs_id = observation_id("Delete me")

    window._delete_scratch(obs_id)

    assert not (Path(window._scratch_dir) / "observations" / f"{obs_id}.json").exists()
    assert _scratch_ids(window) == []
    assert window._scratch_pane.isHidden()
    assert "Deleted" in window.statusBar().currentMessage()


# -- auto-add dependencies (B10h-1b) ---------------------------------------------------


def test_promote_a_figure_pulls_its_scratch_bank(qtbot: QtBot, tmp_path: Path) -> None:
    """The message-13 gap: promoting a figure also moves the scratch bank it consumes."""
    window = _window(qtbot, tmp_path)
    _stage_scratch_bank(window, "lpred_a_2026-06-27")  # the bank fig_demo consumes
    window._save_figure(_figure_spec())  # fig_demo -> scratch, consumes lpred_a
    _open_phase(window, tmp_path)

    window._promote_scratch("fig_demo")

    assert window._phase_manifest is not None
    phase = entries_by_id(window._phase_manifest)
    assert "fig_demo" in phase  # the figure...
    assert "lpred_a_2026-06-27" in phase  # ...and its bank, pulled along (auto-add)
    assert _scratch_ids(window) == []  # both left scratch
    assert "+1 dependency" in window.statusBar().currentMessage()


def test_auto_add_off_leaves_the_dependency_in_scratch(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    window._auto_add_deps = False  # Settings toggle off
    _stage_scratch_bank(window, "lpred_a_2026-06-27")
    window._save_figure(_figure_spec())
    _open_phase(window, tmp_path)

    window._promote_scratch("fig_demo")

    assert window._phase_manifest is not None
    assert "fig_demo" in entries_by_id(window._phase_manifest)  # only the figure moves
    assert "lpred_a_2026-06-27" not in entries_by_id(window._phase_manifest)
    assert _scratch_ids(window) == ["lpred_a_2026-06-27"]  # its bank stays in scratch


def test_save_observation_to_phase_pulls_a_scratch_bank(qtbot: QtBot, tmp_path: Path) -> None:
    window = _window(qtbot, tmp_path)
    _stage_scratch_bank(window, "lpred_a_2026-06-27")
    _open_phase(window, tmp_path)
    window._explore_df = _explore_frame()  # captured banks_loaded == [lpred_a_2026-06-27]

    window._write_observation("Note", "prose", target="phase")

    assert window._phase_manifest is not None
    phase = entries_by_id(window._phase_manifest)
    assert observation_id("Note") in phase  # the observation...
    assert "lpred_a_2026-06-27" in phase  # ...and the bank it references, pulled from scratch
    assert "lpred_a_2026-06-27" not in _scratch_ids(window)
