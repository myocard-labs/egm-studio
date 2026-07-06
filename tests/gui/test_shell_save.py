"""Tests for Save-observation wiring into a loaded phase (Block 10c).

The modal dialog is exercised in ``test_save_observation_dialog``; here the shell's
gating (``_save_observation``) and the testable write core (``_write_observation``) are
driven directly — the latter writes the JSON, indexes the manifest, and reloads the tree.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
from myocard_egm_contracts import Role
from myocard_egm_data.phases import (
    MANIFEST_FILENAME,
    FigureEntry,
    FigureSpec,
    ObservationEntry,
    TraceRef,
    ViewState,
    load_figure_spec,
    load_observation,
)
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import MainWindow
from myocard_egm_studio.save import (
    build_observation,
    observation_entry,
    observation_id,
    save_manifest,
    save_observation,
    with_entry,
)
from myocard_egm_studio.view_model import entries_by_id
from myocard_egm_studio.view_model.phase_actions import type_actions

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def _explore_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": [0, 1],
            "source": ["lpred_a_2026-06-27", "lpred_a_2026-06-27"],
            "trace_idx": [0, 1],
            "peak_to_peak": [1.0, 2.0],
        }
    )


def _phase_copy(tmp_path: Path) -> Path:
    """A writable phase dir: just the fixture's manifest (referenced files may be absent)."""
    phase = tmp_path / "phase_1_5"
    phase.mkdir()
    shutil.copy(_FIXTURE_DIR / MANIFEST_FILENAME, phase / MANIFEST_FILENAME)
    return phase


def test_save_observation_menu_offers_both_targets(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.findChild(QtWidgets.QMenu, "saveObservation") is not None  # a submenu now (2d)
    assert window.findChild(QtGui.QAction, "saveObservationToScratch") is not None
    assert window.findChild(QtGui.QAction, "saveObservationToPhase") is not None


def test_save_observation_with_nothing_loaded_asks_for_a_bank(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._save_observation()  # no bank -> guarded, no dialog (no phase is fine: scratch mode)
    assert "Load a bank" in window.statusBar().currentMessage()


def test_save_observation_needs_a_bank(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(_phase_copy(tmp_path)))
    window._save_observation()  # phase but no bank -> guarded
    assert "Load a bank" in window.statusBar().currentMessage()


def test_write_observation_writes_file_and_indexes_it(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    window._explore_df = _explore_frame()

    window._write_observation("Late gain in bipolar", "amplitude climbs toward the scar edge")

    obs_id = observation_id("Late gain in bipolar")
    written = phase / "observations" / f"{obs_id}.json"
    assert written.exists()
    observation = load_observation(written)  # the file round-trips as a valid Observation
    assert observation.id == obs_id
    assert observation.description.startswith("amplitude climbs")

    assert window._phase_manifest is not None  # reloaded after the write
    assert obs_id in entries_by_id(window._phase_manifest)  # indexed into the manifest
    assert f"Saved observation {obs_id}" in window.statusBar().currentMessage()


def test_write_observation_captures_the_loaded_banks(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    window._explore_df = _explore_frame()

    window._write_observation("Bank note", "prose")

    observation = load_observation(phase / "observations" / f"{observation_id('Bank note')}.json")
    assert observation.view_state is not None
    assert observation.view_state.model_dump()["banks_loaded"] == ["lpred_a_2026-06-27"]


_FIXTURE_PARENT = "obs_saturation_iafdb_2026-06-26"  # the observation already in the fixture phase


def test_existing_observation_ids_lists_phase_observations(qtbot: QtBot, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window._existing_observation_ids() == []  # no phase yet
    window._load_phase_into_tree(str(_phase_copy(tmp_path)))
    assert _FIXTURE_PARENT in window._existing_observation_ids()


def test_write_observation_records_parent_links(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    window._explore_df = _explore_frame()

    window._write_observation(
        "Builds on saturation", "extends the earlier finding", [_FIXTURE_PARENT]
    )

    observation = load_observation(
        phase / "observations" / f"{observation_id('Builds on saturation')}.json"
    )
    assert observation.references is not None
    assert observation.references.model_dump()["observations"] == [_FIXTURE_PARENT]


def test_saving_an_observation_keeps_the_phase_validated(qtbot: QtBot, tmp_path: Path) -> None:
    """If the phase was validated first, saving an observation re-runs validation (never
    downgrades the tree to existence-only) and still reports the save."""
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    window._explore_df = _explore_frame()
    window._validate_phase()
    assert window._phase_validated is True

    window._write_observation("Post-validate note", "prose")

    assert window._phase_validated is True  # validation preserved across the write
    assert "Saved observation" in window.statusBar().currentMessage()  # save message wins


def test_saving_an_observation_does_not_fabricate_validation(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    window._explore_df = _explore_frame()
    assert window._phase_validated is False  # never validated

    window._write_observation("Unvalidated note", "prose")

    assert window._phase_validated is False  # still existence-only, not silently validated


def test_edit_observation_action_is_available(qtbot: QtBot) -> None:
    edit = next(a for a in type_actions(Role.observation) if a.id == "edit_observation")
    assert edit.available  # the Phase-tree "Edit observation" item is enabled


def _created_observation(window: MainWindow, phase: Path, title: str, description: str) -> Path:
    """Save an observation into the window's loaded phase and return its file path."""
    window._explore_df = _explore_frame()
    window._write_observation(title, description)
    return phase / "observations" / f"{observation_id(title)}.json"


def test_apply_observation_edit_rewrites_prose_keeping_id(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    path = _created_observation(window, phase, "First finding", "first prose")
    existing = load_observation(path)

    window._apply_observation_edit(existing, "First finding", "revised prose", [_FIXTURE_PARENT])

    reloaded = load_observation(path)
    assert reloaded.id == existing.id  # same file, same id
    assert reloaded.description == "revised prose"
    assert reloaded.references is not None
    assert reloaded.references.model_dump()["observations"] == [_FIXTURE_PARENT]
    assert f"Updated observation {existing.id}" in window.statusBar().currentMessage()


def test_apply_observation_edit_preserves_the_usage_tag(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    path = _created_observation(window, phase, "Paper finding", "prose")
    existing = load_observation(path)
    # Promote the entry to informed_paper, then reload so the window sees it.
    assert window._phase_manifest is not None
    promoted = observation_entry(existing, usage_tag="informed_paper")
    save_manifest(with_entry(window._phase_manifest, "observations", promoted), phase)
    window._load_phase_into_tree(str(phase))

    window._apply_observation_edit(existing, "Paper finding", "edited prose", [])

    assert window._phase_manifest is not None
    entry = entries_by_id(window._phase_manifest)[existing.id]
    assert isinstance(entry, ObservationEntry)
    assert entry.usage_tag is not None and entry.usage_tag.value == "informed_paper"  # not reset


def test_edit_observation_missing_file_reports(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    window._edit_observation("obs_gone_2026-01-01", phase / "observations" / "obs_gone.json")
    assert "Could not open observation" in window.statusBar().currentMessage()


def test_open_observation_action_is_available(qtbot: QtBot) -> None:
    open_action = next(a for a in type_actions(Role.observation) if a.id == "open_observation")
    assert open_action.available  # "Open observation" (reload the view) is enabled


def _saved_observation(phase: Path, **kwargs: object) -> Path:
    """Write a standalone observation file into ``phase`` and return its path."""
    observation = build_observation(title="Reload me", description="prose", **kwargs)  # type: ignore[arg-type]
    return save_observation(observation, phase)


def test_open_observation_without_a_view_state_reports(qtbot: QtBot, tmp_path: Path) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    path = _saved_observation(phase)  # no view_state captured
    window._open_observation("obs_reload_me_x", path, scope_dirs=[window._phase_dir])
    assert "saved no view" in window.statusBar().currentMessage()


def test_restore_filter_decides_by_parseability(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    applied: list[object] = []
    monkeypatch.setattr(window._filter_panel, "set_spec", lambda spec: applied.append(spec))
    monkeypatch.setattr(window, "_on_recalculate", lambda spec: applied.append(("recalc", spec)))

    assert window._restore_filter(None) == "no filter"
    assert window._restore_filter("Match all: peak_to_peak > 1.5").startswith("filter: ")
    assert applied  # a parseable filter drives set_spec + recalculate
    applied.clear()
    assert "not auto-applied" in window._restore_filter("free text nobody can parse")
    assert applied == []  # an unparseable filter touches neither


def test_restore_selection_selects_matching_pinned_traces(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._explore_df = _explore_frame()  # row_ids 0,1 are lpred_a trace 0,1
    picked: list[list[int]] = []
    monkeypatch.setattr(window._explore_view.result_list, "select_row_ids", picked.append)

    count = window._restore_selection(
        [
            TraceRef(bank="lpred_a_2026-06-27", index=1),  # -> row_id 1
            TraceRef(bank="lpred_a_2026-06-27", index=9),  # no such trace -> skipped
        ]
    )
    assert count == 1
    assert picked == [[1]]


def test_open_observation_reloads_banks_filter_and_selection(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    path = _saved_observation(
        phase,
        view_state=ViewState.model_validate({"banks_loaded": ["lpred_a_2026-06-27"]}),
        traces=[TraceRef(bank="lpred_a_2026-06-27", index=0)],
    )

    # Bank loading needs real files; stub it to report one loaded + populate the frame.
    def fake_reload(bank_ids: object, scope_dirs: object) -> tuple[int, int]:
        window._explore_df = _explore_frame()
        return 1, 0

    monkeypatch.setattr(window, "_reload_banks", fake_reload)
    monkeypatch.setattr(window._explore_view.result_list, "select_row_ids", lambda _ids: None)

    window._open_observation("obs_reload_me_x", path, scope_dirs=[window._phase_dir])

    assert window._modes_stack.currentIndex() == 0  # landed on Signal exploration
    message = window.statusBar().currentMessage()
    assert "Reloaded" in message and "1 bank(s)" in message and "1 trace(s) selected" in message


def test_open_observation_when_no_banks_resolve_reports(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))
    path = _saved_observation(
        phase, view_state=ViewState.model_validate({"banks_loaded": ["lpred_absent_2026-06-27"]})
    )
    monkeypatch.setattr(window, "_reload_banks", lambda ids, scope_dirs: (0, 1))
    window._open_observation("obs_reload_me_x", path, scope_dirs=[window._phase_dir])
    assert "none of its 1 bank(s)" in window.statusBar().currentMessage()


def _figure_spec(**overrides: object) -> FigureSpec:
    raw: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_demo",
        "description": "demo",
        "recipe": "prediction-histogram",
        "inputs": {"groups": [{"name": "g", "bank_id": "lpred_a_2026-06-27"}]},
        "output": {"format": "pdf", "path": "out.pdf"},
    }
    raw.update(overrides)
    return FigureSpec.model_validate(raw)


def test_save_figure_into_phase_writes_the_spec_and_indexes_it(
    qtbot: QtBot, tmp_path: Path
) -> None:
    phase = _phase_copy(tmp_path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(phase))

    window._save_figure(_figure_spec(illustrates_observations=[_FIXTURE_PARENT]))

    written = phase / "figures" / "fig_demo.json"
    assert written.exists()
    assert load_figure_spec(written).id == "fig_demo"  # spec round-trips at the canonical path
    assert window._phase_manifest is not None
    entry = entries_by_id(window._phase_manifest)["fig_demo"]
    assert isinstance(entry, FigureEntry)
    assert [b.root for b in entry.consumes_banks or []] == ["lpred_a_2026-06-27"]
    assert [o.root for o in entry.consumes_observations or []] == [_FIXTURE_PARENT]
    assert "Saved figure fig_demo into the phase" in window.statusBar().currentMessage()


def test_current_selection_dispatches_by_active_flow(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window._explore_view.result_list, "selected_row_ids", lambda: [1, 2])
    monkeypatch.setattr(window._diagnostics_view.result_list, "selected_row_ids", lambda: [7])

    window._modes_stack.setCurrentIndex(0)  # Flow A (signal exploration)
    assert window._current_selection() == [1, 2]
    window._modes_stack.setCurrentIndex(1)  # Noise — no trace selection
    assert window._current_selection() == []
    window._modes_stack.setCurrentIndex(2)  # Flow B (ML diagnostics)
    assert window._current_selection() == [7]
    window._modes_stack.setCurrentIndex(3)  # Flow C — no trace selection
    assert window._current_selection() == []
