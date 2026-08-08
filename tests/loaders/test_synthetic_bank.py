"""Tests for loaders.synthetic_bank — locating a ClassifierBank's θ companion.

Discovery is by ``bank_type``, not by filename: the producer records the companion as an
extra ``banks`` entry, so the reference travels with the artifact. These build the entries
directly rather than reading a real bank — the artifacts are gitignored and cannot back a
CI suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from myocard_egm_data.banks import ClassifierBank, ClassifierBankMetaData, ClassifierTrace

from myocard_egm_studio.loaders.synthetic_bank import (
    load_theta_companion,
    swap_in_synthetic_signals,
)
from myocard_egm_studio.view_model.theta import THETA_BANK_TYPE, theta_companion_ref


def _entry(bank_id: str, bank_type: str, bank_path: str) -> ClassifierBankMetaData:
    return ClassifierBankMetaData(
        bank_id=bank_id, bank_type=bank_type, bank_path=bank_path, bank_metadata={}
    )


def _bank(*entries: ClassifierBankMetaData) -> ClassifierBank:
    trace = ClassifierTrace(
        bank_id=entries[0].bank_id,
        signal=np.zeros(8, dtype=np.float32),
        freq_hz=1000.0,
        amp_type="mv",
        split=None,
        label_truth=1,
        prediction=None,
        trace_metadata={"simulation_id": 0},
    )
    return ClassifierBank(
        id=entries[0].bank_id, banks=list(entries), traces=[trace], labels={1: "f"}
    )


def test_the_companion_is_found_by_bank_type_and_resolved_beside_the_bank() -> None:
    """A bare filename resolves next to the ClassifierBank, so moving the pair is safe."""
    bank = _bank(
        _entry("tbank_run", "synthetic_egm_pipeline", "<local>"),
        _entry("tbank_run_theta", THETA_BANK_TYPE, "run_theta.synthetic.h5"),
        _entry("nbank_noise", "mixer", "noise.h5"),
    )
    ref = theta_companion_ref(bank, bank_path=Path("/data/banks/run.classifier.h5"))
    assert ref is not None
    assert ref.bank_id == "tbank_run_theta"
    assert ref.path == Path("/data/banks/run_theta.synthetic.h5")


def test_a_bank_with_no_companion_entry_returns_none() -> None:
    """No θ side is a fact, not a failure — an IAFDB bank simply has no generation config."""
    bank = _bank(_entry("tbank_iafdb", "iafdb", "<local>"))
    assert theta_companion_ref(bank, bank_path=Path("/data/x.classifier.h5")) is None
    assert load_theta_companion(bank, bank_path=Path("/data/x.classifier.h5")) is None


def test_a_companion_entry_with_the_local_sentinel_raises() -> None:
    """``<local>`` means "the bank in hand" and is never a resolvable companion path."""
    bank = _bank(
        _entry("tbank_run", "synthetic_egm_pipeline", "<local>"),
        _entry("tbank_run_theta", THETA_BANK_TYPE, "<local>"),
    )
    with pytest.raises(ValueError, match="no usable path"):
        theta_companion_ref(bank, bank_path=Path("/data/run.classifier.h5"))


def test_a_declared_but_missing_companion_raises_rather_than_returning_none(
    tmp_path: Path,
) -> None:
    """Declared-but-broken must not collapse into "no θ", or an empty table reads as real."""
    bank = _bank(
        _entry("tbank_run", "synthetic_egm_pipeline", "<local>"),
        _entry("tbank_run_theta", THETA_BANK_TYPE, "absent_theta.synthetic.h5"),
    )
    with pytest.raises(FileNotFoundError, match="no file is there"):
        load_theta_companion(bank, bank_path=tmp_path / "run.classifier.h5")


# --- the synthetic signal source ------------------------------------------- #


class _Traces:
    def __init__(self, sim_ids: list[int], pairs: list[int], signals: list[np.ndarray]) -> None:
        self.simulation_id = sim_ids
        self.pair_index = pairs
        self.signal = signals


class _Companion:
    """Only what the swap reads: fs, and traces keyed by (simulation_id, pair_index)."""

    def __init__(
        self,
        sim_ids: list[int],
        pairs: list[int],
        signals: list[np.ndarray],
        *,
        fs_hz: float = 1000.0,
    ) -> None:
        self.fs_hz = fs_hz
        self.traces = _Traces(sim_ids, pairs, signals)


def _bank_with(keys: list[tuple[int, int]], *, fs_hz: float = 1000.0) -> ClassifierBank:
    traces = [
        ClassifierTrace(
            bank_id="tbank_run",
            signal=np.zeros(4, dtype=np.float32),
            freq_hz=fs_hz,
            amp_type="mv",
            split=None,
            label_truth=1,
            prediction=None,
            trace_metadata={"simulation_id": sim, "pair_index": pair},
        )
        for sim, pair in keys
    ]
    return ClassifierBank(
        id="tbank_run",
        banks=[_entry("tbank_run", "synthetic_egm_pipeline", "<local>")],
        traces=traces,
        labels={1: "f"},
    )


def test_the_swap_replaces_samples_and_keeps_everything_else() -> None:
    """Same rows, same labels, same metadata — only the waveform differs."""
    bank = _bank_with([(0, 0), (0, 1), (1, 0)])
    companion: Any = _Companion(
        sim_ids=[1, 0, 0],  # deliberately a different order than the bank
        pairs=[0, 1, 0],
        signals=[np.full(4, 3.0), np.full(4, 2.0), np.full(4, 1.0)],
    )

    swapped = swap_in_synthetic_signals(bank, companion)

    # Matched on (simulation_id, pair_index), not position — so order does not matter.
    assert [float(t.signal[0]) for t in swapped.traces] == [1.0, 2.0, 3.0]
    assert [t.label_truth for t in swapped.traces] == [1, 1, 1]
    assert [t.trace_metadata for t in swapped.traces] == [t.trace_metadata for t in bank.traces]


def test_a_sample_rate_mismatch_is_refused() -> None:
    """Swapping across rates silently changes every sample-indexed feature."""
    bank = _bank_with([(0, 0)], fs_hz=1000.0)
    companion: Any = _Companion([0], [0], [np.zeros(4)], fs_hz=500.0)

    with pytest.raises(ValueError, match="rate mismatch"):
        swap_in_synthetic_signals(bank, companion)


def test_a_trace_with_no_counterpart_is_refused() -> None:
    bank = _bank_with([(0, 0), (9, 9)])
    companion: Any = _Companion([0], [0], [np.zeros(4)])

    with pytest.raises(ValueError, match="no such trace"):
        swap_in_synthetic_signals(bank, companion)


def test_a_duplicate_key_on_the_companion_is_refused() -> None:
    """A non-unique (simulation_id, pair_index) would pair waveforms with the wrong row."""
    bank = _bank_with([(0, 0)])
    companion: Any = _Companion([0, 0], [0, 0], [np.zeros(4), np.ones(4)])

    with pytest.raises(ValueError, match="two traces keyed"):
        swap_in_synthetic_signals(bank, companion)
