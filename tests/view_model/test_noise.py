"""Tests for view_model.noise — a noise bank's segments prepared for the Noise view (B10g)."""

from __future__ import annotations

import types

import numpy as np
import pytest

from myocard_egm_studio.view_model import noise as noise_mod
from myocard_egm_studio.view_model.noise import load_noise_bank


def _stub(n: int) -> types.SimpleNamespace:
    """A read_noise_bank_hdf5 stand-in with ``n`` zero-signal segments (like the metadata test)."""
    return types.SimpleNamespace(
        fs_hz=1000.0,
        source="iafdb",
        traces=types.SimpleNamespace(
            signal=[[0.0] * 32 for _ in range(n)],
            source_record=[f"rec{i}" for i in range(n)],
            source_channel=[f"c{i}" for i in range(n)],
        ),
    )


def test_load_noise_bank_returns_every_segment_with_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(noise_mod, "read_noise_bank_hdf5", lambda _p: _stub(40))
    bank = load_noise_bank("nbank.h5")
    assert len(bank.segments) == 40  # the whole bank, no cap (unlike the viewer sample)
    assert bank.fs_hz == 1000.0
    assert bank.source == "iafdb"
    seg = bank.segments[7]
    assert seg.index == 7  # its position in the bank
    assert seg.source_record == "rec7"
    assert seg.source_channel == "c7"
    assert seg.signal.dtype == np.float64


def test_load_noise_bank_exposes_sorted_distinct_filter_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dup = types.SimpleNamespace(
        fs_hz=500.0,
        source="iafdb",
        traces=types.SimpleNamespace(
            signal=[[0.0] * 8 for _ in range(4)],
            source_record=["rec_b", "rec_a", "rec_b", "rec_a"],  # repeats across segments
            source_channel=["c2", "c1", "c1", "c2"],
        ),
    )
    monkeypatch.setattr(noise_mod, "read_noise_bank_hdf5", lambda _p: dup)
    bank = load_noise_bank("nbank.h5")
    assert bank.records() == ["rec_a", "rec_b"]  # deduped + sorted, for the record filter
    assert bank.channels() == ["c1", "c2"]  # deduped + sorted, for the channel filter
