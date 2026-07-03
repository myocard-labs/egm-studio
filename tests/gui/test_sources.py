"""Tests for the direct bank-open loader (gui/sources)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.banks import ClassifierBank, write_classifier_bank

from myocard_egm_studio.gui.sources import load_traces, load_view_model, traces_from_bank
from myocard_egm_studio.gui.widgets import TraceData
from myocard_egm_studio.view_model import FEATURE_COLUMNS, IDENTITY_COLUMNS


def test_traces_from_bank_adapts(tiny_classifier_bank: ClassifierBank) -> None:
    traces = traces_from_bank(tiny_classifier_bank)
    assert len(traces) == len(tiny_classifier_bank.traces)
    assert all(isinstance(t, TraceData) for t in traces)
    assert traces[0].fs_hz == 1000.0
    assert traces[0].signal.ndim == 1
    assert "pair" in traces[0].label  # electrode reads "pair N", built from trace metadata


def test_traces_from_bank_limit(tiny_classifier_bank: ClassifierBank) -> None:
    assert len(traces_from_bank(tiny_classifier_bank, limit=3)) == 3


def test_load_traces_roundtrips_via_hdf5(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    path = tmp_path / "bank.h5"
    write_classifier_bank(tiny_classifier_bank, path)
    traces = load_traces(path, limit=4)
    assert len(traces) == 4
    assert traces[0].label  # a non-empty metadata label


def test_load_view_model_joins_identity_metadata_features(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    path = tmp_path / "bank.h5"
    write_classifier_bank(tiny_classifier_bank, path)
    df = load_view_model(path, source="Synthetic v1.5")
    assert len(df) == len(tiny_classifier_bank.traces)
    assert list(df["source"].unique()) == ["Synthetic v1.5"]  # constant for one bank
    assert set(IDENTITY_COLUMNS).issubset(df.columns)
    assert set(FEATURE_COLUMNS).issubset(df.columns)
    assert "patient_id" in df.columns  # the producer's per-trace metadata is flattened in


def test_load_view_model_source_defaults_to_bank_id(
    tiny_predictions_bank: ClassifierBank, tmp_path: Path
) -> None:
    path = tmp_path / "preds.h5"
    write_classifier_bank(tiny_predictions_bank, path)
    df = load_view_model(path)  # no explicit source
    assert list(df["source"].unique()) == ["lpred_studio_fixture_2026-06-28"]


def test_load_view_model_source_falls_back_to_file_stem(
    tiny_classifier_bank: ClassifierBank, tmp_path: Path
) -> None:
    path = tmp_path / "synth_bank.h5"  # the fixture bank carries no stable id
    write_classifier_bank(tiny_classifier_bank, path)
    df = load_view_model(path)
    assert list(df["source"].unique()) == ["synth_bank"]
