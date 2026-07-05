"""The scratch-artifacts sidebar list (Block 10e).

A small list of the observations / figure specs sitting in the scratch folder — saved with
no phase open. Each row offers a right-click **Promote to phase** (move + index into the
loaded phase) and **Delete from scratch**. The shell shows this widget only while scratch
is non-empty, so an empty scratch leaves the left sidebar exactly as it was.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.save import ScratchArtifact

_ARTIFACT_ROLE = QtCore.Qt.ItemDataRole.UserRole
#: A quiet per-kind marker so observations and figures read apart at a glance.
_KIND_GLYPH = {"observation": "◍", "figure": "▤"}

__all__ = ["ScratchList"]


class ScratchList(QtWidgets.QWidget):
    """Lists scratch artifacts; emits a promote / delete request per right-clicked item."""

    promoteRequested = QtCore.Signal(object)  # a ScratchArtifact -> shell moves it into the phase
    deleteRequested = QtCore.Signal(object)  # a ScratchArtifact -> shell removes the scratch file

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scratchList")
        title = QtWidgets.QLabel("Scratch")
        title.setObjectName("sidebarTitle")
        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("scratchItems")
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
        layout.addWidget(self._list)

    def set_artifacts(self, artifacts: Sequence[ScratchArtifact]) -> None:
        """Populate the list from ``artifacts`` (each row carries its ScratchArtifact)."""
        self._list.clear()
        for artifact in artifacts:
            item = QtWidgets.QListWidgetItem(f"{_KIND_GLYPH.get(artifact.kind, '')} {artifact.id}")
            item.setData(_ARTIFACT_ROLE, artifact)
            item.setToolTip(str(artifact.path))
            self._list.addItem(item)

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        artifact = item.data(_ARTIFACT_ROLE)
        menu = QtWidgets.QMenu(self)
        promote = menu.addAction("Promote to phase")
        delete = menu.addAction("Delete from scratch")
        chosen = menu.exec(self._list.viewport().mapToGlobal(pos))
        if chosen is promote:
            self.promoteRequested.emit(artifact)
        elif chosen is delete:
            self.deleteRequested.emit(artifact)
