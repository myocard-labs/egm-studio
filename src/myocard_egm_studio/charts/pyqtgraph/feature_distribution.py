"""pyqtgraph ``feature-distribution-overlay`` — the GUI-embedded twin of the
matplotlib recipe (``charts/matplotlib/feature_distribution_overlay``).

Reuses ``analysis/distributions`` (the same KDE / histogram / KS / Wasserstein
primitives) so the curves match the paper figure exactly — that shared analysis
is the whole point of the two-backend split. Returns a ``GraphicsLayoutWidget``
for live GUI display; group colours are the shared Okabe-Ito palette, with
background / foreground supplied per display context (:class:`PgChartStyle`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray

from myocard_egm_studio.analysis import distributions
from myocard_egm_studio.charts.inputs import FeatureGroup
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle

_GRID_POINTS = 200
_DEGENERATE_PAD = 1.0


def _finite(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return values[np.isfinite(values)]


def _panel_xrange(arrays: list[NDArray[np.float64]]) -> tuple[float, float] | None:
    """Pooled finite [min, max] across groups; None if nothing is finite."""
    pooled = np.concatenate([_finite(a) for a in arrays])
    if pooled.size == 0:
        return None
    lo, hi = float(pooled.min()), float(pooled.max())
    if hi <= lo:  # degenerate (all one value) — pad so a curve is drawable
        hi = lo + _DEGENERATE_PAD
    return lo, hi


def _panel_title(feature: str, arrays: list[NDArray[np.float64]], annotate: str) -> str:
    """Feature name plus the two-group distance (KS / Wasserstein), when defined."""
    if annotate == "none" or len(arrays) != 2:
        return feature
    try:
        if annotate == "wasserstein":
            return f"{feature}   W={distributions.wasserstein_distance(arrays[0], arrays[1]):.2g}"
        return f"{feature}   KS={distributions.ks_distance(arrays[0], arrays[1]):.2f}"
    except ValueError:
        return feature


def _draw_panel(
    plot: pg.PlotItem,
    feature: str,
    data: list[FeatureGroup],
    *,
    kind: str,
    bins: int,
    annotate: str,
    units: dict[str, str],
    style: PgChartStyle,
) -> None:
    """Overlay each group's density for one feature into ``plot``."""
    arrays = [g.values[feature] for g in data]
    plot.setTitle(_panel_title(feature, arrays, annotate), color=style.foreground)
    pen = pg.mkPen(style.foreground)
    for axis_name in ("left", "bottom"):
        axis = plot.getAxis(axis_name)
        axis.setPen(pen)
        axis.setTextPen(pen)
    # Label every panel's x-axis — the unit when it has one, else a blank spacer
    # — so all panels reserve the same bottom-label height and share one aspect
    # ratio (matplotlib gets this uniformity from constrained_layout).
    unit = units.get(feature)
    plot.setLabel("bottom", unit if unit else " ", color=style.foreground)

    xr = _panel_xrange(arrays)
    if xr is None:  # nothing finite anywhere — leave the panel titled but empty
        return
    lo, hi = xr

    # KDE needs >= 2 distinct values in every group; else fall back to a density
    # histogram for the whole panel (matches the matplotlib recipe's rule).
    use_kde = kind == "kde" and all(np.unique(_finite(a)).size >= 2 for a in arrays)
    for i, arr in enumerate(arrays):
        if use_kde:
            grid = np.linspace(lo, hi, _GRID_POINTS)
            _, density = distributions.kde(arr, grid=grid)
            plot.plot(grid, density, pen=color_for(i))
        elif _finite(arr).size > 0:
            counts, edges = distributions.histogram(arr, bins=bins, range=(lo, hi), density=True)
            plot.plot(edges, counts, stepMode="center", pen=color_for(i))
    plot.setXRange(lo, hi, padding=0)


def _add_group_legend(
    widget: pg.GraphicsLayoutWidget,
    data: list[FeatureGroup],
    *,
    ncols: int,
    style: PgChartStyle,
) -> None:
    """One horizontal group legend, centred in a thin strip above the grid.

    Mirrors the matplotlib figure legend (above the panels) so the group names
    never overlap a panel's curves. The legend is parented to a borderless host
    ViewBox spanning the columns and anchored to its centre, so it sizes to its
    own content (the entries stay together) instead of stretching across the grid
    the way a plain layout-cell legend does.
    """
    host = widget.addViewBox(row=0, col=0, colspan=ncols, enableMouse=False)
    host.setBackgroundColor(None)
    legend = pg.LegendItem(
        horSpacing=20, colCount=len(data), labelTextColor=style.foreground, frame=False
    )
    for i, group in enumerate(data):
        legend.addItem(pg.PlotDataItem(pen=pg.mkPen(color_for(i), width=2)), group.name)
    legend.setParentItem(host)
    legend.anchor(itemPos=(0.5, 0.5), parentPos=(0.5, 0.5))
    widget.ci.layout.setRowFixedHeight(0, 30)


def feature_distribution_overlay(
    data: Sequence[FeatureGroup],
    *,
    features: Sequence[str] | None = None,
    kind: str = "kde",
    bins: int = 40,
    annotate: str = "ks",
    style: PgChartStyle = DEFAULT_STYLE,
) -> pg.GraphicsLayoutWidget:
    """Render the feature-distribution overlay into a GraphicsLayoutWidget.

    The pyqtgraph counterpart to the matplotlib recipe: same FeatureGroup input,
    same analysis, for live GUI display. ``features`` curates + orders the panels
    (default: every feature). ``kind`` (kde | histogram), ``bins`` and ``annotate``
    (ks | wasserstein | none) mirror the matplotlib styling keys.
    """
    if not data:
        raise ValueError("feature-distribution-overlay needs at least one FeatureGroup.")
    all_features = list(data[0].values)
    if not all_features:
        raise ValueError("FeatureGroup.values is empty; no features to plot.")
    if any(set(g.values) != set(all_features) for g in data):
        raise ValueError("all FeatureGroups must share the same feature keys.")
    feats = [f for f in features if f in all_features] if features is not None else all_features
    units = data[0].units or {}

    ncols = math.ceil(math.sqrt(len(feats))) if feats else 1
    widget = pg.GraphicsLayoutWidget()
    widget.setBackground(style.background)
    _add_group_legend(widget, list(data), ncols=ncols, style=style)
    for idx, feature in enumerate(feats):
        row, col = divmod(idx, ncols)
        plot = widget.addPlot(row=row + 1, col=col)  # row 0 is the legend strip
        _draw_panel(
            plot,
            feature,
            list(data),
            kind=kind,
            bins=bins,
            annotate=annotate,
            units=units,
            style=style,
        )
    return widget
