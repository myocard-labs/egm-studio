"""Tests for File > Open phase wiring into the right-rail Phase tree (Block 6)."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import MainWindow

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


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
