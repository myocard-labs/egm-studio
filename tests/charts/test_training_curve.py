"""Tests for the ``training-curve`` matplotlib recipe.

A snapshot (loss + metric panels) plus logic over an in-memory TrainingCurve. The
run-record -> curves extraction lives in the loader (tested in
tests/figures/test_loaders.py); here we check the two-panel layout, the train +
val loss lines, and the best-epoch marker.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.matplotlib.training_curve import training_curve

_TOL = 20.0


def _spec() -> FigureSpec:
    """Minimal valid training-curve FigureSpec (the recipe is data-driven)."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_training_curve_test",
            "description": "training-curve recipe test spec",
            "recipe": "training-curve",
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _curve(*, best: int | None = 4) -> TrainingCurve:
    return TrainingCurve(
        epochs=np.arange(1, 7, dtype=np.int64),
        loss={
            "train": np.linspace(0.5, 0.1, 6).astype(np.float64),
            "val": np.linspace(0.55, 0.15, 6).astype(np.float64),
        },
        metric={"val": np.linspace(0.6, 0.96, 6).astype(np.float64)},
        metric_name="AUROC",
        best_epoch=best,
    )


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_loss_and_metric_panels() -> Figure:
    """Two panels (loss + AUROC) sharing the epoch axis, best epoch marked — F-1.5.11."""
    return training_curve(_curve(), _spec())


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def test_two_panels() -> None:
    """Loss panel + metric panel."""
    fig = training_curve(_curve(), _spec())
    assert len(fig.axes) == 2


def test_loss_panel_has_train_val_and_best_marker() -> None:
    """The loss panel carries a train + val line plus the best-epoch marker."""
    labels = {ln.get_label() for ln in training_curve(_curve(best=4), _spec()).axes[0].lines}
    assert {"train", "val"} <= labels
    assert any("best" in str(lab) for lab in labels)  # the axvline's legend label


def test_no_best_marker_when_none() -> None:
    """best_epoch=None draws no marker (loss panel is just train + val)."""
    fig = training_curve(_curve(best=None), _spec())
    assert len(fig.axes[0].lines) == 2


def test_empty_raises() -> None:
    """No epochs is a caller error."""
    empty = TrainingCurve(epochs=np.array([], dtype=np.int64), loss={}, metric={})
    with pytest.raises(ValueError, match="at least one epoch"):
        training_curve(empty, _spec())
