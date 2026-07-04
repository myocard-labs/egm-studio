"""Loaded-banks list — the left-sidebar roster of banks open in Flow A (B7.8).

A small vertical list, one row per loaded bank: a colour swatch (the bank's
overlay colour, so the list, the summary curves, and the legend agree), the
bank's label, and a remove button. Emits :attr:`removeRequested` with the bank's
path; the shell drops it and rebuilds the combined view. Dumb + rebuildable —
:meth:`set_banks` re-renders the whole roster from the shell's state.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets

#: One roster row: (label, path, swatch colour hex). ``path`` is the remove key.
BankRow = tuple[str, str, str]


class LoadedBanksList(QtWidgets.QWidget):
    """The left-sidebar list of loaded banks; emits the path to remove on request."""

    removeRequested = QtCore.Signal(str)  # the bank path to drop

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("loadedBanksList")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        header = QtWidgets.QLabel("Loaded banks")
        header.setObjectName("sidebarSectionTitle")
        outer.addWidget(header)

        self._rows = QtWidgets.QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(2)
        outer.addLayout(self._rows)
        self.set_banks([])

    def set_banks(self, banks: Sequence[BankRow]) -> None:
        """Re-render the roster; an empty roster shows a muted placeholder."""
        self._clear()
        if not banks:
            placeholder = QtWidgets.QLabel("No banks loaded")
            placeholder.setObjectName("placeholderSubtitle")
            self._rows.addWidget(placeholder)
            return
        for label, path, color in banks:
            self._rows.addWidget(self._make_row(label, path, color))

    def _make_row(self, label: str, path: str, color: str) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        row.setObjectName("bankRow")
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        swatch = QtWidgets.QLabel()
        swatch.setFixedSize(12, 12)
        swatch.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(swatch)

        name = QtWidgets.QLabel(label)
        name.setObjectName("bankRowName")
        name.setToolTip(path)
        layout.addWidget(name, 1)

        remove = QtWidgets.QToolButton()
        remove.setObjectName("bankRowRemove")
        remove.setText("✕")
        remove.setToolTip(f"Remove {label}")
        remove.clicked.connect(lambda: self.removeRequested.emit(path))
        layout.addWidget(remove)
        return row

    def _clear(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)  # drop from the tree now (deleteLater is deferred)
                widget.deleteLater()
