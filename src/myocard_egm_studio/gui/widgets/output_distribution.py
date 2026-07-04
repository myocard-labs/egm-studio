"""Output-distribution view — overlaid P(positive) histograms, one per source (B8e).

The Flow B "Output" tab's content: a single pyqtgraph panel that overlays each loaded
source's P(positive) distribution (the :func:`charts.pyqtgraph.draw_output_distribution`
primitive) under a shared :class:`~gui.widgets.legend.SourceLegend`. Feed it one
:class:`PredictionGroup` per source (:meth:`set_groups`); :meth:`set_style` recolours on
a theme change, mirroring :class:`~gui.widgets.feature_grid.FeatureDistributionGrid`.
"""

from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6 import QtWidgets

from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph import (
    DEFAULT_STYLE,
    PgChartStyle,
    draw_output_distribution,
)
from myocard_egm_studio.gui.widgets.legend import SourceLegend


class OutputDistributionView(QtWidgets.QWidget):
    """Overlaid P(positive) output distributions, one coloured curve per source."""

    def __init__(
        self, style: PgChartStyle = DEFAULT_STYLE, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("outputDistribution")
        self._style = style
        self._groups: list[PredictionGroup] = []

        self._legend = SourceLegend()
        self._plot = pg.PlotWidget()
        self._plot.setObjectName("outputDistributionPlot")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._legend)
        layout.addWidget(self._plot, 1)
        self._rebuild()

    def set_groups(self, groups: Sequence[PredictionGroup]) -> None:
        """Overlay one P(positive) curve per source (empty clears to the bare axes)."""
        self._groups = list(groups)
        self._rebuild()

    def clear(self) -> None:
        """Drop every curve — the bare probability axes remain."""
        self.set_groups([])

    def set_style(self, style: PgChartStyle) -> None:
        """Recolour the panel for a theme change."""
        self._style = style
        self._rebuild()

    def _rebuild(self) -> None:
        self._plot.setBackground(self._style.background)
        plot_item = self._plot.getPlotItem()
        plot_item.clear()
        self._legend.set_entries([(g.name, color_for(i)) for i, g in enumerate(self._groups)])
        draw_output_distribution(plot_item, self._groups, style=self._style)

    @property
    def plot(self) -> pg.PlotWidget:
        return self._plot
