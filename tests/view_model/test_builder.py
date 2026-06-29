"""Unit tests for view_model.build_view_model over a tiny ClassifierBank."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from myocard_egm_data.banks import ClassifierBank

from myocard_egm_studio.view_model import (
    FEATURE_COLUMNS,
    IDENTITY_COLUMNS,
    build_view_model,
)


def test_columns_and_shape(tiny_classifier_bank: ClassifierBank) -> None:
    """The view-model has one row per trace and carries every identity + feature
    column, plus the explicit ``source`` group label and the producer's
    per-trace metadata flattened into columns (patient_id, sim_id)."""
    vm = build_view_model(tiny_classifier_bank, source="Synthetic")
    assert len(vm) == tiny_classifier_bank.n_traces
    for col in IDENTITY_COLUMNS:
        assert col in vm.columns
    for col in FEATURE_COLUMNS:
        assert col in vm.columns
    assert "source" in vm.columns
    assert bool((vm["source"] == "Synthetic").all())
    assert "patient_id" in vm.columns
    assert "sim_id" in vm.columns


def test_identity_values(tiny_classifier_bank: ClassifierBank) -> None:
    """Identity columns are populated from the bank: the source bank's stable id
    + type, ``label_name`` mapped through ``bank.labels``, and ``trace_idx``
    equal to the row's position."""
    vm = build_view_model(tiny_classifier_bank)
    row0 = vm.iloc[0]
    assert row0["source_bank_id"] == "tbank_studio_fixture_2026-06-27"
    assert row0["source_bank_type"] == "synthetic"
    assert row0["label_name"] == tiny_classifier_bank.labels[row0["label"]]
    assert list(vm["trace_idx"]) == list(range(tiny_classifier_bank.n_traces))


def test_features_are_finite(tiny_classifier_bank: ClassifierBank) -> None:
    """Every egm-features column is finite for the well-behaved fixture traces —
    a NaN would signal a feature-extraction problem leaking into the view-model."""
    vm = build_view_model(tiny_classifier_bank)
    for col in FEATURE_COLUMNS:
        assert np.isfinite(vm[col].to_numpy(dtype=float)).all(), col


def test_unlabeled_bank_has_null_labels(tiny_unlabeled_bank: ClassifierBank) -> None:
    """An unlabeled bank (the IAFDB shape) yields null ``label`` / ``label_name``
    columns rather than raising — the view-model supports label-free banks."""
    vm = build_view_model(tiny_unlabeled_bank, with_features=False)
    assert vm["label"].isna().all()
    assert vm["label_name"].isna().all()


def test_without_features_omits_feature_columns(tiny_classifier_bank: ClassifierBank) -> None:
    """``with_features=False`` returns a metadata-only frame, skipping the
    (slow) egm-features extraction and all 11 feature columns."""
    vm = build_view_model(tiny_classifier_bank, with_features=False)
    assert not any(col in vm.columns for col in FEATURE_COLUMNS)


def test_empty_bank_returns_empty_frame(tiny_classifier_bank: ClassifierBank) -> None:
    """An empty bank returns a zero-row frame that still carries the fixed
    identity columns, so downstream code can rely on the schema being present."""
    empty = dataclasses.replace(tiny_classifier_bank, traces=[])
    vm = build_view_model(empty)
    assert len(vm) == 0
    for col in IDENTITY_COLUMNS:
        assert col in vm.columns


def test_mixed_sample_rate_raises(tiny_classifier_bank: ClassifierBank) -> None:
    """A bank whose traces disagree on ``freq_hz`` can't feed the single-rate
    feature extractor, so build_view_model raises (via ClassifierBank.uniform_fs_hz)."""
    traces = list(tiny_classifier_bank.traces)
    traces[0] = dataclasses.replace(traces[0], freq_hz=500.0)
    bank = dataclasses.replace(tiny_classifier_bank, traces=traces)
    with pytest.raises(ValueError, match="single shared sample rate"):
        build_view_model(bank)
