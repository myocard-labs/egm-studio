"""Responsive feature-distribution grid — the ADR-018 bank-summary panel grid (B7.7b).

Each egm-features column is drawn as its own pyqtgraph panel (reusing
``charts/pyqtgraph.draw_feature_panel``, so a panel matches its paper-figure
twin), laid out in a wrap-on-overflow flow inside a scroll area. ADR-018: panels
keep a readable min/max size, clamped by a user scale factor; the grid wraps to
more rows as the window narrows and scrolls when the panels overflow.

Multiple banks overlay per panel — one coloured curve per source, with a legend
(B7.8c). A KDE / Histogram toggle picks the display; KDE is the default (smooth
curves compare more cleanly than overlaid step histograms).
"""

from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from myocard_egm_studio.charts.inputs import FeatureGroup
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE, PgChartStyle, draw_feature_panel

_PANEL_BASE = (300, 220)  # panel (w, h) in px at scale 1.0
_PANEL_MIN = (200, 150)  # smallest readable panel — below this the grid wraps/scrolls
_PANEL_MAX = (560, 400)  # cap before the grid just adds whitespace
_SCALE_MIN, _SCALE_MAX = 0.6, 2.0
_SCALE_STEPS = 14  # slider granularity between min and max
_HIST_BINS = 30  # per-panel histogram resolution
_KINDS = ("kde", "histogram")  # combo order; index 0 (KDE) is the default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class _FlowLayout(QtWidgets.QLayout):
    """Left-to-right layout that wraps to a new row on overflow (Qt flow-layout).

    The standard Qt example pattern: place items at their sizeHint, wrapping when
    the next item would exceed the available width, and report the wrapped total
    height via :meth:`heightForWidth` so a scroll area can size the viewport.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self.setSpacing(spacing)
        self.setContentsMargins(spacing, spacing, spacing, spacing)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> QtCore.Qt.Orientation:
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QtCore.QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QtCore.QSize:
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size.grownBy(margins)

    def _do_layout(self, rect: QtCore.QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        x0 = rect.x() + margins.left()
        right = rect.right() - margins.right()
        x, y, line_height = x0, rect.y() + margins.top(), 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            if x > x0 and x + hint.width() > right + 1:  # wrap to the next row
                x, y = x0, y + line_height + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x += hint.width() + spacing
            line_height = max(line_height, hint.height())
        return y + line_height + margins.bottom() - rect.y()


class _Legend(QtWidgets.QWidget):
    """A horizontal source legend: a colour swatch + name per overlaid group."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("gridLegend")
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(8, 0, 8, 2)
        self._layout.setSpacing(14)
        self.set_entries([])

    def set_entries(self, entries: Sequence[tuple[str, str]]) -> None:
        """Show ``(name, colour hex)`` per group; hidden unless there are 2+."""
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


class FeatureDistributionGrid(QtWidgets.QWidget):
    """A wrap + scroll grid of per-feature distribution panels (ADR-018).

    Feed it one or more :class:`FeatureGroup` (:meth:`set_groups`); it overlays a
    coloured curve per group in each feature panel, with a legend for 2+. The
    KDE / Histogram combo picks the display (:attr:`kindChanged` reports it) and
    the scale slider clamps panel size (:attr:`scaleChanged`); the shell persists
    both. :meth:`set_style` recolours on a theme change.
    """

    scaleChanged = QtCore.Signal(float)
    kindChanged = QtCore.Signal(str)

    def __init__(
        self, style: PgChartStyle = DEFAULT_STYLE, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("featureGrid")
        self._style = style
        self._groups: list[FeatureGroup] = []
        self._scale = 1.0
        self._kind = "kde"
        self._panels: list[pg.PlotWidget] = []

        self._kind_combo = QtWidgets.QComboBox()
        self._kind_combo.setObjectName("plotKind")
        self._kind_combo.addItems(["KDE", "Histogram"])
        self._kind_combo.currentIndexChanged.connect(self._on_kind)

        self._scale_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._scale_slider.setObjectName("panelScale")
        self._scale_slider.setRange(0, _SCALE_STEPS)
        self._scale_slider.setFixedWidth(140)
        self._scale_slider.setToolTip("Panel size")
        self._scale_slider.valueChanged.connect(self._on_slider)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 0)
        header.addWidget(QtWidgets.QLabel("Plot"))
        header.addWidget(self._kind_combo)
        header.addStretch(1)
        header.addWidget(QtWidgets.QLabel("Panel size"))
        header.addWidget(self._scale_slider)

        self._legend = _Legend()

        self._flow_host = QtWidgets.QWidget()
        self._flow = _FlowLayout(self._flow_host)
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setObjectName("featureGridScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._flow_host)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self._legend)
        layout.addWidget(self._scroll, 1)
        self._sync_slider()

    # -- public API -----------------------------------------------------------

    def set_groups(self, groups: Sequence[FeatureGroup]) -> None:
        """Overlay one distribution curve per group in each feature panel."""
        self._groups = list(groups)
        self._rebuild()

    def set_group(self, group: FeatureGroup) -> None:
        """Convenience for the single-bank case: overlay just one group."""
        self.set_groups([group])

    def clear(self) -> None:
        """Remove every panel (e.g. the last loaded bank was removed)."""
        self.set_groups([])

    def set_style(self, style: PgChartStyle) -> None:
        """Recolour the panels for a theme change."""
        self._style = style
        self._rebuild()

    def scale_factor(self) -> float:
        return self._scale

    def set_scale_factor(self, factor: float) -> None:
        """Set the panel scale (clamped to ADR-018's range); syncs the slider + panels."""
        self._scale = _clamp(factor, _SCALE_MIN, _SCALE_MAX)
        self._sync_slider()
        self._apply_panel_size()

    def kind(self) -> str:
        return self._kind

    def set_kind(self, kind: str) -> None:
        """Set the display to ``"kde"`` or ``"histogram"``; syncs the combo + redraws."""
        self._kind = kind if kind in _KINDS else "kde"
        self._kind_combo.blockSignals(True)
        self._kind_combo.setCurrentIndex(_KINDS.index(self._kind))
        self._kind_combo.blockSignals(False)
        self._rebuild()

    @property
    def panels(self) -> list[pg.PlotWidget]:
        return self._panels

    # -- internals ------------------------------------------------------------

    def _panel_size(self) -> QtCore.QSize:
        w = _clamp(_PANEL_BASE[0] * self._scale, _PANEL_MIN[0], _PANEL_MAX[0])
        h = _clamp(_PANEL_BASE[1] * self._scale, _PANEL_MIN[1], _PANEL_MAX[1])
        return QtCore.QSize(int(w), int(h))

    def _apply_panel_size(self) -> None:
        size = self._panel_size()
        for panel in self._panels:
            panel.setFixedSize(size)
        self._flow_host.updateGeometry()

    def _rebuild(self) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._panels = []
        self._legend.set_entries([(g.name, color_for(i)) for i, g in enumerate(self._groups)])
        if not self._groups:
            return
        units = self._groups[0].units or {}
        for feature in self._groups[0].values:
            panel = pg.PlotWidget()
            panel.setBackground(self._style.background)
            draw_feature_panel(
                panel.getPlotItem(),
                feature,
                self._groups,
                kind=self._kind,
                bins=_HIST_BINS,
                annotate="ks",  # two groups -> KS distance in the title; silent otherwise
                units=units,
                style=self._style,
            )
            self._flow.addWidget(panel)
            self._panels.append(panel)
        self._apply_panel_size()

    def _on_kind(self, index: int) -> None:
        self._kind = _KINDS[index]
        self._rebuild()
        self.kindChanged.emit(self._kind)

    def _on_slider(self, step: int) -> None:
        self._scale = _SCALE_MIN + (_SCALE_MAX - _SCALE_MIN) * step / _SCALE_STEPS
        self._apply_panel_size()
        self.scaleChanged.emit(self._scale)

    def _sync_slider(self) -> None:
        step = round((self._scale - _SCALE_MIN) / (_SCALE_MAX - _SCALE_MIN) * _SCALE_STEPS)
        self._scale_slider.blockSignals(True)
        self._scale_slider.setValue(step)
        self._scale_slider.blockSignals(False)
