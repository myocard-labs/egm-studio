"""pytest-qt tests for the loaded-runs roster (gui/widgets/run_list, B8f)."""

from __future__ import annotations

from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import LoadedRunsList


def _rows(roster: LoadedRunsList) -> list[QtWidgets.QWidget]:
    return roster.findChildren(QtWidgets.QWidget, "runRow")


def test_set_runs_renders_one_row_each(qtbot: QtBot) -> None:
    roster = LoadedRunsList()
    qtbot.addWidget(roster)
    roster.set_runs([("v1", "#111111"), ("v1.5", "#222222")])
    assert len(_rows(roster)) == 2


def test_remove_button_emits_the_run_label(qtbot: QtBot) -> None:
    roster = LoadedRunsList()
    qtbot.addWidget(roster)
    roster.set_runs([("v1.5", "#222222")])
    received: list[str] = []
    roster.removeRequested.connect(received.append)
    button = roster.findChild(QtWidgets.QToolButton, "runRowRemove")
    assert button is not None
    button.click()
    assert received == ["v1.5"]


def test_empty_clears_the_roster(qtbot: QtBot) -> None:
    roster = LoadedRunsList()
    qtbot.addWidget(roster)
    roster.set_runs([("v1", "#111111")])
    roster.set_runs([])
    assert _rows(roster) == []
