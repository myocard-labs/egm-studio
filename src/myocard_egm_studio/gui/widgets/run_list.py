"""Loaded-runs list — the Flow B Training-tab roster of loaded training runs (B8f).

A small vertical list mirroring the loaded-banks roster (:mod:`.bank_list`): one row
per run — a colour swatch (the run's overlay colour, so the roster, the curves, and
the legend agree) + its label + a remove button. Emits :attr:`removeRequested` with
the run label (the shell drops it and re-feeds the Training tab). Dumb + rebuildable —
:meth:`set_runs` re-renders the whole roster from state.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtCore, QtWidgets

#: One roster row: (run label, swatch colour hex). ``label`` is the row key.
RunRow = tuple[str, str]


class LoadedRunsList(QtWidgets.QWidget):
    """The Training-tab list of loaded runs; emits the run label for the remove action."""

    removeRequested = QtCore.Signal(str)  # the run label to drop

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("loadedRunsList")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        header = QtWidgets.QLabel("Loaded runs")
        header.setObjectName("sidebarSectionTitle")
        outer.addWidget(header)

        self._rows = QtWidgets.QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(2)
        outer.addLayout(self._rows)
        self.set_runs([])

    def set_runs(self, runs: Sequence[RunRow]) -> None:
        """Re-render the roster, one row per (label, colour); empty clears it."""
        self._clear()
        for label, color in runs:
            self._rows.addWidget(self._make_row(label, color))

    def _make_row(self, label: str, color: str) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        row.setObjectName("runRow")
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        swatch = QtWidgets.QLabel()
        swatch.setFixedSize(12, 12)
        swatch.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(swatch)

        name = QtWidgets.QLabel(label)
        name.setObjectName("runRowName")
        name.setToolTip(label)
        layout.addWidget(name, 1)

        remove = QtWidgets.QToolButton()
        remove.setObjectName("runRowRemove")
        remove.setText("✕")
        remove.setToolTip(f"Remove {label}")
        remove.clicked.connect(lambda: self.removeRequested.emit(label))
        layout.addWidget(remove)
        return row

    def _clear(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)  # drop from the tree now (deleteLater is deferred)
                widget.deleteLater()
