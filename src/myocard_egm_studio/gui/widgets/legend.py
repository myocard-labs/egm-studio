"""A horizontal source legend — a colour swatch + name per overlaid group.

Shared by the summary distribution grid (B7.7b) and the feature scatter (B7.9b):
both overlay one coloured series per loaded bank and want the same swatch + name
key, hidden until there are 2+ sources to disambiguate. Colours are the caller's
(the shared Okabe-Ito ``color_for``), so the legend matches the plot it annotates.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtWidgets


class SourceLegend(QtWidgets.QWidget):
    """Colour-swatch + name per source; the widget hides unless there are 2+ entries."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sourceLegend")
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(8, 0, 8, 2)
        self._layout.setSpacing(14)
        self.set_entries([])

    def set_entries(self, entries: Sequence[tuple[str, str]]) -> None:
        """Show ``(name, colour hex)`` per group; hidden unless there are 2+ to tell apart."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for name, color in entries:
            self._layout.addWidget(_legend_entry(name, color))
        self._layout.addStretch(1)
        self.setVisible(len(entries) > 1)


def _legend_entry(name: str, color: str) -> QtWidgets.QWidget:
    row = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    swatch = QtWidgets.QLabel()
    swatch.setFixedSize(11, 11)
    swatch.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
    label = QtWidgets.QLabel(name)
    label.setObjectName("legendName")
    layout.addWidget(swatch)
    layout.addWidget(label)
    return row
