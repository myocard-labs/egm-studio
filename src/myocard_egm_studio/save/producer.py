"""Build a producer-artifact manifest entry from a loaded bank / run file (Block 10h-2b).

egm-studio indexes producer artifacts (banks, runs) it did not create — it only points at
them (ADR-021), so these entries are absolute path *pointers*, not copies. The producing
package / version is not recorded in the artifact files today, so a curator-indexed entry
stamps a sentinel provenance (``"unknown"``); making ``produced_by`` optional is a deferred
egm-contracts change (refactor-cleanup batch). Ids come from the file — a bank's ``.id``, a
run's ``run_id`` — and a run also carries its ``trained_on_bank`` dependency.
"""

from __future__ import annotations

from pathlib import Path

from myocard_egm_contracts import Role, role_of
from myocard_egm_data.banks import load_classifier_bank
from myocard_egm_data.phases import EgmBankEntry, NoiseBankEntry, TrainingRunEntry
from myocard_egm_data.records import load_training_run_record

#: Provenance stamped on a curator-indexed producer artifact, whose file records no
#: producing package/version. Deferred egm-contracts change: make ``produced_by`` optional.
UNKNOWN_PRODUCER = "unknown"
UNKNOWN_VERSION = "0"

__all__ = ["UNKNOWN_PRODUCER", "UNKNOWN_VERSION", "bank_entry", "run_entry"]


def _base(artifact_id: str, path: Path | str) -> dict[str, str]:
    """The pointer-entry preamble: id + an absolute path outside the phase + sentinel provenance."""
    return {
        "id": artifact_id,
        "path": str(path),
        "produced_by_package": UNKNOWN_PRODUCER,
        "produced_by_version": UNKNOWN_VERSION,
    }


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
