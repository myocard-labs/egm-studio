"""Open data files into view-ready structures for the GUI (Block 5).

egm-studio's direct-open path: read a bank via egm-data and adapt it to the
selector's :class:`LoadedBank` / :class:`BankTrace` (per-trace metadata fields +
display data). The curated display / filter fields per bank type live in
:mod:`..field_config`. This "open a loose file" capability complements
phase-manifest loading (Blocks 6+); it goes through egm-data readers, never raw
file I/O.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from myocard_egm_data.banks import ClassifierBank, load_classifier_bank

from myocard_egm_studio.gui.field_config import CLASS_FIELD
from myocard_egm_studio.gui.widgets import BankTrace, LoadedBank, TraceData
from myocard_egm_studio.view_model import build_view_model

# Electrode-ish metadata keys (preference order) + how they read in a plot title.
_ELECTRODE_PREFIX = {"source_channel": "ch", "pair_index": "pair", "electrode_pair_id": "pair"}


def load_bank(path: str | Path) -> LoadedBank:
    """Load a ClassifierBank from ``path`` and adapt it for the trace selector."""
    return loaded_bank(load_classifier_bank(path))


def load_view_model(path: str | Path, *, source: str | None = None) -> pd.DataFrame:
    """Load a ClassifierBank and build its per-trace view-model DataFrame.

    The GUI's entry to the feature + metadata table the Block 7 filter / result
    list bind to: one row per trace; columns are ``source`` + identity + the
    producer's metadata keys + the 11 egm-features (see ``view_model.builder``).
    ``source`` labels the bank as a constant column — defaults to the bank's
    stable id, else the file stem — uniform for a single bank and the axis
    multi-bank loading (B7.8) will vary and filter on.
    """
    bank = load_classifier_bank(path)
    label = source or bank.id or Path(path).stem
    return build_view_model(bank, source=label)


def loaded_bank(bank: ClassifierBank) -> LoadedBank:
    """Adapt a ClassifierBank to a LoadedBank (bank type + per-trace fields + data)."""
    bank_type = bank.banks[0].bank_type if bank.banks else "unknown"
    labels = bank.labels or {}
    traces: list[BankTrace] = []
    for index, trace in enumerate(bank.traces):
        fields = {key: str(value) for key, value in (trace.trace_metadata or {}).items()}
        fields[CLASS_FIELD] = (
            str(labels.get(trace.label_truth, "n/a")) if trace.label_truth is not None else "n/a"
        )
        data = TraceData(
            signal=np.asarray(trace.signal, dtype=np.float64),
            fs_hz=float(trace.freq_hz),
            label=_title(fields, index),
        )
        traces.append(BankTrace(index=index, fields=fields, data=data))
    return LoadedBank(bank_type=bank_type, traces=traces)


def traces_from_bank(bank: ClassifierBank, *, limit: int | None = None) -> list[TraceData]:
    """The display data of a bank's traces (the first ``limit`` if given)."""
    data = [bt.data for bt in loaded_bank(bank).traces]
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
