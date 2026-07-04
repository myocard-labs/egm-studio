"""pytest-qt smoke tests for the Block 4 layout shell (ADR-025).

Per ADR-013 these check structure + wiring, not pixel positions: the window
builds, the three work-area columns exist, the menu bar is populated, sidebars
collapse/expand (menu checkmark in sync), and the mode control is exclusive. Run
headless under the offscreen QPA platform (CI uses xvfb).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui import shell as shell_mod
from myocard_egm_studio.gui.shell import CollapsibleSidebar, MainWindow
from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.widgets import TraceContainer, TraceView
from myocard_egm_studio.view_model.filtering import Condition, FilterSpec


def test_shell_builds_with_three_columns(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "egm-studio"
    splitter = window.findChild(QtWidgets.QSplitter, "columnSplitter")
    assert splitter is not None
    assert splitter.count() == 3  # left | main | right


def test_menu_bar_has_expected_top_level_menus(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    titles = [action.text() for action in window.menuBar().actions()]
    assert titles == ["&File", "&View", "&Help"]


def test_left_sidebar_collapses_and_expands_via_menu(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    left = window.findChild(CollapsibleSidebar, "leftSidebar")
    action = window.findChild(QtGui.QAction, "toggleLeftSidebar")
    assert left is not None
    assert action is not None
    assert not left.is_collapsed()
    assert action.isChecked()  # ticked == expanded

    action.trigger()
    assert left.is_collapsed()
    assert not action.isChecked()

    action.trigger()
    assert not left.is_collapsed()
    assert action.isChecked()


def test_sidebar_toggle_button_keeps_menu_in_sync(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    right = window.findChild(CollapsibleSidebar, "rightSidebar")
    action = window.findChild(QtGui.QAction, "toggleRightSidebar")
    assert right is not None
    assert action is not None

    right.toggleRequested.emit()  # as if the in-panel collapse button was clicked
    assert right.is_collapsed()
    assert not action.isChecked()


def test_mode_control_is_exclusive(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    buttons = window.findChildren(QtWidgets.QPushButton, "modeButton")
    assert len(buttons) == 3
    assert buttons[0].isChecked()  # signal-exploration default

    buttons[2].click()
    assert buttons[2].isChecked()
    assert not buttons[0].isChecked()


def _open(qtbot: QtBot, bank: ClassifierBank, tmp_path: Path) -> MainWindow:
    path = tmp_path / "bank.h5"
    write_classifier_bank(bank, path)
    window = MainWindow()
    qtbot.addWidget(window)
    window._open_bank_explore(str(path))
    return window


def test_open_bank_populates_result_list(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    table = window._explore_view.result_list._table
    assert table.rowCount() == len(tiny_classifier_bank.traces)
    assert "Loaded" in window.statusBar().currentMessage()


def test_selecting_a_trace_shows_the_detail(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    window._explore_view.result_list._table.selectRow(0)
    assert window.findChild(TraceContainer) is not None


def test_filter_narrows_the_result_list(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    total = window._explore_view.result_list._table.rowCount()
    window._on_filter_changed(FilterSpec((Condition("label_name", "==", "fibrotic"),)))
    kept = window._explore_view.result_list._table.rowCount()
    assert 0 < kept < total
    assert "match" in window.statusBar().currentMessage()


def test_open_bank_cancel_aborts_the_load(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hitting Cancel mid-load trips the progress dialog; the next progress tick
    raises, the load unwinds, and no bank state is committed."""
    window = MainWindow()
    qtbot.addWidget(window)

    def cancel_then_progress(_path: str, *, progress: Callable[[int, int], None]) -> object:
        dialog = window.findChild(QtWidgets.QProgressDialog)
        assert dialog is not None  # the shell shows it before load_exploration runs
        dialog.cancel()  # as if the user clicked Cancel
        progress(0, 10)  # sees wasCanceled -> raises _LoadCancelled
        raise AssertionError("progress tick did not abort after Cancel")

    monkeypatch.setattr(shell_mod, "load_exploration", cancel_then_progress)
    window._open_bank_explore(str(tmp_path / "unused.h5"))

    assert "canceled" in window.statusBar().currentMessage().lower()
    assert window._explore_df is None  # nothing committed


def test_theme_change_restyles_the_detail(
    qtbot: QtBot,
    qapp: QtWidgets.QApplication,
    tiny_classifier_bank: ClassifierBank,
    tmp_path: Path,
) -> None:
    window = _open(qtbot, tiny_classifier_bank, tmp_path)
    window._explore_view.result_list._table.selectRow(0)
    light = window.findChild(QtGui.QAction, "themeAction_light")
    assert light is not None
    light.trigger()
    content = window._explore_view._waveforms.content
    assert isinstance(content, TraceView)
    assert content.container.palette == plot_palette("light")
