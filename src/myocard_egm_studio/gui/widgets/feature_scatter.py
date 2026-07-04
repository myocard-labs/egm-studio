"""Interactive feature scatter — the B7.9 Flow A scatter view.

A 2-D ``(feat_x, feat_y)`` scatter of the current filter result: one colour per
source bank, two axis pickers (any egm-features column per axis), pan / zoom (the
pyqtgraph ViewBox), and a source legend. Clicking a point emits its ``row_id``
(:attr:`pointClicked`) so the shell can open that trace in the detail pane; the
chosen axes persist across launches (:attr:`axesChanged`, saved by the shell).
Reuses ``charts/pyqtgraph.draw_feature_scatter`` so points + colours match the rest
of Flow A (the summary overlay + the loaded-banks roster).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.inputs import ScatterSeries
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle, draw_feature_scatter
from myocard_egm_studio.gui.widgets.legend import SourceLegend


def _resolve(desired: str, features: list[str], fallback: int) -> str:
    """``desired`` if it is a current feature, else the ``fallback``-th feature (or "")."""
    if desired in features:
        return desired
    if not features:
        return ""
    return features[min(fallback, len(features) - 1)]


class FeatureScatterView(QtWidgets.QWidget):
    """A pannable feature scatter with axis pickers + click-to-select (B7.9).

    Feed it the filtered frame's per-source :class:`ScatterSeries`
    (:meth:`set_series`); it draws one colour per source and fills the two axis
    combos from the feature columns. Picking an axis redraws + reports the pair
    (:attr:`axesChanged`); clicking a point reports its ``row_id``
    (:attr:`pointClicked`). :meth:`set_style` recolours on a theme change.
    """

    pointClicked = QtCore.Signal(int)  # row_id of the clicked point
    axesChanged = QtCore.Signal(str, str)  # (x_feature, y_feature)

    def __init__(
        self, style: PgChartStyle = DEFAULT_STYLE, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("featureScatter")
        self._style = style
        self._series: list[ScatterSeries] = []
        self._features: list[str] = []
        self._x = ""
        self._y = ""
        self._items: list[pg.ScatterPlotItem] = []
        self._front_source: str | None = None  # a source raised above the others (B7-scatter-front)

        self._x_combo = QtWidgets.QComboBox()
        self._x_combo.setObjectName("scatterX")
        self._y_combo = QtWidgets.QComboBox()
        self._y_combo.setObjectName("scatterY")
        for combo in (self._x_combo, self._y_combo):
            combo.currentIndexChanged.connect(self._on_axis)

        self._recenter_button = QtWidgets.QPushButton("Recenter")
        self._recenter_button.setObjectName("recenterView")
        self._recenter_button.setToolTip("Fit the view to the points")
        self._recenter_button.clicked.connect(self.recenter)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 0)
        header.addWidget(QtWidgets.QLabel("X"))
        header.addWidget(self._x_combo)
        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("Y"))
        header.addWidget(self._y_combo)
        header.addStretch(1)
        header.addWidget(self._recenter_button)

        self._legend = SourceLegend()

        self._plot = pg.PlotWidget()
        self._plot.setObjectName("scatterPlot")
        self._plot.setBackground(self._style.background)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self._legend)
        layout.addWidget(self._plot, 1)

    # -- public API -----------------------------------------------------------

    def set_series(self, series: Sequence[ScatterSeries]) -> None:
        """Show one coloured point cloud per source; (re)fills the axis combos."""
        self._series = list(series)
        self._sync_features()
        self._redraw()

    def clear(self) -> None:
        """Drop all points (e.g. the filter matched nothing / no bank loaded)."""
        self.set_series([])

    def set_style(self, style: PgChartStyle) -> None:
        """Recolour the plot for a theme change."""
        self._style = style
        self._plot.setBackground(style.background)
        self._redraw()

    def recenter(self) -> None:
        """Fit the view back to the current points (after a manual pan / zoom)."""
        self._plot.getPlotItem().getViewBox().autoRange()

    def bring_to_front(self, source: str) -> None:
        """Raise ``source``'s points above the others, so a huge bank doesn't bury them.

        Draw order (hence overplotting) is load order, so a large bank loaded last hides
        the rest; this stacks the chosen source on top by z-value. The choice persists
        across redraws (a filter apply / axis change re-applies it).
        """
        self._front_source = source
        self._apply_front_order()

    def _apply_front_order(self) -> None:
        for source, item in zip(self._series, self._items, strict=True):
            item.setZValue(1 if source.name == self._front_source else 0)

    def x_feature(self) -> str:
        return self._x

    def y_feature(self) -> str:
        return self._y

    def set_axes(self, x: str, y: str) -> None:
        """Set the desired (x, y) feature axes (e.g. a restored preference).

        Applied now when the features are already loaded, else remembered until they
        are. Syncs the combos *without* emitting :attr:`axesChanged` (no echo on
        restore); unknown feature names fall back to the first / second column.
        """
        self._x, self._y = x, y
        if self._features:
            self._x = _resolve(x, self._features, 0)
            self._y = _resolve(y, self._features, 1)
            self._apply_axis_combos()
            self._redraw()

    @property
    def items(self) -> list[pg.ScatterPlotItem]:
        return self._items

    # -- internals ------------------------------------------------------------

    def _sync_features(self) -> None:
        """Repopulate the axis combos when the feature set changes (else keep them)."""
        features = list(self._series[0].values) if self._series else []
        if features == self._features:
            return  # same columns (e.g. a filter update) — keep the current axes
        self._features = features
        for combo in (self._x_combo, self._y_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(features)
            combo.blockSignals(False)
        self._x = _resolve(self._x, features, 0)
        self._y = _resolve(self._y, features, 1)
        self._apply_axis_combos()

    def _apply_axis_combos(self) -> None:
        for combo, feature in ((self._x_combo, self._x), (self._y_combo, self._y)):
            combo.blockSignals(True)
            if feature in self._features:
                combo.setCurrentIndex(self._features.index(feature))
            combo.blockSignals(False)

    def _redraw(self) -> None:
        plot = self._plot.getPlotItem()
        if not self._series or not self._x or not self._y:
            plot.clear()
            self._items = []
            self._legend.set_entries([])
            return
        self._items = draw_feature_scatter(
            plot, self._series, x=self._x, y=self._y, style=self._style
        )
        for item in self._items:
            item.sigClicked.connect(self._on_points_clicked)
        self._legend.set_entries([(s.name, color_for(i)) for i, s in enumerate(self._series)])
        self._apply_front_order()  # re-raise the chosen source after the redraw rebuilt items
        plot.getViewBox().autoRange()  # recenter to the new data (filter / axis change)

    def _on_axis(self, _index: int) -> None:
        self._x = self._x_combo.currentText()
        self._y = self._y_combo.currentText()
        self._redraw()
        self.axesChanged.emit(self._x, self._y)

    def _on_points_clicked(self, _item: Any, points: Sequence[Any], _ev: Any) -> None:
        """pyqtgraph ScatterPlotItem click -> emit the first hit point's row_id."""
        if len(points) == 0:
            return
        data = points[0].data()
        if data is not None:
            self.pointClicked.emit(int(data))
