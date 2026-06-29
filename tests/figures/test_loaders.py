"""Tests for figures.loaders — the bank -> recipe-input adapter + resolution.

The adapter (``prediction_group_from_bank``) is permanent Block-7 code; these
tests pin its softmax derivation and its labeled/unlabeled/error handling. The
loader + ``resolve_recipe_data`` tests cover the ``{bank_id: path}`` resolution
the CLI drives (and the manifest will drive later).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest
from myocard_egm_data.banks import (
    ClassifierBank,
    ClassifierBankMetaData,
    ClassifierPrediction,
    ClassifierTrace,
    write_classifier_bank,
)
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.figures.loaders import (
    LoaderNotRegisteredError,
    UnmappedBankIdError,
    load_group_banks,
    load_prediction_groups,
    prediction_group_from_bank,
    resolve_recipe_data,
)

_FIXTURE_PRED_ID = "lpred_studio_fixture_2026-06-28"


def _ph_spec(*groups: tuple[str, str]) -> FigureSpec:
    """A prediction-histogram spec whose inputs.groups are (name, bank_id) pairs."""
    return FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_loader_test",
            "description": "loader test spec",
            "recipe": "prediction-histogram",
            "inputs": {"groups": [{"name": n, "bank_id": b} for n, b in groups]},
            "output": {"format": "png", "path": "out.png"},
        }
    )


def _single_trace_pred_bank(*, logits: dict[int, float], label_truth: int) -> ClassifierBank:
    """A 1-trace lpred_ bank with explicit logits, for exact softmax checks."""
    trace = ClassifierTrace(
        bank_id="tbank_single_2026-06-28",
        signal=np.zeros(8, dtype=np.float32),
        freq_hz=1000.0,
        amp_type="mv",
        split=None,
        label_truth=label_truth,
        prediction=ClassifierPrediction(
            label_pred=int(logits[1] >= logits[0]),
            label_prob=0.5,
            pred_logits=logits,
        ),
        trace_metadata={},
    )
    meta = ClassifierBankMetaData(
        bank_id="tbank_single_2026-06-28",
        bank_type="synthetic",
        bank_path="<mem>",
        bank_metadata={},
    )
    return ClassifierBank(
        id="lpred_single_2026-06-28",
        banks=[meta],
        traces=[trace],
        labels={0: "healthy", 1: "fibrotic"},
    )


# --- adapter -------------------------------------------------------------- #


def test_adapter_labeled_separates(tiny_predictions_bank: ClassifierBank) -> None:
    """A labeled predictions bank yields per-class labels + names, and healthy
    probs sit below fibrotic (the fixture logits were pushed toward truth)."""
    group = prediction_group_from_bank(tiny_predictions_bank, name="Synthetic val")
    n = len(tiny_predictions_bank.traces)
    assert group.name == "Synthetic val"
    assert group.probs.shape == (n,)
    assert np.all((group.probs >= 0.0) & (group.probs <= 1.0))
    assert group.labels is not None
    assert group.labels.shape == (n,)
    assert group.label_names == {0: "healthy", 1: "fibrotic"}
    assert group.probs[group.labels == 0].mean() < group.probs[group.labels == 1].mean()


def test_adapter_unlabeled_single_distribution(
    tiny_unlabeled_predictions_bank: ClassifierBank,
) -> None:
    """An unlabeled predictions bank (upred_) yields labels=None / names=None."""
    group = prediction_group_from_bank(tiny_unlabeled_predictions_bank, name="IAFDB")
    assert group.labels is None
    assert group.label_names is None
    assert np.all((group.probs >= 0.0) & (group.probs <= 1.0))


def test_adapter_softmax_positive_prob() -> None:
    """P(positive) is softmax(pred_logits)[1]: logits {0:0, 1:ln3} -> 0.75."""
    bank = _single_trace_pred_bank(logits={0: 0.0, 1: float(np.log(3.0))}, label_truth=1)
    group = prediction_group_from_bank(bank, name="x")
    assert group.probs[0] == pytest.approx(0.75)


def test_adapter_raises_without_prediction(tiny_classifier_bank: ClassifierBank) -> None:
    """A bank whose traces have no prediction is rejected (not an lpred_/upred_)."""
    with pytest.raises(ValueError, match="no prediction"):
        prediction_group_from_bank(tiny_classifier_bank, name="x")


def test_adapter_raises_on_mixed_labels(tiny_predictions_bank: ClassifierBank) -> None:
    """A bank mixing labeled + unlabeled traces is rejected."""
    traces = list(tiny_predictions_bank.traces)
    traces[0] = dataclasses.replace(traces[0], label_truth=None)
    bank = dataclasses.replace(tiny_predictions_bank, traces=traces)
    with pytest.raises(ValueError, match="mixes"):
        prediction_group_from_bank(bank, name="x")


# --- shared group->bank resolution ---------------------------------------- #


def test_load_group_banks_resolves_in_spec_order(
    tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """Returns (group name, loaded bank) pairs in spec order."""
    path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, path)
    spec = _ph_spec(("Synthetic val", _FIXTURE_PRED_ID))
    pairs = load_group_banks(spec, {_FIXTURE_PRED_ID: str(path)})
    assert [name for name, _ in pairs] == ["Synthetic val"]
    assert pairs[0][1].n_traces == tiny_predictions_bank.n_traces


def test_load_group_banks_empty_groups_raises() -> None:
    """A spec with no inputs.groups is a usage error, not an empty result."""
    spec = FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_no_groups",
            "description": "no groups to load",
            "recipe": "prediction-histogram",
            "output": {"format": "png", "path": "out.png"},
        }
    )
    with pytest.raises(ValueError, match=r"no inputs\.groups"):
        load_group_banks(spec, {})


def test_load_group_banks_unmapped_raises() -> None:
    """An unmapped bank_id raises UnmappedBankIdError naming the gap."""
    spec = _ph_spec(("X", "lpred_absent_2026-06-28"))
    with pytest.raises(UnmappedBankIdError, match="lpred_absent_2026-06-28"):
        load_group_banks(spec, {})


# --- loader + resolution -------------------------------------------------- #


def test_load_prediction_groups_round_trip(
    tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """A spec group resolves through {bank_id: path}: the written bank loads +
    adapts into a PredictionGroup, in spec order."""
    path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, path)
    spec = _ph_spec(("Synthetic val", _FIXTURE_PRED_ID))
    groups = load_prediction_groups(spec, {_FIXTURE_PRED_ID: str(path)})
    assert [g.name for g in groups] == ["Synthetic val"]
    assert groups[0].labels is not None


def test_load_prediction_groups_unmapped_raises() -> None:
    """A group whose bank_id has no path entry raises UnmappedBankIdError naming it."""
    spec = _ph_spec(("X", "lpred_absent_2026-06-28"))
    with pytest.raises(UnmappedBankIdError, match="lpred_absent_2026-06-28"):
        load_prediction_groups(spec, {})


def test_resolve_recipe_data_dispatches(
    tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    """resolve_recipe_data routes a prediction-histogram spec to its loader."""
    path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, path)
    spec = _ph_spec(("Synthetic val", _FIXTURE_PRED_ID))
    data = resolve_recipe_data(spec, {_FIXTURE_PRED_ID: str(path)})
    assert isinstance(data, list)
    assert len(data) == 1


def test_resolve_recipe_data_no_loader_raises() -> None:
    """A recipe with no registered loader raises LoaderNotRegisteredError."""
    spec = FigureSpec.model_validate(
        {
            "schema_version": "1",
            "id": "fig_no_loader",
            "description": "no loader for this recipe yet",
            "recipe": "feature-distribution-overlay",
            "output": {"format": "png", "path": "out.png"},
        }
    )
    with pytest.raises(LoaderNotRegisteredError, match="feature-distribution-overlay"):
        resolve_recipe_data(spec, {})
