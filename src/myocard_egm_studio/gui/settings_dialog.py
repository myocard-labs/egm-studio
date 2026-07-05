"""The Settings dialog — egm-studio's preferences window (Block 10e).

A small modal over the persisted :mod:`.preferences` keys. It opens as the first home for
user preferences (ADR-017 save-state): the **scratch folder** (where observations / figure
specs saved with no phase loaded land) and the **theme**. More keys — panel scale, default
plot kind — can join here later; the shell applies the choices on accept.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtWidgets

__all__ = ["SettingsDialog"]


class SettingsDialog(QtWidgets.QDialog):
    """Edit the scratch folder + theme; the shell reads the choices back on accept."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        scratch_dir: str = "",
        theme: str = "",
        themes: Sequence[str] = (),
        auto_add_deps: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.resize(520, 190)

        self._scratch_edit = QtWidgets.QLineEdit(scratch_dir)
        self._scratch_edit.setObjectName("scratchDir")
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("scratchBrowse")
        browse.clicked.connect(self._browse_scratch)
        scratch_row = QtWidgets.QHBoxLayout()
        scratch_row.addWidget(self._scratch_edit, 1)
        scratch_row.addWidget(browse)

        self._auto_add_check = QtWidgets.QCheckBox(
            "Automatically add dependencies when saving or promoting into a phase"
        )
        self._auto_add_check.setObjectName("autoAddDeps")
        self._auto_add_check.setChecked(auto_add_deps)

        self._theme_combo = QtWidgets.QComboBox()
        self._theme_combo.setObjectName("themeCombo")
        self._theme_combo.addItems([name.capitalize() for name in themes])
        self._themes = list(themes)
        if theme in self._themes:
            self._theme_combo.setCurrentIndex(self._themes.index(theme))

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QtWidgets.QFormLayout()
        form.addRow("Scratch folder", scratch_row)
        form.addRow("Theme", self._theme_combo)
        form.addRow("Dependencies", self._auto_add_check)
        hint = QtWidgets.QLabel(
            "Observations and figures saved with no phase open go to the scratch folder,"
            " then Promote them into a phase."
        )
        hint.setObjectName("placeholderSubtitle")
        hint.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def _browse_scratch(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose scratch folder", self._scratch_edit.text()
        )
        if chosen:
            self._scratch_edit.setText(chosen)

    def scratch_dir(self) -> str:
        return self._scratch_edit.text().strip()

    def theme(self) -> str:
        index = self._theme_combo.currentIndex()
        return self._themes[index] if 0 <= index < len(self._themes) else ""

    def auto_add_deps(self) -> bool:
        return self._auto_add_check.isChecked()
