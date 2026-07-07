"""Phase artifact tree — the read-only right-rail view of a phase's manifest (Block 6).

Renders the ten role-based artifact groups (``view_model.phase_groups``) as a tree:
group -> artifact -> its manifest-pointer detail rows. The count shows next to each
group name whether the group is collapsed or expanded; expanding an artifact reveals
its pointer (path, producer, and the relationship / usage fields).

Existence / validity shows as a status **dot** beside each artifact (:meth:`set_groups`
populates, :meth:`set_statuses` marks): a hollow grey ring = present but not yet
validated, filled green = OK, amber = a problem (schema-invalid *or* a dependency not in
the phase), red = missing. The specific "why" rides along as the row's tooltip. Each group
header rolls its children up to the worst status (dot + coloured text). [ADR-021, ADR-025]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from myocard_egm_contracts import Role, role_of
from PySide6 import QtCore, QtGui, QtWidgets

from myocard_egm_studio.view_model import phase_actions
from myocard_egm_studio.view_model.phase_groups import ArtifactGroup, ArtifactRow
from myocard_egm_studio.view_model.phase_status import ArtifactStatus

# Item-data role holding an item's ArtifactStatus — read by tests and, later, the
# Block 10 curator context menu.
STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole
# Artifact id stashed on each artifact row so a right-click can recover it.
ARTIFACT_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1

_ICON_PX = 14  # status-dot canvas size

# Semantic status colours, theme-independent so a dot reads the same in any theme.
_GREEN = QtGui.QColor("#3fb950")
_GREY = QtGui.QColor("#8b949e")
_RED = QtGui.QColor("#f85149")
_AMBER = QtGui.QColor("#d29922")
_DEFAULT_BRUSH = QtGui.QBrush()  # empty brush -> inherit the theme's text colour

# status -> (dot colour, filled?). PRESENT is a hollow ring: "there, unverified".
# INVALID + UNRESOLVED share amber (both "present but not right"); the tooltip disambiguates.
_ICON_SPECS: dict[ArtifactStatus, tuple[QtGui.QColor, bool]] = {
    ArtifactStatus.OK: (_GREEN, True),
    ArtifactStatus.PRESENT: (_GREY, False),
    ArtifactStatus.MISSING: (_RED, True),
    ArtifactStatus.INVALID: (_AMBER, True),
    ArtifactStatus.UNRESOLVED: (_AMBER, True),
}
_STATUS_COLOR = {status: colour for status, (colour, _) in _ICON_SPECS.items()}
_ICON_CACHE: dict[ArtifactStatus, QtGui.QIcon] = {}


class PhaseTree(QtWidgets.QTreeWidget):
    """Read-only tree of a phase's artifacts, grouped by role, with pointer details."""

    # (action_id, artifact_id) from the right-click menu; the shell executes it.
    actionRequested = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, scratch: bool = False) -> None:
        super().__init__(parent)
        self._scratch = scratch  # a scratch tree leads its menu with Promote/Delete
        self.setObjectName("scratchTree" if scratch else "phaseTree")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIconSize(QtCore.QSize(_ICON_PX, _ICON_PX))
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._items_by_id: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._groups: list[tuple[QtWidgets.QTreeWidgetItem, tuple[str, ...]]] = []
        self._add_mode = False  # a bank is loaded -> additive viewers relabel to "Add …"
        self._figure_outputs: dict[str, bool] = {}  # figure id -> its image is on disk (B9)

    def set_add_mode(self, add_mode: bool) -> None:
        """Toggle the additive-when-loaded relabel of the bank viewers (B7.8)."""
        self._add_mode = add_mode

    def set_figure_outputs(self, outputs: Mapping[str, bool]) -> None:
        """Record which figures have a rendered image, tuning their menus (B9).

        A figure with an image offers **View figure** + **Regenerate figure**; without one,
        just **Generate figure**. The shell recomputes + re-sets this after a generate.
        """
        self._figure_outputs = dict(outputs)

    def set_groups(self, groups: Sequence[ArtifactGroup]) -> None:
        """Populate from a phase's display groups, replacing any prior contents."""
        self.clear()
        self._items_by_id = {}
        self._groups = []
        for group in groups:
            group_item = QtWidgets.QTreeWidgetItem([f"{group.label}  ({group.count})"])
            self.addTopLevelItem(group_item)
            self._groups.append((group_item, tuple(row.id for row in group.rows)))
            for row in group.rows:
                item = _artifact_item(row)
                self._items_by_id[row.id] = item
                group_item.addChild(item)

    def set_statuses(
        self,
        statuses: Mapping[str, ArtifactStatus],
        details: Mapping[str, str] | None = None,
    ) -> None:
        """Mark each artifact with a status dot (+ optional ``details`` as its "why" tooltip)
        and roll each group header up to the worst of its children (dot + coloured text)."""
        details = details or {}
        for artifact_id, item in self._items_by_id.items():
            _apply_status(item, statuses.get(artifact_id), colour_text=False)
            item.setToolTip(0, details.get(artifact_id, ""))
        for group_item, child_ids in self._groups:
            rollup = _group_status([statuses.get(cid) for cid in child_ids])
            _apply_status(group_item, rollup, colour_text=True)

    # -- right-click actions --------------------------------------------------

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        """Pop the per-artifact action menu; artifact rows only (not groups/details)."""
        item = self.itemAt(pos)
        artifact_id = item.data(0, ARTIFACT_ID_ROLE) if item is not None else None
        if not artifact_id:
            return
        self._artifact_menu(str(artifact_id)).exec(self.viewport().mapToGlobal(pos))

    def _artifact_menu(self, artifact_id: str) -> QtWidgets.QMenu:
        """Build one artifact's context menu from its role's action policy."""
        menu = QtWidgets.QMenu(self)
        menu.setToolTipsVisible(True)
        role = role_of(artifact_id)
        if self._scratch:  # a scratch item leads with Promote / Delete, then the shared menu
            for action in phase_actions.scratch_actions():
                self._add_action(menu, action, artifact_id)
            menu.addSeparator()
        if role is Role.figure:  # figures are dynamic: View / Generate / Regenerate per state
            specific = phase_actions.figure_actions(
                output_exists=self._figure_outputs.get(artifact_id, False)
            )
        else:
            specific = phase_actions.type_actions(role)
        for action in specific:
            self._add_action(menu, action, artifact_id)
        if specific:
            menu.addSeparator()
        for action in phase_actions.info_actions(role):
            self._add_action(menu, action, artifact_id)
        if not self._scratch:  # a loaded phase gets the curator Remove; scratch has Delete
            menu.addSeparator()
            for action in phase_actions.management_actions():
                self._add_action(menu, action, artifact_id)
        return menu

    def _add_action(
        self, menu: QtWidgets.QMenu, action: phase_actions.ArtifactAction, artifact_id: str
    ) -> None:
        qaction = menu.addAction(phase_actions.menu_label(action, add_mode=self._add_mode))
        qaction.setEnabled(action.available)
        if action.note:
            qaction.setToolTip(action.note)
        qaction.triggered.connect(
            lambda _checked=False, aid=action.id: self.actionRequested.emit(aid, artifact_id)
        )


def _apply_status(
    item: QtWidgets.QTreeWidgetItem, status: ArtifactStatus | None, *, colour_text: bool
) -> None:
    """Set an item's status dot (and, for group headers, its text colour)."""
    item.setData(0, STATUS_ROLE, status)
    if status is None:
        item.setIcon(0, QtGui.QIcon())
        if colour_text:
            item.setForeground(0, _DEFAULT_BRUSH)
        return
    item.setIcon(0, _status_icon(status))
    if colour_text:
        item.setForeground(0, QtGui.QBrush(_STATUS_COLOR[status]))


def _group_status(child_statuses: list[ArtifactStatus | None]) -> ArtifactStatus | None:
    """Roll a group's children up to a single status: the worst wins, empty -> None."""
    known = [status for status in child_statuses if status is not None]
    if not known:
        return None
    severity = (
        ArtifactStatus.MISSING,
        ArtifactStatus.INVALID,
        ArtifactStatus.UNRESOLVED,
        ArtifactStatus.PRESENT,
    )
    for worst in severity:
        if any(status is worst for status in known):
            return worst
    return ArtifactStatus.OK


def _status_icon(status: ArtifactStatus) -> QtGui.QIcon:
    """A cached status-dot icon (needs a running QGuiApplication, so built lazily)."""
    icon = _ICON_CACHE.get(status)
    if icon is None:
        colour, filled = _ICON_SPECS[status]
        icon = _paint_dot(colour, filled=filled)
        _ICON_CACHE[status] = icon
    return icon


def _paint_dot(colour: QtGui.QColor, *, filled: bool) -> QtGui.QIcon:
    """Paint a small circle — filled for a decided state, a ring for 'unverified'."""
    pixmap = QtGui.QPixmap(_ICON_PX, _ICON_PX)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    rect = QtCore.QRectF(2.5, 2.5, _ICON_PX - 5, _ICON_PX - 5)
    if filled:
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(colour)
    else:
        pen = QtGui.QPen(colour)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        rect = rect.adjusted(0.6, 0.6, -0.6, -0.6)
    painter.drawEllipse(rect)
    painter.end()
    return QtGui.QIcon(pixmap)


def _artifact_item(row: ArtifactRow) -> QtWidgets.QTreeWidgetItem:
    """One artifact node with its manifest pointer expanded into child detail rows."""
    item = QtWidgets.QTreeWidgetItem([row.id])
    item.setData(0, ARTIFACT_ID_ROLE, row.id)
    item.addChild(QtWidgets.QTreeWidgetItem([f"path: {row.path}"]))
    item.addChild(QtWidgets.QTreeWidgetItem([f"produced by: {row.produced_by}"]))
    for label, value in row.details:
        item.addChild(QtWidgets.QTreeWidgetItem([f"{label}: {value}"]))
    return item
