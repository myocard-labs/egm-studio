"""Tests for File > Open phase wiring into the right-rail Phase tree (Block 6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from myocard_egm_data.phases import load_phase_dir
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import MainWindow
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


def test_view_traces_action_routes_to_bank_loader(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _loaded_window(qtbot)
    opened: list[str] = []
    monkeypatch.setattr(window, "_open_bank_explore", opened.append)
    window._on_phase_action("view_traces", _BANK_ID)
    assert opened == [str(_FIXTURE_DIR / _BANK_PATH)]
