"""Tests for the ``calibration-reliability-diagram`` matplotlib recipe.

A snapshot (a well-calibrated curve vs an over-confident one + the y=x line)
plus logic tests over small in-memory PredictionGroups. The reliability / ECE
math is pinned in ``tests/analysis/test_metrics.py``; here we check the recipe
wires it into lines + legend and rejects unlabeled groups.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.calibration_reliability_diagram import (
    calibration_reliability_diagram,
)
from myocard_egm_studio.charts.matplotlib.inputs import PredictionGroup

_TOL = 20.0


def _spec() -> FigureSpec:
    """Minimal valid calibration-reliability-diagram FigureSpec (the recipe is data-driven)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_calibration_test",
            "description": "calibration-reliability-diagram recipe test spec",
            "recipe": "calibration-reliability-diagram",
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _group(name: str, *, skew: float, seed: int, n: int = 800) -> PredictionGroup:
    """Labeled group; ``skew=0`` is well-calibrated, ``skew>0`` is over-confident.

    The true positive rate is the predicted prob pulled toward 0.5 by ``skew``,
    so a positive skew makes the predictions too extreme for the observed
    outcomes (the reliability curve flattens away from the diagonal). Deterministic
    via ``seed`` so the snapshot is stable.
    """
    rng = np.random.default_rng(seed)
    probs = rng.random(n).astype(np.float64)
    true_rate = 0.5 + (probs - 0.5) * (1.0 - skew)
    labels = (rng.random(n) < true_rate).astype(np.int64)
    return PredictionGroup(
        name=name, probs=probs, labels=labels, label_names={0: "healthy", 1: "fibrotic"}
    )


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_calibrated_vs_overconfident() -> Figure:
    """A near-diagonal curve and an over-confident one + the y=x line — the F-1.5.5 shape."""
    data = [
        _group("Well calibrated", skew=0.0, seed=1),
        _group("Over-confident", skew=0.6, seed=2),
    ]
    return calibration_reliability_diagram(data, _spec())


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def test_one_line_per_group_plus_diagonal() -> None:
    """One reliability line per group, plus the single y=x diagonal."""
    data = [_group("A", skew=0.0, seed=1), _group("B", skew=0.5, seed=2)]
    fig = calibration_reliability_diagram(data, _spec())
    assert len(fig.axes[0].lines) == 3  # 2 reliability curves + diagonal


def test_ece_in_legend_labels() -> None:
    """Each curve carries its ECE in the legend label."""
    fig = calibration_reliability_diagram([_group("A", skew=0.0, seed=1)], _spec())
    legend = fig.axes[0].get_legend()
    assert legend is not None
    labels = [t.get_text() for t in legend.get_texts()]
    assert any("ECE = " in lab for lab in labels)


def test_empty_raises() -> None:
    """No groups is a caller error."""
    with pytest.raises(ValueError, match="at least one"):
        calibration_reliability_diagram([], _spec())


def test_unlabeled_group_raises() -> None:
    """A group without truth labels can't be calibrated — undefined without truth."""
    unlabeled = PredictionGroup(name="IAFDB", probs=np.array([0.2, 0.8, 0.5], dtype=np.float64))
    with pytest.raises(ValueError, match="unlabeled"):
        calibration_reliability_diagram([unlabeled], _spec())
