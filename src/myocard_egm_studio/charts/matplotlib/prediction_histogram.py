"""``prediction-histogram`` recipe — histograms of model output P(class).

The highest-leverage recipe in the project: it covers both the labeled case
(per-class P(positive) histograms on a synthetic eval set) and the label-free
case (the qualitative IAFDB output distribution), which together account for
the bulk of the Phase-1.5 realism figures in
``project/paper_figure_inventory.md``.

Data is a list of :class:`..inputs.PredictionGroup`. Two layouts, selected by
``spec.layout["mode"]``:

- ``"panels"`` (default) — one subplot per group, shared probability x-axis. A
  group carrying truth ``labels`` is split into per-class histograms (the
  separation a good classifier should show); an unlabeled group draws a single
  distribution.
- ``"overlay"`` — one axis, each group's distribution drawn as a step outline
  distinguished by color + legend (the synthetic-vs-real de-saturation view).

Styling keys (``spec.styling``): ``bins`` (int, default 30), ``density``
(bool, default False), ``xlabel`` (str, default ``"P(positive class)"``).

Histogram, not KDE: predicted probabilities saturate (the IAFDB case pins
near 1.0), where a Gaussian KDE covariance is singular. Fixed bins over an
explicit ``(0, 1)`` range stay well-defined and align across groups.
[analysis/distributions.py]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.figure import Figure

from myocard_egm_studio.analysis import distributions
from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: Probability axis range; bins align across groups when fixed here.
_PROB_RANGE = (0.0, 1.0)


def _styling(spec: FigureSpec) -> tuple[int, bool, str]:
    """Pull (bins, density, xlabel) from ``spec.styling`` with defaults."""
    styling = spec.styling or {}
    bins = int(styling.get("bins", 30))
    density = bool(styling.get("density", False))
    xlabel = str(styling.get("xlabel", "P(positive class)"))
    return bins, density, xlabel


def _draw_panel(ax: Axes, group: PredictionGroup, *, bins: int, density: bool) -> None:
    """Draw one group into one panel — per-class split when labels are present."""
    if group.labels is None:
        counts, edges = distributions.histogram(
            group.probs, bins=bins, range=_PROB_RANGE, density=density
        )
        ax.stairs(counts, edges, fill=True, color=color_for(0), alpha=0.85)
        return
    names = group.label_names or {}
    classes = [int(c) for c in np.unique(group.labels)]
    for i, cls in enumerate(classes):
        selected = group.probs[group.labels == cls]
        if selected.size == 0:
            continue
        counts, edges = distributions.histogram(
            selected, bins=bins, range=_PROB_RANGE, density=density
        )
        ax.stairs(
            counts,
            edges,
            fill=True,
            alpha=0.55,
            color=color_for(i),
            label=names.get(cls, f"class {cls}"),
        )
    ax.legend()


@register("prediction-histogram")
def prediction_histogram(data: list[PredictionGroup], spec: FigureSpec) -> Figure:
    """Render the ``prediction-histogram`` figure. See the module docstring."""
    if not data:
        raise ValueError("prediction-histogram needs at least one PredictionGroup.")
    bins, density, xlabel = _styling(spec)
    mode = str((spec.layout or {}).get("mode", "panels"))
    ylabel = "density" if density else "count"

    with paper_style():
        if mode == "overlay":
            figure = Figure(figsize=(5.0, 3.2), layout="constrained")
            ax = figure.subplots()
            for i, group in enumerate(data):
                counts, edges = distributions.histogram(
                    group.probs, bins=bins, range=_PROB_RANGE, density=density
                )
                ax.stairs(counts, edges, color=color_for(i), label=group.name)
            ax.set_xlim(*_PROB_RANGE)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.legend()
        elif mode == "panels":
            n = len(data)
            figure = Figure(figsize=(3.0 * n, 3.2), layout="constrained")
            axes = np.atleast_1d(figure.subplots(1, n, sharex=True, squeeze=True))
            for ax, group in zip(axes, data, strict=True):
                _draw_panel(ax, group, bins=bins, density=density)
                ax.set_xlim(*_PROB_RANGE)
                ax.set_title(group.name)
                ax.set_xlabel(xlabel)
            axes[0].set_ylabel(ylabel)
        else:
            raise ValueError(
                f"prediction-histogram: unknown layout mode {mode!r}; use 'panels' or 'overlay'."
            )
    return figure
