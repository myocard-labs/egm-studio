"""Artifact existence + format status for the Phase tree (Block 6).

Resolves each manifest entry's path against a base dir (relative by default;
an absolute path wins) and reports a status the tree colours:

- ``MISSING`` — the file is not there.
- ``PRESENT`` — the file exists but has not been format-validated yet; this is
  the state after the cheap on-load existence pass.
- ``OK`` — validated: it passed its egm-contracts schema, or its type has no
  file validator so existence is all there is to check.
- ``INVALID`` — present but fails its egm-contracts schema validator.

Existence is cheap, so it runs eagerly when a phase loads (PRESENT / MISSING);
format validation opens the file and only runs when the user triggers it, turning
PRESENT into OK or INVALID. Only the JSON-schema artifact types (runs, figures,
observations) have a file validator here; banks, models, and papers fall back to
an existence check.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from pathlib import Path

from myocard_egm_contracts import (
    Role,
    role_of,
    validate_figure_spec,
    validate_observation,
    validate_training_run_record,
)
from myocard_egm_data.phases import (
    EgmBankEntry,
    FigureEntry,
    ModelEntry,
    NoiseBankEntry,
    ObservationEntry,
    PaperEntry,
    PhaseManifest,
    TrainingRunEntry,
)

_Entry = (
    EgmBankEntry
    | NoiseBankEntry
    | TrainingRunEntry
    | ModelEntry
    | ObservationEntry
    | FigureEntry
    | PaperEntry
)


class ArtifactStatus(Enum):
    """Existence / format state of one manifest artifact."""

    OK = "ok"
    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"


# Roles whose file has an egm-contracts schema validator (path -> ValidationResult).
# Banks / models / papers have none here, so their check is existence only for now.
_VALIDATORS = {
    Role.training_run: validate_training_run_record,
    Role.figure: validate_figure_spec,
    Role.observation: validate_observation,
}


def resolve_path(base_dir: Path | str, path: str) -> Path:
    """Resolve a manifest ``path`` against ``base_dir``; an absolute ``path`` wins."""
    return Path(base_dir) / path


def _all_entries(manifest: PhaseManifest) -> Iterator[_Entry]:
    for section in (
        manifest.egm_banks,
        manifest.noise_banks,
        manifest.training_runs,
        manifest.models,
        manifest.observations,
        manifest.figures,
        manifest.papers,
    ):
        yield from section or ()


def artifact_status(base_dir: Path | str, entry: _Entry, *, validate: bool) -> ArtifactStatus:
    """One artifact's status. Absent file -> MISSING. Present but not yet validated
    -> PRESENT. When ``validate`` is set, a present file resolves to OK (it passed,
    or its type has no validator) or INVALID (it failed its schema)."""
    resolved = resolve_path(base_dir, entry.path)
    if not resolved.exists():
        return ArtifactStatus.MISSING
    if not validate:
        return ArtifactStatus.PRESENT
    validator = _VALIDATORS.get(role_of(entry.id))
    if validator is None:
        return ArtifactStatus.OK
    return ArtifactStatus.OK if validator(resolved).ok else ArtifactStatus.INVALID


def phase_statuses(
    manifest: PhaseManifest, base_dir: Path | str, *, validate: bool = False
) -> dict[str, ArtifactStatus]:
    """Every artifact id -> its status. ``validate=False`` is the cheap on-load
    existence pass (PRESENT / MISSING); ``validate=True`` also runs the per-type
    format validation, resolving PRESENT into OK or INVALID."""
    return {e.id: artifact_status(base_dir, e, validate=validate) for e in _all_entries(manifest)}
