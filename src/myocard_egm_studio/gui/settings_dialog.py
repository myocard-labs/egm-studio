"""The Settings dialog — egm-studio's preferences window (Block 10e).

A small modal over the persisted :mod:`.preferences` keys. It opens as the first home for
user preferences (ADR-017 save-state): the **scratch folder** (where observations / figure
specs saved with no phase loaded land) and the **theme**. More keys — panel scale, default
plot kind — can join here later; the shell applies the choices on accept.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets

__all__ = ["SettingsDialog"]

_CEILING_MIN_MB = 128
_CEILING_MAX_MB = 65536  # 64 GB — a generous cap, well past any realistic working set
_CEILING_STEP_MB = 128


class SettingsDialog(QtWidgets.QDialog):
    """Edit the scratch folder + theme + view-model cache; the shell reads the choices back."""

    #: Emitted when the user clicks "Flush cache now"; the shell clears the frame store.
    flushRequested = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        scratch_dir: str = "",
        theme: str = "",
        themes: Sequence[str] = (),
        auto_add_deps: bool = True,
        cache_ceiling_mb: int = 1024,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.resize(520, 230)

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

        # View-model cache (Block 11): the in-RAM ceiling + a manual flush. The spinbox
        # is a persisted preference; the button clears the store immediately (the shell
        # handles flushRequested).
        self._ceiling_spin = QtWidgets.QSpinBox()
        self._ceiling_spin.setObjectName("cacheCeiling")
        self._ceiling_spin.setRange(_CEILING_MIN_MB, _CEILING_MAX_MB)
        self._ceiling_spin.setSingleStep(_CEILING_STEP_MB)
        self._ceiling_spin.setSuffix(" MB")
        self._ceiling_spin.setValue(cache_ceiling_mb)
        self._flush_button = QtWidgets.QPushButton("Flush cache now")
        self._flush_button.setObjectName("flushCache")
        self._flush_button.clicked.connect(self.flushRequested)
        cache_row = QtWidgets.QHBoxLayout()
        cache_row.addWidget(self._ceiling_spin, 1)
        cache_row.addWidget(self._flush_button)

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
        form.addRow("View-model cache", cache_row)
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

    def cache_ceiling_mb(self) -> int:
        return self._ceiling_spin.value()
