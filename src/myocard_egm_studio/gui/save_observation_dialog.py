"""The Save / Edit observation dialog — title + prose + parent links (Block 10c).

A small modal dialog gathering what an observation needs: a ``title`` (used for the
``obs_<slug>_<date>`` id when creating), a required ``description`` (the prose), and any
*parent observations* this one builds on (``references.observations``). At creation it
also shows a read-only summary of what will be auto-captured (banks + filter + selection).

The same dialog serves editing: pass ``observation_id`` to switch to edit mode — the id is
shown read-only (it is stable, minted at creation), the window retitles, and the capture
summary is dropped. ``title`` / ``description`` / ``selected_parents`` prefill the fields.
Save stays disabled until both title and description are non-empty.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets

__all__ = ["SaveObservationDialog"]


class SaveObservationDialog(QtWidgets.QDialog):
    """Collect an observation's ``title`` / ``description`` / parent links (create or edit)."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        summary: str = "",
        parent_observations: Sequence[str] = (),
        title: str = "",
        description: str = "",
        selected_parents: Sequence[str] = (),
        observation_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("saveObservationDialog")
        editing = observation_id is not None
        self.setWindowTitle("Edit observation" if editing else "Save observation")
        self.resize(460, 380)

        self._title = QtWidgets.QLineEdit(title)
        self._title.setObjectName("observationTitle")
        self._title.setPlaceholderText("Short title (becomes the id)")
        self._description = QtWidgets.QPlainTextEdit(description)
        self._description.setObjectName("observationDescription")
        self._description.setPlaceholderText("What did you notice? (required)")
        self._parents = self._build_parent_list(parent_observations, selected_parents)

        self._buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self._save_button = self._buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        self._save_button.setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._title.textChanged.connect(self._update_enabled)
        self._description.textChanged.connect(self._update_enabled)

        form = QtWidgets.QFormLayout()
        if editing:
            id_label = QtWidgets.QLabel(observation_id)
            id_label.setObjectName("observationId")
            id_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow("Id", id_label)
        form.addRow("Title", self._title)
        form.addRow("Description", self._description)
        form.addRow("Builds on", self._parents)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        if summary and not editing:
            summary_label = QtWidgets.QLabel(summary)
            summary_label.setObjectName("placeholderSubtitle")
            summary_label.setWordWrap(True)
            layout.addWidget(summary_label)
        layout.addWidget(self._buttons)
        self._update_enabled()

    def _build_parent_list(
        self, candidates: Sequence[str], selected: Sequence[str]
    ) -> QtWidgets.QListWidget:
        """A checkable list of candidate parent observation ids (pre-checking ``selected``)."""
        widget = QtWidgets.QListWidget()
        widget.setObjectName("observationParents")
        widget.setMaximumHeight(110)
        chosen = set(selected)
        for obs_id in candidates:
            item = QtWidgets.QListWidgetItem(obs_id)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if obs_id in chosen else QtCore.Qt.CheckState.Unchecked
            )
            widget.addItem(item)
        if not candidates:
            widget.setEnabled(False)
            placeholder = QtWidgets.QListWidgetItem("No other observations in this phase")
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            widget.addItem(placeholder)
        return widget

    def _update_enabled(self) -> None:
        self._save_button.setEnabled(bool(self.title()) and bool(self.description()))

    def title(self) -> str:
        return self._title.text().strip()

    def description(self) -> str:
        return self._description.toPlainText().strip()

    def parents(self) -> list[str]:
        """Checked parent-observation ids, in list order."""
        return [
            item.text()
            for i in range(self._parents.count())
            if (item := self._parents.item(i)).checkState() == QtCore.Qt.CheckState.Checked
        ]
