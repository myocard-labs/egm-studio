"""Build a producer-artifact manifest entry from a loaded bank / run file (Block 10h-2b).

egm-studio indexes producer artifacts (banks, runs) it did not create. Under B17 the file is
**copied into the phase folder** and the entry records a path relative to it, so the phase
is self-contained and movable (see ``save.phase_storage``); an artifact left outside keeps
an absolute pointer. A bank's declared companions — the θ bank, the noise bank it was mixed
with — travel with it, since it names them by paths resolved beside itself.

Provenance is **omitted** rather than stamped. The artifact files record no producing
package or version, and egm-contracts v0.6.0 made ``produced_by_package`` /
``produced_by_version`` optional (B19), so the entry simply leaves them unset. Previously
they carried ``"unknown"`` / ``"0"`` sentinels, which read as a *claim* about provenance
rather than an absence of one.

Ids come from the file — a bank's ``.id``, a run's ``run_id`` — and a run also carries its
``trained_on_bank`` dependency.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from myocard_egm_contracts import Role, role_of
from myocard_egm_data.banks import ClassifierBank, load_classifier_bank
from myocard_egm_data.phases import EgmBankEntry, ModelEntry, NoiseBankEntry, TrainingRunEntry
from myocard_egm_data.records import load_training_run_record

from myocard_egm_studio.save.phase_storage import copy_into_phase, phase_relative
from myocard_egm_studio.view_model.theta import LOCAL_SENTINEL

__all__ = [
    "bank_entry",
    "declared_companions",
    "model_entry",
    "noise_bank_entry",
    "run_entry",
]


def store(
    path: Path | str,
    artifact_id: str,
    phase_dir: Path | str | None,
    *,
    companions: Iterable[Path | str] = (),
) -> Path:
    """Place ``path`` for indexing: copied into ``phase_dir`` when there is one (B17).

    ``phase_dir=None`` is the scratch case — scratch is a working area, not an archive, so
    an artifact stays where the producer left it and the entry points at it absolutely.
    """
    if phase_dir is None:
        return Path(path)
    return copy_into_phase(path, phase_dir, role_of(artifact_id).name, companions=companions)


def declared_companions(bank: ClassifierBank, path: Path | str) -> tuple[Path, ...]:
    """Files ``bank`` points at with a *relative* path, resolved beside it.

    A synthetic ClassifierBank names its sources in ``banks[]``: the θ companion it is keyed
    to by ``simulation_id``, and the noise bank it was mixed with. Those are bare filenames
    resolved beside the ``.h5``, so copying the bank into a phase on its own leaves them
    dangling — the phase would hold a bank whose θ cannot be found, which is exactly the
    self-containment B17 exists to guarantee.

    Two entries are skipped. ``<local>`` is the "this is the bank you already have" sentinel,
    not a path. An **absolute** path names something that deliberately lives elsewhere; it
    resolves from anywhere already, and copying it in would be a decision this function is
    not entitled to make.
    """
    beside = Path(path).parent
    return tuple(
        beside / raw
        for entry in bank.banks
        if (raw := (entry.bank_path or "").strip())
        and raw != LOCAL_SENTINEL
        and not Path(raw).is_absolute()
    )


def _base(
    artifact_id: str,
    path: Path | str,
    phase_dir: Path | str | None = None,
    *,
    companions: Iterable[Path | str] = (),
) -> dict[str, str]:
    """The entry preamble: id + path. Provenance is left unset, not invented (B19).

    ``produced_by_*`` are optional as of egm-contracts v0.6.0. A curator-indexed file
    records no producing package or version, so omitting them says "unknown" honestly,
    where the old ``"unknown"`` / ``"0"`` sentinels looked like recorded facts.
    """
    stored = store(path, artifact_id, phase_dir, companions=companions)
    recorded = phase_relative(stored, Path(phase_dir)) if phase_dir is not None else str(stored)
    return {"id": artifact_id, "path": recorded}


def _read_json(path: Path | str) -> dict[str, Any]:
    """Load a JSON record's top-level object. Curator id-reads go through here rather than the
    typed loaders, so they tolerate schema-version drift (we only need the stable id fields)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def bank_entry(
    path: Path | str, *, phase_dir: Path | str | None = None
) -> EgmBankEntry | NoiseBankEntry:
    """A manifest entry for a loaded bank — a NoiseBankEntry for ``nbank_`` ids, else EgmBank."""
    bank = load_classifier_bank(path)
    bank_id = bank.id
    if not bank_id:
        raise ValueError(f"bank at {path} has no stable id; cannot index it")
    base = _base(bank_id, path, phase_dir, companions=declared_companions(bank, path))
    if role_of(bank_id) is Role.noise_bank:
        return NoiseBankEntry.model_validate(base)
    return EgmBankEntry.model_validate(base)


def run_entry(path: Path | str, *, phase_dir: Path | str | None = None) -> TrainingRunEntry:
    """A manifest entry for a loaded training run — carries its ``trained_on_bank`` dependency."""
    record = load_training_run_record(path)
    if not record.run_id:
        raise ValueError(f"training run at {path} has no run_id; cannot index it")
    return TrainingRunEntry.model_validate(
        {
            **_base(record.run_id, path, phase_dir),
            "trained_on_bank": record.trained_on_bank_id,
            "produced_model": record.produced_model_id,
        }
    )


def model_entry(path: Path | str, *, phase_dir: Path | str | None = None) -> ModelEntry:
    """A manifest entry for a model-metadata JSON — carries its ``trained_from_run`` dependency.

    Reads ``model_id`` (+ the run id, if any) straight from the JSON rather than the strict
    typed loader, so a curator can index a model across model-metadata schema versions. The
    producing run id lives in the open-ended ``training_provenance`` block under the well-known
    ``run_id`` key (egm-classifier v0.4.0+); it may be absent, in which case ``trained_from_run``
    is left unset. A missing ``model_id`` is an error — the artifact must carry its own id.
    """
    data = _read_json(path)
    model_id = data.get("model_id")
    if not model_id:
        raise ValueError(f"model metadata at {path} has no model_id; cannot index it")
    base = _base(str(model_id), path, phase_dir)
    provenance = data.get("training_provenance")
    run_id = provenance.get("run_id") if isinstance(provenance, dict) else None
    if run_id:
        base["trained_from_run"] = str(run_id)
    return ModelEntry.model_validate(base)


#: How the noise-bank exporter names the run-record sidecar (iafdb convention): the ``.h5``'s
#: stem + this suffix, in the same folder — e.g. ``foo_noise.h5`` -> ``foo_noise_run_record.json``.
_NOISE_RECORD_SUFFIX = "_run_record.json"


def noise_bank_entry(path: Path | str, *, phase_dir: Path | str | None = None) -> NoiseBankEntry:
    """A manifest entry for a noise-bank ``.h5`` (its segments). The ``.h5`` carries no id, so the
    stable ``bank_id`` is read from its **sibling run record** — ``<stem>_run_record.json`` next to
    it (the iafdb export convention). The entry points at the ``.h5`` (matching produced entries),
    so the segment / metadata viewers, which read the ``.h5``, work. A missing sibling record or
    ``bank_id`` is an error.
    """
    h5 = Path(path)
    record = h5.with_name(h5.stem + _NOISE_RECORD_SUFFIX)
    if not record.exists():
        raise ValueError(
            f"noise bank {h5.name} has no sibling run record ({record.name}); cannot read its id"
        )
    bank_id = _read_json(record).get("bank_id")
    if not bank_id:
        raise ValueError(f"noise-bank record {record.name} has no bank_id; cannot index it")
    return NoiseBankEntry.model_validate(
        _base(str(bank_id), h5, phase_dir)
    )  # entry points at the .h5
