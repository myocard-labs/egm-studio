"""Training view — the loss + selection-metric overlay for Flow B (B8f).

The Flow B "Training" tab's content: wraps the :func:`...charts.pyqtgraph.
training_curves_overlay` GraphicsLayoutWidget, one colour per loaded run. Training
runs load through a separate path (``File ▸ Open training run`` reads a ``run.json``,
not a bank), so this shows a prompt until a run is loaded (:meth:`set_runs`).
"""

from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph import (
    DEFAULT_STYLE,
    PgChartStyle,
    training_curves_overlay,
)
from myocard_egm_studio.gui.widgets.run_list import LoadedRunsList

_LANDING = "Open a training run (File ▸ Open training run) to see its loss + metric curves."


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class TrainingView(QtWidgets.QWidget):
    """The training-curves overlay (loss + metric vs epoch) over a removable-run roster."""

    removeRequested = QtCore.Signal(str)  # a run label the user asked to drop

    def __init__(
        self, style: PgChartStyle = DEFAULT_STYLE, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("trainingView")
        self._style = style
        self._runs: list[tuple[str, TrainingCurve]] = []
        self._overlay: pg.GraphicsLayoutWidget | None = None

        self._roster = LoadedRunsList()
        self._roster.removeRequested.connect(self.removeRequested)
        self._host = QtWidgets.QWidget()
        self._host_layout = QtWidgets.QVBoxLayout(self._host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)

        loaded_page = QtWidgets.QWidget()
        loaded_layout = QtWidgets.QVBoxLayout(loaded_page)
        loaded_layout.setContentsMargins(8, 4, 8, 0)
        loaded_layout.addWidget(self._roster)
        loaded_layout.addWidget(self._host, 1)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(_placeholder(_LANDING))  # page 0 — nothing loaded
        self._stack.addWidget(loaded_page)  # page 1 — roster + overlay
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

    def set_runs(self, runs: Sequence[tuple[str, TrainingCurve]]) -> None:
        """Overlay one loss + metric curve per run; empty shows the open-a-run prompt."""
        self._runs = list(runs)
        if not self._runs:
            self._stack.setCurrentIndex(0)
            return
        self._roster.set_runs([(label, color_for(i)) for i, (label, _) in enumerate(self._runs)])
        self._rebuild()
        self._stack.setCurrentIndex(1)

    def clear(self) -> None:
        """Drop every run — back to the open-a-run prompt."""
        self.set_runs([])

    def set_style(self, style: PgChartStyle) -> None:
        """Recolour for a theme change (only when a run is showing)."""
        self._style = style
        if self._runs:
            self._rebuild()

    def _rebuild(self) -> None:
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._overlay = training_curves_overlay(self._runs, style=self._style)
        self._host_layout.addWidget(self._overlay)

    @property
    def overlay(self) -> pg.GraphicsLayoutWidget | None:
        return self._overlay
