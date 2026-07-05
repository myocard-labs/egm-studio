"""Tests for the Phase artifact tree widget (gui/widgets/phase_tree)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import load_phase_dir
from PySide6 import QtCore, QtGui, QtWidgets
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


def _menu_labels(menu: QtWidgets.QMenu) -> list[str]:
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def _menu_action(menu: QtWidgets.QMenu, text: str) -> QtGui.QAction:
    return next(action for action in menu.actions() if action.text() == text)


def test_context_menu_policy_is_custom(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    assert tree.contextMenuPolicy() == QtCore.Qt.ContextMenuPolicy.CustomContextMenu


def test_bank_menu_lists_viewers_then_info(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    menu = tree._artifact_menu(_child(_top(tree, 0), 0).text(0))  # a training bank
    assert _menu_labels(menu) == [
        "Explore signal",
        "View feature distributions",
        "Show metadata",
        "Reveal file",
        "Copy id",
    ]
    assert any(action.isSeparator() for action in menu.actions())  # divider before the info group


def test_add_mode_relabels_feature_distributions(qtbot: QtBot) -> None:
    """With a bank loaded (add mode), View feature distributions -> Add feature
    distribution; Explore signal keeps its label (B7.8b-fix)."""
    tree = _populated(qtbot)
    bank_id = _child(_top(tree, 0), 0).text(0)  # a training bank
    tree.set_add_mode(True)
    labels = _menu_labels(tree._artifact_menu(bank_id))
    assert "Add feature distribution" in labels
    assert "View feature distributions" not in labels
    assert "Explore signal" in labels


def test_run_menu_enables_view_curves(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    menu = tree._artifact_menu(_child(_top(tree, 5), 0).text(0))  # a training run
    assert _menu_action(menu, "View training curves").isEnabled() is True  # wired in B8f
    assert _menu_action(menu, "Show metadata").isEnabled() is True


def test_model_menu_disables_planned_action(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    menu = tree._artifact_menu(_child(_top(tree, 6), 0).text(0))  # a model
    assert _menu_action(menu, "Go to training run").isEnabled() is False  # not wired yet


def test_model_menu_has_no_show_metadata(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    labels = _menu_labels(tree._artifact_menu(_child(_top(tree, 6), 0).text(0)))  # a model
    assert "Go to training run" in labels
    assert "Show metadata" not in labels  # .pt checkpoints have no cheap file view
    assert labels[-2:] == ["Reveal file", "Copy id"]


def test_triggering_action_emits_signal(qtbot: QtBot) -> None:
    tree = _populated(qtbot)
    bank_id = _child(_top(tree, 0), 0).text(0)
    menu = tree._artifact_menu(bank_id)
    with qtbot.waitSignal(tree.actionRequested) as blocker:
        _menu_action(menu, "Copy id").trigger()
    assert blocker.args == ["copy_id", bank_id]


def test_figure_menu_reflects_output_existence(qtbot: QtBot) -> None:
    """A figure offers Generate until its image exists, then View + Regenerate (B9)."""
    from myocard_egm_contracts import Role, role_of

    from myocard_egm_studio.view_model import entries_by_id

    tree = _populated(qtbot)
    fig_id = next(
        aid for aid in entries_by_id(load_phase_dir(_FIXTURE_DIR)) if role_of(aid) == Role.figure
    )

    before = _menu_labels(tree._artifact_menu(fig_id))  # default: not generated
    assert "Generate figure" in before
    assert "View figure" not in before
    assert "Regenerate figure" not in before

    tree.set_figure_outputs({fig_id: True})  # the image now exists
    after = _menu_labels(tree._artifact_menu(fig_id))
    assert "View figure" in after
    assert "Regenerate figure" in after
    assert "Generate figure" not in after
