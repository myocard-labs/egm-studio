"""File-level metadata for a phase artifact — the "Show metadata" content (Block 6).

The right-click "Show metadata" reads an artifact's *actual file* (not its manifest
pointer) and renders a per-type summary. All reads go through egm-data — egm-studio
never opens an HDF5/JSON directly (architecture invariant #1). Three tiers:

- **EGM banks** (the four bank roles) -> a curated :class:`ClassifierBank` summary:
  trace count, sample rate, labels + their distribution, splits, and each source
  bank's free ``bank_metadata`` dict (this is where synthetic vs IAFDB banks differ).
- **Noise banks** -> the slim noise-bank header (source, rate, segment count).
- **Runs / figures / observations** -> the validated record, pretty-printed as JSON.

Models (``.pt`` checkpoints) and papers (directories) have no cheap file view and
are intentionally absent here — their menu offers Reveal file + Copy id only.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from myocard_egm_contracts import Role
from myocard_egm_data.banks import ClassifierBank, load_classifier_bank, read_noise_bank_hdf5
from myocard_egm_data.phases import load_figure_spec, load_observation
from myocard_egm_data.records import load_training_run_record


def has_metadata_view(role: Role) -> bool:
    """Whether this role's file can be summarized (drives the menu's Show metadata)."""
    return role in _READERS


def artifact_metadata_text(role: Role, path: Path | str) -> str:
    """A human-readable summary of the artifact's file, dispatched by role.

    Raises ``ValueError`` for a role with no file view (model / paper); the caller
    (the shell) wraps read errors — a missing or malformed file — into friendly text.
    """
    reader = _READERS.get(role)
    if reader is None:
        raise ValueError(f"No metadata view for role {role.value!r}.")
    return reader(Path(path))


# -- bank summary (the rich, per-source, synthetic-vs-IAFDB-aware view) -----------


def _classifier_summary(path: Path) -> str:
    bank = load_classifier_bank(path)
    lines = [
        f"id: {bank.id or '(untracked)'}",
        f"schema version: {bank.schema_version}",
        f"created: {bank.created_utc}",
        f"traces: {bank.n_traces}",
        f"sample rate: {_rate(bank)}",
        f"signal length: {_lengths(bank)}",
        f"amplitude: {', '.join(sorted({t.amp_type for t in bank.traces})) or 'n/a'}",
        f"labels: {_labels(bank)}",
        f"label counts: {_counts(_label_name(bank, t.label_truth) for t in bank.traces)}",
        f"splits: {_counts(t.split or 'unassigned' for t in bank.traces)}",
        f"predictions: {sum(t.prediction is not None for t in bank.traces)}/{bank.n_traces} traces",
        "",
        f"source banks ({len(bank.banks)}):",
    ]
    for meta in bank.banks:
        lines.append(f"  • {meta.bank_id}  [{meta.bank_type}]")
        for key, value in meta.bank_metadata.items():
            lines.append(f"      {key}: {_render(value)}")
    return "\n".join(lines)


def _rate(bank: ClassifierBank) -> str:
    try:
        return f"{bank.uniform_fs_hz():g} Hz"
    except ValueError:
        rates = sorted({float(t.freq_hz) for t in bank.traces})
        return f"mixed {rates} Hz"


def _lengths(bank: ClassifierBank) -> str:
    sizes = {int(t.signal.shape[0]) for t in bank.traces}
    if not sizes:
        return "n/a"
    if len(sizes) == 1:
        return f"{next(iter(sizes))} samples"
    return f"{min(sizes)}-{max(sizes)} samples (mixed)"


def _labels(bank: ClassifierBank) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(bank.labels.items())) if bank.labels else "n/a"


def _label_name(bank: ClassifierBank, label: int | None) -> str:
    if label is None:
        return "unlabeled"
    return bank.labels.get(label, str(label))


# -- noise-bank header ------------------------------------------------------------


def _noise_summary(path: Path) -> str:
    bank = read_noise_bank_hdf5(path)
    signals = bank.traces.signal
    records = sorted(set(bank.traces.source_record))
    channels = sorted(set(bank.traces.source_channel))
    return "\n".join(
        [
            f"schema version: {bank.schema_version}",
            f"created: {bank.created_utc}",
            f"source: {bank.source}",
            f"sample rate: {bank.fs_hz:g} Hz",
            f"segments: {len(signals)}",
            f"segment length: {len(signals[0]) if signals else 0} samples",
            f"source records ({len(records)}): {_preview(records, 8)}",
            f"source channels ({len(channels)}): {_preview(channels, 12)}",
        ]
    )


# -- JSON records (run / figure / observation) ------------------------------------


def _as_json(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json", exclude_none=True), indent=2, default=str)


def _run_json(path: Path) -> str:
    return _as_json(load_training_run_record(path))


def _figure_json(path: Path) -> str:
    return _as_json(load_figure_spec(path))


def _observation_json(path: Path) -> str:
    return _as_json(load_observation(path))


# -- shared helpers ---------------------------------------------------------------


def _counts(values: Iterable[Any]) -> str:
    counter = Counter(values)
    return ", ".join(f"{key}: {n}" for key, n in sorted(counter.items(), key=lambda kv: str(kv[0])))


def _render(value: Any) -> str:
    return json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)


def _preview(values: list[str], limit: int) -> str:
    shown = ", ".join(values[:limit])
    return f"{shown} …" if len(values) > limit else shown


# Role -> file reader. Its keys are the roles that get "Show metadata" — kept in
# sync with phase_actions._METADATA_ROLES by test_metadata_roles_match.
_READERS: dict[Role, Callable[[Path], str]] = {
    Role.training_bank: _classifier_summary,
    Role.pretraining_bank: _classifier_summary,
    Role.labeled_prediction_bank: _classifier_summary,
    Role.unlabeled_prediction_bank: _classifier_summary,
    Role.noise_bank: _noise_summary,
    Role.training_run: _run_json,
    Role.figure: _figure_json,
    Role.observation: _observation_json,
}
