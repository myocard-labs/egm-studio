"""Unit tests for view_model.build_view_model over a tiny ClassifierBank."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest
from myocard_egm_data.banks import ClassifierBank
from myocard_egm_features.bundle import extract_all

from myocard_egm_studio.view_model import (
    FEATURE_COLUMNS,
    IDENTITY_COLUMNS,
    ProgressFn,
    build_view_model,
    feature_units,
)
from myocard_egm_studio.view_model.builder import _extract_features


class _Abort(Exception):
    """Stand-in for the GUI's cancel signal — a progress callback that raises."""


def test_feature_units_mv_bank() -> None:
    """A raw-mV bank labels peak_to_peak in mV and the spectral features in Hz."""
    units = feature_units("mv")
    assert units["peak_to_peak"] == "mV"
    assert units["spectral_centroid"] == "Hz"
    assert units["dominant_frequency"] == "Hz"
    # Counts / entropies / fractal dimension / [0,1] position are unitless.
    assert "zero_crossings" not in units
    assert "higuchi_fractal_dimension" not in units


def test_feature_units_zscore_drops_amplitude_unit() -> None:
    """A z-scored bank makes peak_to_peak unitless; the Hz features are unchanged."""
    units = feature_units("z_score")
    assert "peak_to_peak" not in units
    assert units["spectral_centroid"] == "Hz"


def test_columns_and_shape(tiny_classifier_bank: ClassifierBank) -> None:
    """The view-model has one row per trace and carries every identity + feature
    column, plus the explicit ``source`` group label and the producer's
    per-trace metadata flattened into columns (patient_id, simulation_id)."""
    vm = build_view_model(tiny_classifier_bank, source="Synthetic")
    assert len(vm) == tiny_classifier_bank.n_traces
    for col in IDENTITY_COLUMNS:
        assert col in vm.columns
    for col in FEATURE_COLUMNS:
        assert col in vm.columns
    assert "source" in vm.columns
    assert bool((vm["source"] == "Synthetic").all())
    assert "patient_id" in vm.columns
    assert "simulation_id" in vm.columns


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


def _recorder() -> tuple[list[tuple[int, int]], ProgressFn]:
    """A progress callback plus the list of ``(done, total)`` pairs it records."""
    calls: list[tuple[int, int]] = []

    def record(done: int, total: int) -> None:
        calls.append((done, total))

    return calls, record


def test_progress_reports_start_and_completion(tiny_classifier_bank: ClassifierBank) -> None:
    """``progress`` fires (0, n) first and (n, n) last, monotonically, and does not
    change the result — it only reports the feature-extraction pass."""
    n = tiny_classifier_bank.n_traces
    calls, record = _recorder()
    with_progress = build_view_model(tiny_classifier_bank, progress=record)
    assert calls[0] == (0, n)
    assert calls[-1] == (n, n)
    done = [c[0] for c in calls]
    assert done == sorted(done)  # monotonic non-decreasing
    assert all(total == n for _, total in calls)
    pd.testing.assert_frame_equal(with_progress, build_view_model(tiny_classifier_bank))


def test_extract_features_chunks_and_matches_whole(tiny_classifier_bank: ClassifierBank) -> None:
    """Chunked extraction reports a progress tick per chunk and, because per-trace
    features are independent, equals one ``extract_all`` over every trace."""
    signals = tiny_classifier_bank.signal_array()
    fs_hz = tiny_classifier_bank.uniform_fs_hz()
    n = len(signals)
    calls, record = _recorder()
    chunked = _extract_features(signals, fs_hz, record, chunk=4)
    assert calls == [(0, n), (4, n), (8, n), (12, n)]
    pd.testing.assert_frame_equal(chunked, extract_all(signals, fs_hz=fs_hz))


def test_extract_features_small_bank_single_pass(tiny_classifier_bank: ClassifierBank) -> None:
    """A bank no larger than one chunk extracts in a single ``extract_all`` call,
    still bracketed by (0, n) and (n, n) progress ticks."""
    signals = tiny_classifier_bank.signal_array()
    fs_hz = tiny_classifier_bank.uniform_fs_hz()
    n = len(signals)
    calls, record = _recorder()
    single = _extract_features(signals, fs_hz, record, chunk=n)
    assert calls == [(0, n), (n, n)]
    pd.testing.assert_frame_equal(single, extract_all(signals, fs_hz=fs_hz))


def test_progress_raise_aborts_the_build(tiny_classifier_bank: ClassifierBank) -> None:
    """A progress callback that raises (the Cancel path) aborts extraction between
    chunks — the exception propagates and the later chunks never run."""
    n = tiny_classifier_bank.n_traces
    calls: list[tuple[int, int]] = []

    def progress(done: int, total: int) -> None:
        calls.append((done, total))
        if done > 0:
            raise _Abort

    with pytest.raises(_Abort):
        build_view_model(tiny_classifier_bank, progress=progress)
    assert calls == [(0, n), (8, n)]  # stopped at the first chunk boundary (default chunk=8)
