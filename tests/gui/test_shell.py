"""pytest-qt smoke tests for the Block 4 layout shell (ADR-025).

Per ADR-013 these check structure + wiring, not pixel positions: the window
builds, the three work-area columns exist, the menu bar is populated, sidebars
collapse/expand (menu checkmark in sync), and the mode control is exclusive. Run
headless under the offscreen QPA platform (CI uses xvfb).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from myocard_egm_data.banks import ClassifierBank, write_classifier_bank
from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import CollapsibleSidebar, MainWindow
from myocard_egm_studio.gui.theme import plot_palette
from myocard_egm_studio.gui.widgets import TraceContainer, TraceData


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


def test_open_bank_shows_trace_container(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    t = np.arange(200, dtype=np.float64) / 1000.0
    traces = [TraceData(np.sin(2.0 * np.pi * 5.0 * t), 1000.0, f"t{i}") for i in range(3)]
    window._show_traces(traces, source="demo.h5")
    assert window.findChild(TraceContainer) is not None


def test_theme_change_restyles_open_traces(qtbot: QtBot, qapp: QtWidgets.QApplication) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    t = np.arange(100, dtype=np.float64) / 1000.0
    window._show_traces([TraceData(np.sin(t), 1000.0, "x")], source="d.h5")
    light = window.findChild(QtGui.QAction, "themeAction_light")
    assert light is not None
    light.trigger()

    content = window._work_area.content
    assert isinstance(content, TraceContainer)
    assert content.palette == plot_palette("light")


def test_open_bank_populates_selector_and_view(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    path = tmp_path / "bank.h5"
    write_classifier_bank(tiny_classifier_bank, path)
    window = MainWindow()
    qtbot.addWidget(window)

    window._load_bank_into_view(str(path))
    assert len(window._trace_selector.selected_traces()) == min(3, len(tiny_classifier_bank.traces))
    assert window.findChild(TraceContainer) is not None
