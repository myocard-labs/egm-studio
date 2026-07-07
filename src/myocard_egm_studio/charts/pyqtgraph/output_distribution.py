"""pyqtgraph ``output-distribution-overlay`` — P(positive) per source in one panel.

The GUI-embedded output-distribution view (Flow B, B8e): one step-histogram curve
per source over a fixed ``[0, 1]`` probability axis, plus a dashed guide at the 0.5
decision threshold. This is the "v1 vs v1.5" headline — overlay each run's output
distribution to see which pushes probabilities to the confident extremes instead of
piling up around the boundary.

Histogram, not KDE: predicted probabilities saturate (the IAFDB case pins near 1.0),
where a Gaussian KDE covariance is singular; fixed bins over an explicit ``(0, 1)``
range stay well-defined and align across sources. This mirrors the matplotlib
``prediction-histogram`` recipe's decision and reuses the same
``analysis/distributions.histogram``, so the live curve matches the paper figure.
GUI-only, like the feature scatter — the headless paper twin is ``prediction-histogram``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6 import QtCore

from myocard_egm_studio.analysis import distributions
from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle

_PROB_RANGE = (0.0, 1.0)  # probability axis; bins align across sources when fixed here
_THRESHOLD = 0.5  # decision boundary — the dashed guide line
_DEFAULT_BINS = 30  # matches the matplotlib prediction-histogram default


def _finite(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return values[np.isfinite(values)]


def draw_output_distribution(
    plot: pg.PlotItem,
    groups: Sequence[PredictionGroup],
    *,
    bins: int = _DEFAULT_BINS,
    style: PgChartStyle = DEFAULT_STYLE,
) -> None:
    """Overlay each group's P(positive) density histogram into ``plot``.

    One density step-histogram per group over the fixed ``(0, 1)`` probability range,
    coloured by load order (``color_for(i)``, matching the source legend + the roster),
    with a dashed vertical guide at the 0.5 decision threshold. Density-normalized, so
    sources of different size compare on one axis. A group with no finite probability is
    skipped; the axes + guide still draw (the empty-state panel).
    """
    pen = pg.mkPen(style.foreground)
    for axis_name in ("left", "bottom"):
        axis = plot.getAxis(axis_name)
        axis.setPen(pen)
        axis.setTextPen(pen)
    plot.setLabel("bottom", "P(positive)", color=style.foreground)
    plot.setLabel("left", "density", color=style.foreground)

    for i, group in enumerate(groups):
        probs = _finite(np.asarray(group.probs, dtype=np.float64))
        if probs.size == 0:
            continue
        counts, edges = distributions.histogram(probs, bins=bins, range=_PROB_RANGE, density=True)
        plot.plot(edges, counts, stepMode="center", pen=color_for(i))

    guide = pg.mkPen(style.foreground)
    guide.setStyle(QtCore.Qt.PenStyle.DashLine)
    plot.addLine(x=_THRESHOLD, pen=guide)
    plot.setXRange(*_PROB_RANGE, padding=0)


def output_distribution_overlay(
    groups: Sequence[PredictionGroup],
    *,
    bins: int = _DEFAULT_BINS,
    style: PgChartStyle = DEFAULT_STYLE,
) -> pg.PlotWidget:
    """Render the output-distribution overlay into a standalone ``PlotWidget``.

    The single-panel convenience wrapper (for demos + the metric-suite view host):
    builds a themed ``PlotWidget`` and draws :func:`draw_output_distribution` into it.
    """
    widget = pg.PlotWidget()
    widget.setBackground(style.background)
    draw_output_distribution(widget.getPlotItem(), groups, bins=bins, style=style)
    return widget
