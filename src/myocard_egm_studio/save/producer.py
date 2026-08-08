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
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from myocard_egm_contracts import Role, role_of
from myocard_egm_data.banks import (
    ClassifierBank,
    check_noise_bank_id_agreement,
    load_classifier_bank,
    read_noise_bank_hdf5,
)
from myocard_egm_data.phases import EgmBankEntry, ModelEntry, NoiseBankEntry, TrainingRunEntry
from myocard_egm_data.records import load_training_run_record

from myocard_egm_studio.save.phase_storage import copy_into_phase, phase_relative
from myocard_egm_studio.view_model.builder import ProgressFn
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
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Place ``path`` for indexing: copied into ``phase_dir`` when there is one (B17).

    ``phase_dir=None`` is the scratch case — scratch is a working area, not an archive, so
    an artifact stays where the producer left it and the entry points at it absolutely.
    Nothing is copied, so ``progress`` / ``cancelled`` are never called on that path.
    """
    if phase_dir is None:
        return Path(path)
    return copy_into_phase(
        path,
        phase_dir,
        role_of(artifact_id).name,
        companions=companions,
        progress=progress,
        cancelled=cancelled,
    )


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
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """The entry preamble: id + path. Provenance is left unset, not invented (B19).

    ``produced_by_*`` are optional as of egm-contracts v0.6.0. A curator-indexed file
    records no producing package or version, so omitting them says "unknown" honestly,
    where the old ``"unknown"`` / ``"0"`` sentinels looked like recorded facts.
    """
    stored = store(
        path, artifact_id, phase_dir, companions=companions, progress=progress, cancelled=cancelled
    )
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
    path: Path | str,
    *,
    phase_dir: Path | str | None = None,
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> EgmBankEntry | NoiseBankEntry:
    """A manifest entry for a loaded bank — a NoiseBankEntry for ``nbank_`` ids, else EgmBank."""
    bank = load_classifier_bank(path)
    bank_id = bank.id
    if not bank_id:
        raise ValueError(
            f"bank {Path(path).name} has no stable id; cannot index it. If it predates stable "
            "ids, re-generate it with the current pipeline."
        )
    base = _base(
        bank_id,
        path,
        phase_dir,
        companions=declared_companions(bank, path),
        progress=progress,
        cancelled=cancelled,
    )
    if role_of(bank_id) is Role.noise_bank:
        return NoiseBankEntry.model_validate(base)
    return EgmBankEntry.model_validate(base)


def run_entry(
    path: Path | str,
    *,
    phase_dir: Path | str | None = None,
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> TrainingRunEntry:
    """A manifest entry for a loaded training run — carries its ``trained_on_bank`` dependency.

    A file that will not parse as a run record is reported as *that*, in one sentence. The
    common cause is a mis-pick: a **noise bank's** sidecar is also named ``..._run_record.json``
    (FB-26), so it lands here easily, and letting the schema's validation errors through
    produces a wall of complaints about a file that was never a training run.
    """
    try:
        record = load_training_run_record(path)
    except Exception as exc:
        raise ValueError(
            f"{Path(path).name} could not be read as a training-run record. If it is a noise "
            "bank's sidecar (also named ..._run_record.json), index the noise bank's .h5 "
            "instead — Add to phase ▸ Noise bank…"
        ) from exc
    if not record.run_id:
        raise ValueError(f"training run {Path(path).name} has no run_id; cannot index it")
    return TrainingRunEntry.model_validate(
        {
            **_base(record.run_id, path, phase_dir, progress=progress, cancelled=cancelled),
            "trained_on_bank": record.trained_on_bank_id,
            "produced_model": record.produced_model_id,
        }
    )


def model_entry(
    path: Path | str,
    *,
    phase_dir: Path | str | None = None,
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ModelEntry:
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
    base = _base(str(model_id), path, phase_dir, progress=progress, cancelled=cancelled)
    provenance = data.get("training_provenance")
    run_id = provenance.get("run_id") if isinstance(provenance, dict) else None
    if run_id:
        base["trained_from_run"] = str(run_id)
    return ModelEntry.model_validate(base)


#: How the noise-bank exporter names the run-record sidecar (iafdb convention): the ``.h5``'s
#: stem + this suffix, in the same folder — e.g. ``foo_noise.h5`` -> ``foo_noise_run_record.json``.
#: Only a *fallback* id source since B20; see :func:`noise_bank_entry`. A rename upstream needs a
#: matching change here or the sidecar stops travelling into phases (backlog FB-26).
_NOISE_RECORD_SUFFIX = "_run_record.json"


def _record_bank_id(h5: Path) -> str | None:
    """The ``bank_id`` in the ``.h5``'s sibling run record, or ``None`` if there isn't one.

    Read as raw JSON rather than through the typed loader so a sidecar at an older schema
    version still yields the one field wanted here.
    """
    record = h5.with_name(h5.stem + _NOISE_RECORD_SUFFIX)
    if not record.exists():
        return None
    value = _read_json(record).get("bank_id")
    return str(value) if value else None


def noise_bank_entry(
    path: Path | str,
    *,
    phase_dir: Path | str | None = None,
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> NoiseBankEntry:
    """A manifest entry for a noise-bank ``.h5`` (its segments).

    The id comes from the bank's **own** ``bank_id`` root attr (``noise_bank`` 1.1, B20) — an
    artifact should carry its own identity rather than borrow a neighbour's. Before that attr
    existed the only copy lived in the sibling ``<stem>_run_record.json``, so that is still read
    as a fallback, and when both are present egm-data checks they **agree**: a bank sitting
    beside someone else's run record reads as provenance while describing different data, which
    is worse than having none.

    The entry points at the ``.h5`` (matching produced entries), so the segment and metadata
    viewers — which read the ``.h5`` — work.
    """
    h5 = Path(path)
    bank_id = read_noise_bank_hdf5(h5).bank_id
    record_id = _record_bank_id(h5)
    check_noise_bank_id_agreement(bank_id, record_id)
    resolved = bank_id or record_id
    if not resolved:
        raise ValueError(
            f"noise bank {h5.name} carries no bank_id, and no sibling run record "
            f"({h5.stem + _NOISE_RECORD_SUFFIX}) supplies one; cannot index it. "
            "Re-generate it with the current pipeline, which stamps the id on the bank itself."
        )
    return NoiseBankEntry.model_validate(  # entry points at the .h5
        _base(resolved, h5, phase_dir, progress=progress, cancelled=cancelled)
    )
