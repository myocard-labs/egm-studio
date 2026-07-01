"""Tests for the direct bank-open loader (gui/sources)."""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.banks import ClassifierBank, write_classifier_bank

from myocard_egm_studio.gui.sources import load_traces, loaded_bank, traces_from_bank
from myocard_egm_studio.gui.widgets import TraceData


def test_traces_from_bank_adapts(tiny_classifier_bank: ClassifierBank) -> None:
    traces = traces_from_bank(tiny_classifier_bank)
    assert len(traces) == len(tiny_classifier_bank.traces)
    assert all(isinstance(t, TraceData) for t in traces)
    assert traces[0].fs_hz == 1000.0
    assert traces[0].signal.ndim == 1


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


def test_loaded_bank_carries_fields(tiny_classifier_bank: ClassifierBank) -> None:
    loaded = loaded_bank(tiny_classifier_bank)
    assert loaded.bank_type == "synthetic"
    assert len(loaded.traces) == len(tiny_classifier_bank.traces)
    first = loaded.traces[0]
    assert first.index == 0
    assert first.fields["class"] in {"healthy", "fibrotic", "n/a"}
    assert "patient_id" in first.fields  # raw metadata preserved for later use
    assert first.data.signal.ndim == 1
    assert "pair" in first.data.label  # electrode reads "pair N", not a bare number
