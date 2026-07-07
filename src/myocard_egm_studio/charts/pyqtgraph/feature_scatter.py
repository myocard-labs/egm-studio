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
#: Fixed seed so an opt-in decimation subset is stable across redraws (a filter / axis /
#: theme change must not reshuffle the cloud), and identical between the two big banks.
_DECIMATION_SEED = 0


def _axis_label(feature: str, units: dict[str, str] | None) -> str:
    """``feature (unit)`` when the feature carries a unit, else the bare name."""
    unit = (units or {}).get(feature)
    return f"{feature} ({unit})" if unit else feature


def _subsample(count: int, cap: int | None) -> NDArray[np.intp] | None:
    """Indices of a deterministic uniform subsample of ``count`` points down to ``cap``.

    Returns None — meaning "plot every point" — when ``cap`` is None (decimation off) or the
    source already fits. The fixed seed keeps the chosen subset stable across redraws.
    """
    if cap is None or count <= cap:
        return None
    return np.random.default_rng(_DECIMATION_SEED).choice(count, size=cap, replace=False)


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
    max_points: int | None = None,
) -> list[pg.ScatterPlotItem]:
    """Draw each source's ``(x, y)`` points into ``plot``; return the scatter items.

    One ScatterPlotItem per series, coloured by load order (``color_for(i)``) to
    match the summary overlay + roster. Only points finite in *both* axes are drawn;
    each carries its ``row_id`` in the item's per-point ``data`` so the widget maps a
    click back to a trace. Returns the items (in series order) so the caller can
    connect ``sigClicked``; an empty ``series`` just clears + labels the plot. Axis
    units come from the first series (as the distribution overlay does).

    ``max_points`` (opt-in decimation) caps how many points each source plots: None
    draws every point (default), an int subsamples a deterministic uniform ``max_points``
    per source over that cap, so two large banks don't overplot each other. Decimation
    only thins the *display* — every trace stays in the result list.
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
        px, py, pids = xs[mask], ys[mask], source.ids[mask]
        keep = _subsample(px.size, max_points)
        if keep is not None:
            px, py, pids = px[keep], py[keep], pids[keep]
        color = pg.mkColor(color_for(i))
        color.setAlpha(_POINT_ALPHA)
        item = pg.ScatterPlotItem(x=px, y=py, data=pids, size=_POINT_SIZE, brush=color, pen=None)
        plot.addItem(item)
        items.append(item)
    return items
