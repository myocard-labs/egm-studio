"""``bar-chart-with-deltas`` recipe — a bar per category, optional baseline deltas.

A generic single-series bar chart (one value per category) with optional error
bars and, when a baseline category is named, a reference line at the baseline
value plus a signed *delta* annotation on every other bar. The catalog reuses it
across figures (F-1.5.3 sim-realism distance reduction, F-3.4 accuracy, F-5.6
per-patient volume, ...); the recipe knows nothing about what the bars mean — it
just draws :class:`..inputs.BarChartData` the loader prepared.

For F-1.5.3 each bar is a synthetic-variant bank's aggregate distance to the
IAFDB reference, the baseline is the un-intervened variant, and the deltas read
out "did this knob move the synthetic distribution toward real?" at a glance.

The recipe is pure plotting: the distance math lives in
``analysis/aggregation`` + the loader, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.figure import Figure

from myocard_egm_studio.charts.inputs import BarChartData
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: Figure sizing: width grows with the bar count (so labels don't crowd), height
#: is fixed. Inches.
_FIG_HEIGHT_IN = 3.4
_FIG_MIN_WIDTH_IN = 4.0
_BAR_SLOT_IN = 0.9  # horizontal allotment per bar
_FIG_PAD_IN = 1.5  # fixed margin added to the bar-count-scaled width

#: Bar + error-bar geometry.
_BAR_WIDTH = 0.7  # fraction of the category slot
_ERR_CAPSIZE = 3.0

#: Baseline reference line + delta-annotation styling.
_BASELINE_LINE_COLOR = "0.4"
_BASELINE_LINE_WIDTH = 1.0
_DELTA_FONTSIZE = 8
_DELTA_TEXT_COLOR = "0.2"
_DELTA_PAD_FRAC = 0.03  # vertical offset of the annotation above a bar, as a
#                         fraction of the tallest bar

#: Rotate the category tick labels once there are many bars or any long label.
_ROTATE_BAR_THRESHOLD = 4
_ROTATE_LABEL_LEN = 8


def _needs_rotation(categories: list[str]) -> bool:
    """Rotate x-tick labels when bars are many or any label is long."""
    return len(categories) > _ROTATE_BAR_THRESHOLD or any(
        len(c) > _ROTATE_LABEL_LEN for c in categories
    )


def _annotate_deltas(ax: Axes, xs: np.ndarray, values: np.ndarray, baseline_index: int) -> None:
    """Reference line at the baseline value + a signed delta on every other bar."""
    base = float(values[baseline_index])
    ax.axhline(
        base, color=_BASELINE_LINE_COLOR, linestyle="--", linewidth=_BASELINE_LINE_WIDTH, zorder=0
    )
    top = float(np.nanmax(values)) if values.size else 1.0
    pad = _DELTA_PAD_FRAC * (top if top > 0 else 1.0)
    for i, value in enumerate(values):
        label = "baseline" if i == baseline_index else f"{float(value) - base:+.2f}"
        ax.text(
            xs[i],
            float(value) + pad,
            label,
            ha="center",
            va="bottom",
            fontsize=_DELTA_FONTSIZE,
            color=_DELTA_TEXT_COLOR,
        )


@register("bar-chart-with-deltas")
def bar_chart_with_deltas(data: BarChartData, spec: FigureSpec) -> Figure:
    """Render the ``bar-chart-with-deltas`` figure. See the module docstring."""
    categories = data.categories
    if not categories:
        raise ValueError("bar-chart-with-deltas needs at least one category.")
    values = np.asarray(data.values, dtype=np.float64)
    if values.shape != (len(categories),):
        raise ValueError(
            f"values shape {values.shape} does not match {len(categories)} categories."
        )
    errors = None
    if data.errors is not None:
        errors = np.asarray(data.errors, dtype=np.float64)
        if errors.shape != values.shape:
            raise ValueError("errors must align one-to-one with values.")
    baseline_index = data.baseline_index
    if baseline_index is not None and not 0 <= baseline_index < len(categories):
        raise ValueError(
            f"baseline_index {baseline_index} is out of range for {len(categories)} categories."
        )

    xs = np.arange(len(categories))
    colors = [color_for(1 if i == baseline_index else 0) for i in range(len(categories))]
    rotated = _needs_rotation(categories)

    with paper_style():
        width = max(_FIG_MIN_WIDTH_IN, _BAR_SLOT_IN * len(categories) + _FIG_PAD_IN)
        figure = Figure(figsize=(width, _FIG_HEIGHT_IN), layout="constrained")
        ax = figure.subplots()
        ax.bar(xs, values, width=_BAR_WIDTH, color=colors, yerr=errors, capsize=_ERR_CAPSIZE)
        ax.set_xticks(xs)
        ax.set_xticklabels(
            categories,
            rotation=30 if rotated else 0,
            ha="right" if rotated else "center",
        )
        if data.value_label:
            ax.set_ylabel(data.value_label)
        if baseline_index is not None:
            _annotate_deltas(ax, xs, values, baseline_index)
    return figure
