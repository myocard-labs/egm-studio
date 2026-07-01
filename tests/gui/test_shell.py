"""pytest-qt smoke tests for the Block 4 layout shell (ADR-025).

Per ADR-013 these check structure + wiring, not pixel positions: the window
builds, the three work-area columns exist, the menu bar is populated, sidebars
collapse/expand (menu checkmark in sync), and the mode control is exclusive. Run
headless under the offscreen QPA platform (CI uses xvfb).
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.shell import CollapsibleSidebar, MainWindow


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
