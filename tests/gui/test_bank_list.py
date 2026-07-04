"""pytest-qt tests for the loaded-banks list (gui/widgets/bank_list)."""

from __future__ import annotations

from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import LoadedBanksList


def _names(widget: LoadedBanksList) -> list[str]:
    return [
        label.text()
        for label in widget.findChildren(QtWidgets.QLabel)
        if label.objectName() == "bankRowName"
    ]


def test_set_banks_renders_one_row_per_bank(qtbot: QtBot) -> None:
    widget = LoadedBanksList()
    qtbot.addWidget(widget)
    widget.set_banks([("Synthetic", "/a.h5", "#0072B2"), ("IAFDB", "/b.h5", "#D55E00")])
    assert _names(widget) == ["Synthetic", "IAFDB"]


def test_remove_button_emits_the_bank_path(qtbot: QtBot) -> None:
    widget = LoadedBanksList()
    qtbot.addWidget(widget)
    widget.set_banks([("Synthetic", "/a.h5", "#0072B2")])
    button = next(
        b for b in widget.findChildren(QtWidgets.QToolButton) if b.objectName() == "bankRowRemove"
    )
    with qtbot.waitSignal(widget.removeRequested) as blocker:
        button.click()
    assert blocker.args == ["/a.h5"]


def test_empty_roster_shows_placeholder(qtbot: QtBot) -> None:
    widget = LoadedBanksList()
    qtbot.addWidget(widget)
    widget.set_banks([("Synthetic", "/a.h5", "#0072B2")])
    widget.set_banks([])  # remove all
    assert _names(widget) == []
    texts = [label.text() for label in widget.findChildren(QtWidgets.QLabel)]
    assert "No banks loaded" in texts
