"""pyqtgraph feature scatter — a 2-D ``(feat_x, feat_y)`` scatter of traces,
coloured by source (B7.9).

GUI-only, unlike the ``charts/pyqtgraph`` distribution twin: there is no matplotlib
recipe / headless output, because the scatter is a *live-exploration* view — pan /
zoom over the current filter result, one colour per source bank. Each point carries
its ``row_id`` (the ScatterPlotItem's per-point ``data``) so a click resolves back
to a trace. Colours are the shared Okabe-Ito palette (matching the summary overlay +
the loaded-banks roster); background / foreground come from the display context
(:class:`PgChartStyle`).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray

from myocard_egm_studio.charts.inputs import ScatterSeries
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle

#: Point diameter in px; translucent so dense clusters read as density, not a blob.
_POINT_SIZE = 7
_POINT_ALPHA = 160  # 0-255


def _axis_label(feature: str, units: dict[str, str] | None) -> str:
    """``feature (unit)`` when the feature carries a unit, else the bare name."""
    unit = (units or {}).get(feature)
    return f"{feature} ({unit})" if unit else feature


def _finite_mask(x: NDArray[np.float64], y: NDArray[np.float64]) -> NDArray[np.bool_]:
    """Points finite in *both* axes — a NaN/inf in either drops the point."""
    return np.isfinite(x) & np.isfinite(y)


def draw_feature_scatter(
    plot: pg.PlotItem,
    series: Sequence[ScatterSeries],
    *,
    x: str,
    y: str,
    style: PgChartStyle = DEFAULT_STYLE,
) -> list[pg.ScatterPlotItem]:
    """Draw each source's ``(x, y)`` points into ``plot``; return the scatter items.

    One ScatterPlotItem per series, coloured by load order (``color_for(i)``) to
    match the summary overlay + roster. Only points finite in *both* axes are drawn;
    each carries its ``row_id`` in the item's per-point ``data`` so the widget maps a
    click back to a trace. Returns the items (in series order) so the caller can
    connect ``sigClicked``; an empty ``series`` just clears + labels the plot. Axis
    units come from the first series (as the distribution overlay does).
    """
    plot.clear()
    pen = pg.mkPen(style.foreground)
    for axis_name in ("left", "bottom"):
        axis = plot.getAxis(axis_name)
        axis.setPen(pen)
        axis.setTextPen(pen)
    units = series[0].units if series else None
    plot.setLabel("bottom", _axis_label(x, units), color=style.foreground)
    plot.setLabel("left", _axis_label(y, units), color=style.foreground)

    items: list[pg.ScatterPlotItem] = []
    for i, source in enumerate(series):
        xs, ys = source.values[x], source.values[y]
        mask = _finite_mask(xs, ys)
        color = pg.mkColor(color_for(i))
        color.setAlpha(_POINT_ALPHA)
        item = pg.ScatterPlotItem(
            x=xs[mask], y=ys[mask], data=source.ids[mask], size=_POINT_SIZE, brush=color, pen=None
        )
        plot.addItem(item)
        items.append(item)
    return items
