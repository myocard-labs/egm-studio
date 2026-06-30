"""``calibration-reliability-diagram`` recipe — overlaid reliability curves.

The second synthetic-val metric figure (F-1.5.5), companion to
``roc-curve-multi-line``: one reliability curve per model on the synthetic
held-out validation set — binned mean predicted probability (x) against the
observed positive fraction (y) — over the ``y = x`` perfect-calibration line,
each annotated with its ECE. Shows whether an intervention kept the model
well-calibrated in-distribution. Synthetic-only: needs ground truth, which IAFDB
lacks [[feedback-iafdb-unlabeled-no-ml-validation]].

Reuses :class:`..inputs.PredictionGroup` and the ``prediction-histogram`` loader
(stacked registration), exactly like ``roc-curve-multi-line``; a group without
``labels`` is an error. The binning + ECE math lives in
:mod:`...analysis.metrics`; this recipe only plots.

``styling.n_bins`` (default 10) sets the reliability bins; ``inputs.positive_label``
(default 1) selects the positive class, matching what the loader scored ``probs``
for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.figure import Figure

from myocard_egm_studio.analysis import metrics
from myocard_egm_studio.charts.matplotlib import spec_fields
from myocard_egm_studio.charts.matplotlib.inputs import PredictionGroup
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: Near-square — calibration reads best on equal x/y scales (see ``set_aspect``).
_FIGSIZE = (4.6, 4.4)
#: The ``y = x`` perfectly-calibrated reference.
_PERFECT_COLOR = "0.6"
_MARKERSIZE = 4.0
_DEFAULT_N_BINS = 10


def _n_bins(spec: FigureSpec) -> int:
    """``styling.n_bins`` (default 10) — the reliability bin count."""
    return int((spec.styling or {}).get("n_bins", _DEFAULT_N_BINS))


@register("calibration-reliability-diagram")
def calibration_reliability_diagram(data: list[PredictionGroup], spec: FigureSpec) -> Figure:
    """Render the ``calibration-reliability-diagram`` figure. See the module docstring."""
    if not data:
        raise ValueError("calibration-reliability-diagram needs at least one PredictionGroup.")
    positive_label = spec_fields.positive_label(spec)
    n_bins = _n_bins(spec)

    with paper_style():
        figure = Figure(figsize=_FIGSIZE, layout="constrained")
        ax = figure.subplots()
        ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", color=_PERFECT_COLOR, linewidth=1.0)
        for i, group in enumerate(data):
            if group.labels is None:
                raise ValueError(
                    f"calibration-reliability-diagram needs ground-truth labels (synthetic val); "
                    f"group {group.name!r} is unlabeled — calibration is undefined without truth "
                    "(an IAFDB bank can't be scored)."
                )
            mean_pred, obs_freq, _ = metrics.reliability_curve(
                group.labels, group.probs, positive_label=positive_label, n_bins=n_bins
            )
            ece = metrics.expected_calibration_error(
                group.labels, group.probs, positive_label=positive_label, n_bins=n_bins
            )
            ax.plot(
                mean_pred,
                obs_freq,
                marker="o",
                markersize=_MARKERSIZE,
                color=color_for(i),
                label=f"{group.name} (ECE = {ece:.3f})",
            )
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_aspect("equal")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Observed positive fraction")
        ax.legend(loc="upper left")
    return figure
