"""The New-phase dialog — start a fresh, empty phase (Block 10e).

A phase is a folder holding a ``manifest.json`` plus authored-artifact subfolders, so File ▸
New phase… collects the destination folder and the numeric ``phase`` the schema requires
(e.g. ``1.5``) — a bare save-file prompt can't supply that number. On accept the shell writes
an entry-less, ``in_progress`` manifest into the folder and opens it.
"""

from __future__ import annotations

from PySide6 import QtWidgets

__all__ = ["NewPhaseDialog"]


class NewPhaseDialog(QtWidgets.QDialog):
    """Collect a phase number + destination folder; the shell reads them back on accept."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, phase: float = 1.0) -> None:
        super().__init__(parent)
        self.setObjectName("newPhaseDialog")
        self.setWindowTitle("New phase")
        self.resize(520, 150)

        self._phase_spin = QtWidgets.QDoubleSpinBox()
        self._phase_spin.setObjectName("phaseNumber")
        self._phase_spin.setDecimals(1)  # allows half-phases like 1.5
        self._phase_spin.setSingleStep(0.5)
        self._phase_spin.setRange(0.0, 999.0)
        self._phase_spin.setValue(phase)

        self._folder_edit = QtWidgets.QLineEdit()
        self._folder_edit.setObjectName("phaseFolder")
        self._folder_edit.setPlaceholderText("Choose a folder for the phase…")
        self._folder_edit.textChanged.connect(self._sync_create_enabled)
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("phaseFolderBrowse")
        browse.clicked.connect(self._browse_folder)
        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(browse)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.setText("Create")
        self._ok_button = ok_button
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QtWidgets.QFormLayout()
        form.addRow("Phase number", self._phase_spin)
        form.addRow("Folder", folder_row)
        hint = QtWidgets.QLabel(
            "Writes an empty, in-progress manifest.json into the folder and opens it."
        )
        hint.setObjectName("placeholderSubtitle")
        hint.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self._sync_create_enabled()

    def _browse_folder(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose phase folder", self._folder_edit.text()
        )
        if chosen:
            self._folder_edit.setText(chosen)

    def _sync_create_enabled(self) -> None:
        """Create stays disabled until a destination folder is chosen."""
        self._ok_button.setEnabled(bool(self._folder_edit.text().strip()))

    def phase(self) -> float:
        return self._phase_spin.value()

    def folder(self) -> str:
        return self._folder_edit.text().strip()
