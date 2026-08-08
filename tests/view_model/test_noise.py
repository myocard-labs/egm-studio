"""Tests for view_model.noise — a noise bank's segments prepared for the Noise view (B10g)."""

from __future__ import annotations

import types

import numpy as np
import pytest

from myocard_egm_studio.view_model import noise as noise_mod
from myocard_egm_studio.view_model.noise import load_noise_bank


def _stub(n: int, *, bank_id: str | None = "nbank_fixture_2026-06-15") -> types.SimpleNamespace:
    """A read_noise_bank_hdf5 stand-in with ``n`` zero-signal segments (like the metadata test)."""
    return types.SimpleNamespace(
        bank_id=bank_id,
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


def test_the_bank_carries_its_own_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """B20: ``noise_bank`` 1.1 stamps ``bank_id`` on the bank, so the view isn't told what it has."""
    monkeypatch.setattr(noise_mod, "read_noise_bank_hdf5", lambda _p: _stub(2))
    assert load_noise_bank("nbank.h5").bank_id == "nbank_fixture_2026-06-15"


def test_a_pre_b20_bank_reports_no_id_rather_than_guessing(monkeypatch: pytest.MonkeyPatch) -> None:
    """``None`` is the honest answer — it lets the caller fall back, where a made-up id would not."""
    monkeypatch.setattr(noise_mod, "read_noise_bank_hdf5", lambda _p: _stub(2, bank_id=None))
    assert load_noise_bank("nbank.h5").bank_id is None


def test_load_noise_bank_exposes_sorted_distinct_filter_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dup = types.SimpleNamespace(
        bank_id="nbank_fixture_2026-06-15",
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
