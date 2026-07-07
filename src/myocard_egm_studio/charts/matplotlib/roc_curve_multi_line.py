"""``roc-curve-multi-line`` recipe — overlaid ROC curves, one per model.

The first synthetic-val *metric* figure (F-1.5.4): one ROC curve per
intervention model on the synthetic held-out validation set, each annotated with
its AUROC. Synthetic-only by necessity — ROC needs ground truth, which IAFDB
lacks [[feedback-iafdb-unlabeled-no-ml-validation]]. It answers the companion
question to the F-1.5.3 realism bars: did an intervention that improved realism
*cost* in-distribution discrimination?

Reuses :class:`..inputs.PredictionGroup`: each group is one model's predictions
on the (labeled) synthetic val set, so ``probs`` = P(positive class) is the ROC
score and ``labels`` is the truth. A group with no ``labels`` is an error (no
truth, no ROC). The ROC / AUROC math lives in :mod:`...analysis.metrics`; this
recipe only plots.

``positive_label`` (via ``inputs.positive_label``, default 1) selects the
positive class and must match what the loader used to build ``probs`` — the same
key :func:`...loaders.load_prediction_groups` reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.figure import Figure

from myocard_egm_studio.analysis import metrics
from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.matplotlib import spec_fields
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

#: Near-square — a ROC reads best on equal x/y scales (see ``set_aspect`` below).
_FIGSIZE = (4.6, 4.4)
#: The no-skill diagonal (FPR == TPR).
_CHANCE_COLOR = "0.6"


@register("roc-curve-multi-line")
def roc_curve_multi_line(data: list[PredictionGroup], spec: FigureSpec) -> Figure:
    """Render the ``roc-curve-multi-line`` figure. See the module docstring."""
    if not data:
        raise ValueError("roc-curve-multi-line needs at least one PredictionGroup.")
    positive_label = spec_fields.positive_label(spec)

    with paper_style():
        figure = Figure(figsize=_FIGSIZE, layout="constrained")
        ax = figure.subplots()
        ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", color=_CHANCE_COLOR, linewidth=1.0)
        for i, group in enumerate(data):
            if group.labels is None:
                raise ValueError(
                    f"roc-curve-multi-line needs ground-truth labels (synthetic val); group "
                    f"{group.name!r} is unlabeled — ROC is undefined without truth "
                    "(an IAFDB bank can't be scored)."
                )
            fpr, tpr = metrics.roc_curve(group.labels, group.probs, positive_label=positive_label)
            auc = metrics.auroc(group.labels, group.probs, positive_label=positive_label)
            ax.plot(fpr, tpr, color=color_for(i), label=f"{group.name} (AUROC = {auc:.3f})")
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_aspect("equal")
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.legend(loc="lower right")
    return figure
