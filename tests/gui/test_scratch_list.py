"""pytest-qt tests for the scratch sidebar list widget (B10e)."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets import ScratchList
from myocard_egm_studio.save import ScratchArtifact


def _artifacts() -> list[ScratchArtifact]:
    return [
        ScratchArtifact("obs_note_2026-07-05", "observation", Path("/tmp/obs.json")),
        ScratchArtifact("fig_demo_2026-07-05", "figure", Path("/tmp/fig.json")),
    ]


def test_set_artifacts_populates_the_list(qtbot: QtBot) -> None:
    widget = ScratchList()
    qtbot.addWidget(widget)
    widget.set_artifacts(_artifacts())
    listing = widget.findChild(QtWidgets.QListWidget, "scratchItems")
    assert isinstance(listing, QtWidgets.QListWidget)
    assert listing.count() == 2
    assert "obs_note_2026-07-05" in listing.item(0).text()
    assert "fig_demo_2026-07-05" in listing.item(1).text()


def test_set_artifacts_replaces_previous(qtbot: QtBot) -> None:
    widget = ScratchList()
    qtbot.addWidget(widget)
    widget.set_artifacts(_artifacts())
    widget.set_artifacts([])  # a promote/delete that emptied scratch
    listing = widget.findChild(QtWidgets.QListWidget, "scratchItems")
    assert isinstance(listing, QtWidgets.QListWidget)
    assert listing.count() == 0
