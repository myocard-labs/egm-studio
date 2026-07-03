"""Open data files into view-ready structures for the GUI (Block 5+).

egm-studio's direct-open path: read a ClassifierBank via egm-data and adapt it for
the GUI — the per-trace view-model table the filter / result list bind to
(:func:`load_view_model`, :func:`load_exploration`) and the per-trace display data
the detail view draws (:func:`traces_from_bank`, :func:`load_traces`). All reads go
through egm-data readers, never raw file I/O (ADR-001).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from myocard_egm_data.banks import ClassifierBank, load_classifier_bank

from myocard_egm_studio.gui.widgets import TraceData
from myocard_egm_studio.view_model import build_view_model

# Electrode-ish metadata keys (preference order) + how they read in a plot title.
_ELECTRODE_PREFIX = {"source_channel": "ch", "pair_index": "pair", "electrode_pair_id": "pair"}


def load_view_model(path: str | Path, *, source: str | None = None) -> pd.DataFrame:
    """Load a ClassifierBank and build its per-trace view-model DataFrame.

    The GUI's entry to the feature + metadata table the Block 7 filter / result
    list bind to: one row per trace; columns are ``source`` + identity + the
    producer's metadata keys + the 11 egm-features (see ``view_model.builder``).
    ``source`` labels the bank as a constant column — defaults to the bank's stable
    id, else the file stem — uniform for a single bank and the axis multi-bank
    loading (B7.8) will vary and filter on.
    """
    bank = load_classifier_bank(path)
    label = source or bank.id or Path(path).stem
    return build_view_model(bank, source=label)


def load_exploration(
    path: str | Path, *, source: str | None = None
) -> tuple[pd.DataFrame, list[TraceData]]:
    """Load a bank once as both the view-model table and its display traces.

    The Flow A entry (B7.5): reads the ClassifierBank a single time and returns the
    per-trace view-model DataFrame (the filter / result list bind to it) plus the
    per-trace display data indexed by ``trace_idx`` (the detail view resolves a
    selected row's ``trace_idx`` into its waveform). ``source`` defaults as in
    :func:`load_view_model`.
    """
    bank = load_classifier_bank(path)
    label = source or bank.id or Path(path).stem
    return build_view_model(bank, source=label), traces_from_bank(bank)


def traces_from_bank(bank: ClassifierBank, *, limit: int | None = None) -> list[TraceData]:
    """The per-trace display data of a bank (the first ``limit`` if given)."""
    data = [
        TraceData(
            signal=np.asarray(trace.signal, dtype=np.float64),
            fs_hz=float(trace.freq_hz),
            label=_title({k: str(v) for k, v in (trace.trace_metadata or {}).items()}, index),
        )
        for index, trace in enumerate(bank.traces)
    ]
    return data if limit is None else data[:limit]


def load_traces(path: str | Path, *, limit: int | None = None) -> list[TraceData]:
    """Load a bank and return its traces' display data (the first ``limit`` if given)."""
    return traces_from_bank(load_classifier_bank(path), limit=limit)


def _title(fields: dict[str, str], index: int) -> str:
    """A compact per-tile title, e.g. ``P03 · ch 5`` or ``pair 1``."""
    patient = fields.get("patient_id")
    electrode = None
    for key, prefix in _ELECTRODE_PREFIX.items():
        value = fields.get(key)
        if value:
            electrode = f"{prefix} {value}"
            break
    parts = [part for part in (patient, electrode) if part]
    return " · ".join(parts) if parts else f"trace {index}"
