"""``training-curve`` recipe — loss + selection-metric vs epoch.

F-1.5.11: the standard ML training-curve figure for one representative run — a
top panel of loss curves (train + val) and a bottom panel of the selection
metric (val AUROC), sharing the epoch x-axis, with the best / early-stopping
epoch marked. Pure plotting; the loader reads the training run record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.figure import Figure

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

_FIGSIZE = (5.5, 4.6)
_LINE_MARKER = "."
_LINE_LW = 1.2
#: Best-epoch marker (dashed vertical line).
_BEST_COLOR = "0.5"


@register("training-curve")
def training_curve(data: TrainingCurve, spec: FigureSpec) -> Figure:
    """Render the ``training-curve`` figure. See the module docstring."""
    if data.epochs.size == 0:
        raise ValueError("training-curve needs at least one epoch.")

    with paper_style():
        figure = Figure(figsize=_FIGSIZE, layout="constrained")
        ax_loss, ax_metric = figure.subplots(2, 1, sharex=True)
        for i, (name, values) in enumerate(data.loss.items()):
            ax_loss.plot(
                data.epochs,
                values,
                color=color_for(i),
                marker=_LINE_MARKER,
                linewidth=_LINE_LW,
                label=name,
            )
        for i, (name, values) in enumerate(data.metric.items()):
            ax_metric.plot(
                data.epochs,
                values,
                color=color_for(i),
                marker=_LINE_MARKER,
                linewidth=_LINE_LW,
                label=name,
            )
        if data.best_epoch is not None:
            ax_loss.axvline(
                data.best_epoch,
                color=_BEST_COLOR,
                linestyle="--",
                linewidth=1.0,
                label=f"best (epoch {data.best_epoch})",
            )
            ax_metric.axvline(data.best_epoch, color=_BEST_COLOR, linestyle="--", linewidth=1.0)
        ax_loss.set_ylabel("loss")
        ax_loss.legend()
        ax_metric.set_ylabel(data.metric_name)
        ax_metric.set_xlabel("epoch")
        if len(data.metric) > 1:  # a single val series is self-evident from the y-label
            ax_metric.legend()
    return figure
