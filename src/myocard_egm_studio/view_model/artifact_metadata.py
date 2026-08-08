"""File-level metadata for a phase artifact — the "Show metadata" content (Block 6).

The right-click "Show metadata" reads an artifact's *actual file* (not its manifest
pointer) and renders a per-type summary. Structured reads route through egm-data
(architecture invariant #1); the lone exception is the model-metadata sidecar, shown as
raw JSON so the view tolerates schema-version drift. Tiers:

- **EGM banks** (the four bank roles) -> a curated :class:`ClassifierBank` summary:
  trace count, sample rate, labels + their distribution, splits, and each source
  bank's free ``bank_metadata`` dict (this is where synthetic vs IAFDB banks differ).
- **Noise banks** -> the slim noise-bank header (source, rate, segment count).
- **Runs / figures / observations** -> the validated record, pretty-printed as JSON.
- **Models** -> the model-metadata sidecar JSON, shown as-is (read directly, not via the
  typed loader, so it tolerates versions the loader would reject — a display, not an
  interpretation; matches ``save.producer.model_entry``).

Papers (directories) have no cheap file view and are intentionally absent here — their
menu offers Reveal file + Copy id only.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from myocard_egm_contracts import Role
from myocard_egm_data.banks import (
    ClassifierBank,
    load_classifier_bank,
    read_noise_bank_hdf5,
    read_synthetic_bank_hdf5,
    simulation_configs,
)
from myocard_egm_data.phases import load_figure_spec, load_observation
from myocard_egm_data.records import load_training_run_record

from myocard_egm_studio.view_model.theta import (
    THETA_PREFIXES,
    declared_knob_paths,
    theta_companion_ref,
)


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
    lines.extend(_generation_config_lines(bank, path))
    return "\n".join(lines)


def _generation_config_lines(bank: ClassifierBank, path: Path) -> list[str]:
    """The per-simulation generation config, read from the θ companion.

    The ClassifierBank itself carries only five thin bank-level keys under
    ``synthetic_bank`` 2.0 — the generation physics moved to the parallel bank — so the
    interesting provenance is one file away. Rendering it here is what makes "Show
    metadata" still answer *how was this generated?* after the restructure.

    A bank with no companion contributes nothing (the IAFDB case). A companion that is
    declared but unreadable degrades to a one-line note rather than raising: this is a
    read-only inspector, and failing to open it should not stop the rest of the summary
    from being shown.
    """
    try:
        ref = theta_companion_ref(bank, bank_path=path)
        if ref is None:
            return []
        companion = read_synthetic_bank_hdf5(ref.path)
    except (OSError, ValueError) as exc:
        return ["", f"generation config: unavailable ({exc})"]

    configs = simulation_configs(companion)
    lines = ["", f"generation config ({len(configs)} simulation(s)):"]

    knobs = declared_knob_paths(companion)
    lines.append(f"  θ-spec knobs: {', '.join(knobs) if knobs else '(none declared)'}")

    for simulation_id in sorted(configs):
        simulation = configs[simulation_id]
        lines.append(f"  • simulation {simulation_id}  (seed {simulation.seed})")
        for function in (*THETA_PREFIXES, "label_policy"):
            obj = getattr(simulation, function, None)
            if obj is None:
                continue
            lines.extend(_nested(function, obj, indent=6))
    return lines


def _nested(name: str, obj: object, *, indent: int) -> list[str]:
    """``name`` and its fields as indented lines, recursing into nested structures.

    The per-function objects are typed contracts models rather than dicts, and a flat
    ``json.dumps`` of one is a single unreadable line — which is what this replaces. The
    ``type`` discriminator is pulled onto the header, since it names the variant and
    reading it first is what makes the rest of the block interpretable.
    """
    fields = _as_mapping(obj)
    pad = " " * indent
    variant = fields.pop("type", None) if isinstance(fields, dict) else None
    header = f"{pad}{name}" + (f"  [{variant}]" if variant is not None else "")
    lines = [header]
    for key, value in fields.items():
        if isinstance(value, dict):
            lines.extend(_nested(key, value, indent=indent + 2))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # e.g. electrodes.pairs — summarise rather than print N objects.
            lines.append(f"{pad}  {key}: {len(value)} entries")
        else:
            lines.append(f"{pad}  {key}: {_render(value)}")
    return lines


def _as_mapping(obj: object) -> dict[str, Any]:
    """A typed contracts model (or plain dict) as a plain mapping."""
    if isinstance(obj, dict):
        return dict(obj)
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        result: dict[str, Any] = dump()
        return result
    return {}


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


def _model_json(path: Path) -> str:
    """The model-metadata sidecar, shown as-is. Model-metadata schema versions drift and this
    is a display (not an interpretation), so it reads the JSON directly + pretty-prints it —
    tolerating versions the typed loader would reject (matches ``save.producer.model_entry``)."""
    return json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2, default=str)


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
    Role.model: _model_json,
}
