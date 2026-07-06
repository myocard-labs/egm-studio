"""Noise-bank segment display data — the Noise view (Block 10g).

A noise bank's ``.h5`` holds N extracted noise segments (raw signals + each one's source
record / channel). This prepares them as Qt-free display data for the Noise view (the
fourth top-level mode): an overview + filterable segment list over a full-height plot.
Reads route through egm-data's ``read_noise_bank_hdf5`` (architecture invariant #1) —
egm-studio never opens the HDF5 itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from myocard_egm_data.banks import read_noise_bank_hdf5
from numpy.typing import NDArray


@dataclass(frozen=True)
class NoiseSegment:
    """One noise segment: its position in the bank + provenance + the raw signal."""

    index: int
    source_record: str
    source_channel: str
    signal: NDArray[np.float64]


@dataclass(frozen=True)
class NoiseBankSegments:
    """A whole noise bank's segments prepared for the Noise view (Block 12).

    Holds *every* segment (the view filters + plots a selection); the stable ``bank_id`` is
    not here — the ``.h5`` carries none, so the caller supplies it from the manifest entry.
    """

    segments: tuple[NoiseSegment, ...]
    fs_hz: float
    source: str

    def records(self) -> list[str]:
        """The distinct source records, sorted (drives the view's record filter)."""
        return sorted({seg.source_record for seg in self.segments})

    def channels(self) -> list[str]:
        """The distinct source channels, sorted (drives the view's channel filter)."""
        return sorted({seg.source_channel for seg in self.segments})


def load_noise_bank(path: Path | str) -> NoiseBankSegments:
    """Load *all* of a noise bank's segments (from its ``.h5``) for the Noise view. Reading the
    whole bank is O(N) in segments; the shell runs it off the UI thread with a progress dialog."""
    bank = read_noise_bank_hdf5(path)
    records = list(bank.traces.source_record)
    channels = list(bank.traces.source_channel)
    signals = list(bank.traces.signal)
    segments = tuple(
        NoiseSegment(
            index=i,
            source_record=str(records[i]),
            source_channel=str(channels[i]),
            signal=np.asarray(signals[i], dtype=np.float64),
        )
        for i in range(len(signals))
    )
    return NoiseBankSegments(segments=segments, fs_hz=float(bank.fs_hz), source=str(bank.source))
