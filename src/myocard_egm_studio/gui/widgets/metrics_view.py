"""Metrics view — ROC + calibration + per-source confusion for Flow B (B8f).

The Flow B "Metrics" tab's content: the labelled-eval metric suite. A top row pairs
the ROC overlay with the reliability (calibration) overlay — one line per source —
over a bottom row of confusion matrices, one small-multiple per source. All three
reuse the :mod:`...charts.pyqtgraph` metric primitives (so the live panels match the
paper figures). Metrics need ground truth, so an unlabelled ("qualitative") load
shows a message instead (:meth:`show_message`); the view gates on mode.
"""

from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.inputs import ConfusionCounts, PredictionGroup
from myocard_egm_studio.charts.pyqtgraph import (
    DEFAULT_STYLE,
    PgChartStyle,
    draw_calibration,
    draw_confusion,
    draw_roc,
)

_CONFUSION_MIN_H = 220  # keep each small-multiple confusion panel readable
_NORM_KEYS = ("row", "col", "overall", "count")  # confusion cell modes (combo order)
_NORM_LABELS = ("Row %", "Column %", "Overall %", "Counts")


def _placeholder(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("placeholderSubtitle")
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


def _clear(layout: QtWidgets.QLayout) -> None:
    """Recursively empty a layout (widgets deleted, sub-layouts drained)."""
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


class MetricsView(QtWidgets.QWidget):
    """ROC + calibration overlays over per-source confusion small-multiples."""

    normChanged = QtCore.Signal(str)  # the confusion cell mode the user selected

    def __init__(
        self, style: PgChartStyle = DEFAULT_STYLE, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metricsView")
        self._style = style
        self._groups: list[PredictionGroup] = []
        self._confusions: list[ConfusionCounts] = []
        self._norm = _NORM_KEYS[0]  # confusion cell mode (row % by default)
        self._roc: pg.PlotWidget | None = None
        self._calibration: pg.PlotWidget | None = None
        self._confusion_plots: list[pg.PlotWidget] = []

        self._norm_combo = QtWidgets.QComboBox()
        self._norm_combo.setObjectName("confusionNorm")
        self._norm_combo.addItems(_NORM_LABELS)
        self._norm_combo.setToolTip("How each confusion-matrix cell is shown")
        self._norm_combo.currentIndexChanged.connect(self._on_norm)
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 0)
        header.addStretch(1)
        header.addWidget(QtWidgets.QLabel("Confusion"))
        header.addWidget(self._norm_combo)

        self._body = QtWidgets.QWidget()
        self._charts_layout = QtWidgets.QVBoxLayout(self._body)
        self._charts_layout.setContentsMargins(0, 0, 0, 0)

        self._message = _placeholder("")
        self._charts = QtWidgets.QWidget()
        charts_outer = QtWidgets.QVBoxLayout(self._charts)
        charts_outer.setContentsMargins(0, 0, 0, 0)
        charts_outer.addLayout(header)
        charts_outer.addWidget(self._body, 1)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._message)  # page 0 — the no-truth / empty message
        self._stack.addWidget(self._charts)  # page 1 — the metric panels
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

    def set_metrics(
        self, groups: Sequence[PredictionGroup], confusions: Sequence[ConfusionCounts]
    ) -> None:
        """Populate the ROC / calibration overlays + one confusion panel per source."""
        self._groups = list(groups)
        self._confusions = list(confusions)
        self._rebuild()
        self._stack.setCurrentIndex(1)

    def show_message(self, text: str) -> None:
        """Show ``text`` instead of the panels (an unlabelled load, or nothing loaded)."""
        self._message.setText(text)
        self._stack.setCurrentIndex(0)

    def set_norm(self, norm: str) -> None:
        """Set the confusion cell mode (row / col / overall / count); syncs the combo."""
        self._norm = norm if norm in _NORM_KEYS else _NORM_KEYS[0]
        self._norm_combo.blockSignals(True)
        self._norm_combo.setCurrentIndex(_NORM_KEYS.index(self._norm))
        self._norm_combo.blockSignals(False)
        if self._stack.currentIndex() == 1:
            self._rebuild()

    def set_style(self, style: PgChartStyle) -> None:
        """Recolour the panels for a theme change (only when the charts are showing)."""
        self._style = style
        if self._stack.currentIndex() == 1:
            self._rebuild()

    def _on_norm(self, index: int) -> None:
        self._norm = _NORM_KEYS[index]
        if self._confusions:
            self._rebuild()
        self.normChanged.emit(self._norm)

    def _rebuild(self) -> None:
        _clear(self._charts_layout)
        self._roc = self._panel(draw_roc, self._groups)
        self._calibration = self._panel(draw_calibration, self._groups)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self._roc)
        top.addWidget(self._calibration)
        self._charts_layout.addLayout(top, 1)

        self._confusion_plots = []
        if self._confusions:
            row = QtWidgets.QHBoxLayout()
            for counts in self._confusions:
                plot = pg.PlotWidget()
                plot.setBackground(self._style.background)
                plot.setMinimumHeight(_CONFUSION_MIN_H)
                draw_confusion(plot.getPlotItem(), counts, normalize=self._norm, style=self._style)
                row.addWidget(plot)
                self._confusion_plots.append(plot)
            self._charts_layout.addLayout(row, 1)

    def _panel(self, draw: object, groups: list[PredictionGroup]) -> pg.PlotWidget:
        """A themed PlotWidget with ``draw`` (draw_roc / draw_calibration) applied."""
        plot = pg.PlotWidget()
        plot.setBackground(self._style.background)
        draw(plot.getPlotItem(), groups, style=self._style)  # type: ignore[operator]
        return plot

    @property
    def confusion_plots(self) -> list[pg.PlotWidget]:
        return self._confusion_plots
