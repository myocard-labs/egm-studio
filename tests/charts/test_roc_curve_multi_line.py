"""Tests for the ``roc-curve-multi-line`` matplotlib recipe.

A snapshot (two ROC curves of differing AUROC + the chance diagonal) plus logic
tests over small in-memory PredictionGroups. The ROC / AUROC math itself is
pinned in ``tests/analysis/test_metrics.py``; here we check the recipe wires it
into lines + legend correctly and rejects unlabeled groups.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.inputs import PredictionGroup
from myocard_egm_studio.charts.matplotlib.roc_curve_multi_line import roc_curve_multi_line

_TOL = 20.0


def _spec() -> FigureSpec:
    """Minimal valid roc-curve-multi-line FigureSpec (the recipe is data-driven)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_roc_curve_test",
            "description": "roc-curve-multi-line recipe test spec",
            "recipe": "roc-curve-multi-line",
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _scored_group(name: str, *, separation: float, seed: int, n: int = 120) -> PredictionGroup:
    """A labeled group whose positive-class scores are shifted up by ``separation``.

    Larger separation -> the positives' P(fibrotic) sits higher -> higher AUROC.
    Deterministic via ``seed`` so the snapshot is stable.
    """
    rng = np.random.default_rng(seed)
    labels = np.array([0] * (n // 2) + [1] * (n // 2), dtype=np.int64)
    probs = rng.random(n) * 0.5  # base scores in [0, 0.5)
    probs[labels == 1] += separation  # push the positives up
    probs = np.clip(probs, 0.0, 1.0).astype(np.float64)
    return PredictionGroup(
        name=name, probs=probs, labels=labels, label_names={0: "healthy", 1: "fibrotic"}
    )


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_two_curves_with_chance_diagonal() -> Figure:
    """Two models of differing AUROC overlaid + the chance diagonal — the F-1.5.4 shape."""
    data = [
        _scored_group("Baseline", separation=0.45, seed=1),
        _scored_group("Intervention A", separation=0.20, seed=2),
    ]
    return roc_curve_multi_line(data, _spec())


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def test_one_line_per_group_plus_chance() -> None:
    """One ROC line per group, plus the single chance diagonal."""
    data = [_scored_group("A", separation=0.4, seed=1), _scored_group("B", separation=0.2, seed=2)]
    fig = roc_curve_multi_line(data, _spec())
    assert len(fig.axes[0].lines) == 3  # 2 ROC curves + chance


def test_auroc_in_legend_labels() -> None:
    """Each curve carries its AUROC in the legend label."""
    fig = roc_curve_multi_line([_scored_group("A", separation=0.4, seed=1)], _spec())
    legend = fig.axes[0].get_legend()
    assert legend is not None
    labels = [t.get_text() for t in legend.get_texts()]
    assert any("AUROC = " in lab for lab in labels)


def test_empty_raises() -> None:
    """No groups is a caller error."""
    with pytest.raises(ValueError, match="at least one"):
        roc_curve_multi_line([], _spec())


def test_unlabeled_group_raises() -> None:
    """A group without truth labels can't be scored — ROC is undefined."""
    unlabeled = PredictionGroup(name="IAFDB", probs=np.array([0.2, 0.8, 0.5], dtype=np.float64))
    with pytest.raises(ValueError, match="unlabeled"):
        roc_curve_multi_line([unlabeled], _spec())
