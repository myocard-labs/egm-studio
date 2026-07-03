"""Tests for the Phase artifact tree widget (gui/widgets/phase_tree)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import load_phase_dir
from PySide6 import QtWidgets
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.widgets.phase_tree import STATUS_ROLE, PhaseTree
from myocard_egm_studio.view_model.phase_groups import phase_artifact_groups
from myocard_egm_studio.view_model.phase_status import ArtifactStatus

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "phase_1_5"


def _top(tree: PhaseTree, i: int) -> QtWidgets.QTreeWidgetItem:
    item = tree.topLevelItem(i)
    assert item is not None
    return item


def _child(item: QtWidgets.QTreeWidgetItem, i: int) -> QtWidgets.QTreeWidgetItem:
    child = item.child(i)
    assert child is not None
    return child


def _populated(qtbot: QtBot) -> PhaseTree:
    tree = PhaseTree()
    qtbot.addWidget(tree)
    tree.set_groups(phase_artifact_groups(load_phase_dir(_FIXTURE_DIR)))
    return tree


def test_ten_group_nodes_with_counts(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    assert tree.topLevelItemCount() == 10
    assert _top(tree, 0).text(0).startswith("Training banks")
    assert "(1)" in _top(tree, 0).text(0)  # fixture has one artifact per group


def test_artifact_and_inline_detail_nodes(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    training = _top(tree, 0)
    assert training.childCount() == 1
    artifact = _child(training, 0)
    assert artifact.text(0).startswith("tbank_")
    details = [_child(artifact, i).text(0) for i in range(artifact.childCount())]
    assert any(t.startswith("path:") for t in details)
    assert any(t.startswith("produced by:") for t in details)


def test_relationship_detail_shown(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    runs = _top(tree, 5)  # training_run group
    run = _child(runs, 0)
    details = [_child(run, i).text(0) for i in range(run.childCount())]
    assert any("Trained on bank" in t for t in details)


def test_set_groups_replaces_prior(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    tree.set_groups([])
    assert tree.topLevelItemCount() == 0


def _populated_ids(tree: PhaseTree) -> list[str]:
    return [_child(_top(tree, i), 0).text(0) for i in range(10) if _top(tree, i).childCount()]


def test_set_statuses_dots_items_and_colours_group_headers(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    statuses = dict.fromkeys(_populated_ids(tree), ArtifactStatus.OK)
    statuses[_child(_top(tree, 0), 0).text(0)] = ArtifactStatus.MISSING  # training bank missing
    tree.set_statuses(statuses)

    missing_item = _child(_top(tree, 0), 0)
    assert missing_item.data(0, STATUS_ROLE) is ArtifactStatus.MISSING
    assert not missing_item.icon(0).isNull()  # a status dot is set on the item
    assert _top(tree, 0).foreground(0).color().name() == "#f85149"  # its group rolls up red
    assert _top(tree, 1).foreground(0).color().name() == "#3fb950"  # an all-OK group green


def test_present_status_is_grey_and_dotted(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    tree.set_statuses(dict.fromkeys(_populated_ids(tree), ArtifactStatus.PRESENT))
    item = _child(_top(tree, 0), 0)
    assert item.data(0, STATUS_ROLE) is ArtifactStatus.PRESENT
    assert not item.icon(0).isNull()  # unverified items still show a (ring) dot
    assert _top(tree, 0).foreground(0).color().name() == "#8b949e"  # group grey while unverified
