"""Build a producer-artifact manifest entry from a loaded bank / run file (Block 10h-2b).

egm-studio indexes producer artifacts (banks, runs) it did not create — it only points at
them (ADR-021), so these entries are absolute path *pointers*, not copies. The producing
package / version is not recorded in the artifact files today, so a curator-indexed entry
stamps a sentinel provenance (``"unknown"``); making ``produced_by`` optional is a deferred
egm-contracts change (refactor-cleanup batch). Ids come from the file — a bank's ``.id``, a
run's ``run_id`` — and a run also carries its ``trained_on_bank`` dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from myocard_egm_contracts import Role, role_of
from myocard_egm_data.banks import load_classifier_bank
from myocard_egm_data.phases import EgmBankEntry, ModelEntry, NoiseBankEntry, TrainingRunEntry
from myocard_egm_data.records import load_training_run_record

#: Provenance stamped on a curator-indexed producer artifact, whose file records no
#: producing package/version. Deferred egm-contracts change: make ``produced_by`` optional.
UNKNOWN_PRODUCER = "unknown"
UNKNOWN_VERSION = "0"

__all__ = [
    "UNKNOWN_PRODUCER",
    "UNKNOWN_VERSION",
    "bank_entry",
    "model_entry",
    "noise_bank_entry",
    "run_entry",
]


def _base(artifact_id: str, path: Path | str) -> dict[str, str]:
    """The pointer-entry preamble: id + an absolute path outside the phase + sentinel provenance."""
    return {
        "id": artifact_id,
        "path": str(path),
        "produced_by_package": UNKNOWN_PRODUCER,
        "produced_by_version": UNKNOWN_VERSION,
    }


def _read_json(path: Path | str) -> dict[str, Any]:
    """Load a JSON record's top-level object. Curator id-reads go through here rather than the
    typed loaders, so they tolerate schema-version drift (we only need the stable id fields)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def bank_entry(path: Path | str) -> EgmBankEntry | NoiseBankEntry:
    """A manifest entry for a loaded bank — a NoiseBankEntry for ``nbank_`` ids, else EgmBank."""
    bank_id = load_classifier_bank(path).id
    if not bank_id:
        raise ValueError(f"bank at {path} has no stable id; cannot index it")
    base = _base(bank_id, path)
    if role_of(bank_id) is Role.noise_bank:
        return NoiseBankEntry.model_validate(base)
    return EgmBankEntry.model_validate(base)


def run_entry(path: Path | str) -> TrainingRunEntry:
    """A manifest entry for a loaded training run — carries its ``trained_on_bank`` dependency."""
    record = load_training_run_record(path)
    if not record.run_id:
        raise ValueError(f"training run at {path} has no run_id; cannot index it")
    return TrainingRunEntry.model_validate(
        {
            **_base(record.run_id, path),
            "trained_on_bank": record.trained_on_bank_id,
            "produced_model": record.produced_model_id,
        }
    )


def model_entry(path: Path | str) -> ModelEntry:
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
    base = _base(str(model_id), path)
    provenance = data.get("training_provenance")
    run_id = provenance.get("run_id") if isinstance(provenance, dict) else None
    if run_id:
        base["trained_from_run"] = str(run_id)
    return ModelEntry.model_validate(base)


#: How the noise-bank exporter names the run-record sidecar (iafdb convention): the ``.h5``'s
#: stem + this suffix, in the same folder — e.g. ``foo_noise.h5`` -> ``foo_noise_run_record.json``.
_NOISE_RECORD_SUFFIX = "_run_record.json"


def noise_bank_entry(path: Path | str) -> NoiseBankEntry:
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
    return NoiseBankEntry.model_validate(_base(str(bank_id), h5))  # entry points at the .h5
