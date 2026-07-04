"""Tests for File > Open phase wiring into the right-rail Phase tree (Block 6)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from myocard_egm_contracts import Role, role_of
from myocard_egm_data.phases import load_phase_dir
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.gui import shell as shell_mod
from myocard_egm_studio.gui.shell import MainWindow, _LoadedBank
from myocard_egm_studio.view_model import entries_by_id
from myocard_egm_studio.view_model.phase_actions import reveal_target

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"
_ENTRIES = entries_by_id(load_phase_dir(_FIXTURE_DIR))
_BANK_ID = next(aid for aid in _ENTRIES if aid.startswith("tbank_"))
_BANK_PATH = _ENTRIES[_BANK_ID].path


def test_open_phase_action_exists(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.findChild(QtGui.QAction, "openPhase") is not None


def test_load_phase_populates_tree(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(_FIXTURE_DIR))
    assert window._phase_tree.topLevelItemCount() == 10
    message = window.statusBar().currentMessage()
    assert "Loaded phase" in message
    assert "not yet validated" in message  # load is existence-only


def test_bad_phase_path_reports_and_leaves_tree_empty(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(_FIXTURE_DIR / "does_not_exist"))
    assert "Could not open phase" in window.statusBar().currentMessage()
    assert window._phase_tree.topLevelItemCount() == 0


def test_open_phase_marks_missing_files_red(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(_FIXTURE_DIR))  # fixture paths don't resolve
    group = window._phase_tree.topLevelItem(0)  # Training banks group header
    assert group is not None
    assert group.foreground(0).color().name() == "#f85149"  # rolls up red
    child = group.child(0)
    assert child is not None
    assert not child.icon(0).isNull()  # per-item status dot is set


def test_validate_phase_action(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.findChild(QtGui.QAction, "validatePhase") is not None
    window._validate_phase()  # nothing loaded yet
    assert "Open a phase first" in window.statusBar().currentMessage()
    window._load_phase_into_tree(str(_FIXTURE_DIR))
    window._validate_phase()
    message = window.statusBar().currentMessage()
    assert "Validated phase" in message
    assert "missing" in message  # fixture files are all absent -> counted as missing


def _loaded_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    window._load_phase_into_tree(str(_FIXTURE_DIR))
    return window


def test_copy_id_action_copies_to_clipboard(qtbot: QtBot) -> None:
    window = _loaded_window(qtbot)
    window._on_phase_action("copy_id", _BANK_ID)
    app = QtWidgets.QApplication.instance()
    assert isinstance(app, QtWidgets.QApplication)
    assert app.clipboard().text() == _BANK_ID
    assert "Copied id" in window.statusBar().currentMessage()


def test_show_metadata_opens_scrollable_dialog(qtbot: QtBot) -> None:
    window = _loaded_window(qtbot)
    window._on_phase_action("show_metadata", _BANK_ID)
    # fixture bank file doesn't exist -> friendly error text, still surfaced in a dialog
    assert _BANK_ID in window._last_metadata_text
    dialog = window._metadata_dialog
    assert dialog is not None
    view = dialog.findChild(QtWidgets.QPlainTextEdit)
    assert view is not None
    assert view.toPlainText() == window._last_metadata_text


def test_reveal_action_targets_the_artifact_folder(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _loaded_window(qtbot)
    captured: list[Path] = []
    monkeypatch.setattr(window, "_reveal", captured.append)
    window._on_phase_action("reveal_file", _BANK_ID)
    assert captured == [reveal_target(_FIXTURE_DIR, _BANK_PATH)]


def test_bank_actions_dispatch_focus_and_replace(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explore signal always replaces + opens Explore; View feature distributions
    opens Summary and appends only once a bank is already loaded (B7.8b-fix)."""
    window = _loaded_window(qtbot)
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        window,
        "_open_bank_explore",
        lambda _path, *, focus="summary", replace=True: calls.append((focus, replace)),
    )
    window._on_phase_action("explore_signal", _BANK_ID)
    window._on_phase_action("view_feature_distributions", _BANK_ID)
    window._loaded_banks = [_LoadedBank("x", "x", pd.DataFrame(), [])]  # a bank is now loaded
    window._on_phase_action("explore_signal", _BANK_ID)
    window._on_phase_action("view_feature_distributions", _BANK_ID)
    assert calls == [
        ("explore", True),  # explore signal replaces
        ("summary", True),  # view feature distributions, none loaded -> replace
        ("explore", True),  # explore signal replaces even with a bank loaded
        ("summary", False),  # view feature distributions, a bank loaded -> append
    ]


def test_view_curves_action_loads_run_into_flow_b(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The training-run 'View training curves' action resolves the run.json and feeds
    it to Flow B's Training tab (the read is stubbed — the fixture files are absent)."""
    window = _loaded_window(qtbot)
    run_id = next(aid for aid in _ENTRIES if role_of(aid) == Role.training_run)
    seen: list[str] = []

    def fake_loader(path: str, *, metric_key: str = "auroc") -> TrainingCurve:
        seen.append(path)
        epochs = np.arange(1, 4)
        return TrainingCurve(
            epochs=epochs,
            loss={"val": np.asarray(1.0 / epochs, dtype=np.float64)},
            metric={"val": np.asarray(0.6 + 0.1 * epochs, dtype=np.float64)},
            metric_name="AUROC",
        )

    monkeypatch.setattr(shell_mod, "training_curve_from_run", fake_loader)
    window._on_phase_action("view_curves", run_id)
    assert seen == [str(_FIXTURE_DIR / _ENTRIES[run_id].path)]  # resolved from the manifest
    assert [name for name, _ in window._loaded_runs] == [run_id]
    assert window._modes_stack.currentIndex() == 1  # switched to ML diagnostics
    assert window._diagnostics_view._tabs.currentIndex() == 2  # Training tab


def test_view_ml_diagnostics_loads_bank_then_lands_on_flow_b(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prediction bank's 'View ML diagnostics' loads it (additive-aware) + shows Flow B."""
    window = _loaded_window(qtbot)
    pred_id = next(
        aid
        for aid in _ENTRIES
        if role_of(aid) in (Role.labeled_prediction_bank, Role.unlabeled_prediction_bank)
    )
    calls: list[tuple[str | None, bool]] = []
    monkeypatch.setattr(
        window,
        "_open_bank_explore",
        lambda _path, *, focus="summary", replace=True: calls.append((focus, replace)),
    )
    window._on_phase_action("view_ml_diagnostics", pred_id)
    assert calls == [(None, True)]  # no Flow A tab focus; replace (nothing loaded yet)
    assert window._modes_stack.currentIndex() == 1  # landed on ML diagnostics
