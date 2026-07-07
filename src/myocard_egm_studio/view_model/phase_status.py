"""Artifact existence + format status for the Phase tree (Block 6).

Resolves each manifest entry's path against a base dir (relative by default;
an absolute path wins) and reports a status the tree colours:

- ``MISSING`` — the file is not there.
- ``PRESENT`` — the file exists but has not been format-validated yet; this is
  the state after the cheap on-load existence pass.
- ``OK`` — validated: it passed its egm-contracts schema (or its type has no
  file validator) *and* every id it references is indexed in this phase.
- ``INVALID`` — present but fails its egm-contracts schema validator.
- ``UNRESOLVED`` — present + schema-valid, but a dependency id it references is not
  in the phase (e.g. an observation whose banks were never added). The tree paints
  this the same amber as INVALID; the two are told apart by the row's "why" tooltip.

Existence is cheap, so it runs eagerly when a phase loads (PRESENT / MISSING);
format validation opens the file and only runs when the user triggers it, turning
PRESENT into OK / INVALID / UNRESOLVED. The dependency check (:mod:`.dependencies`)
piggybacks on that validate pass — it too reads the observation file — so it only
runs on demand. Only the JSON-schema artifact types (runs, figures, observations)
have a file validator here; banks, models, and papers fall back to an existence
check (and a dependency check for derived banks / models).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
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
    load_observation,
)

from myocard_egm_studio.view_model.dependencies import dependency_ids, manifest_ids

_Entry = (
    EgmBankEntry
    | NoiseBankEntry
    | TrainingRunEntry
    | ModelEntry
    | ObservationEntry
    | FigureEntry
    | PaperEntry
)

#: How many schema issues to name in an INVALID row's "why" before trailing off.
_MAX_ISSUES = 3


class ArtifactStatus(Enum):
    """Existence / format state of one manifest artifact."""

    OK = "ok"
    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"
    UNRESOLVED = "unresolved"  # present + schema-valid, but a referenced id isn't in the phase


@dataclass(frozen=True)
class StatusReport:
    """An artifact's status plus a human "why" for the problem rows (empty when OK)."""

    status: ArtifactStatus
    detail: str = ""


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
    """One artifact's status (ignoring dependencies — see :func:`artifact_report`)."""
    return artifact_report(base_dir, entry, validate=validate, present_ids=None).status


def artifact_report(
    base_dir: Path | str,
    entry: _Entry,
    *,
    validate: bool,
    present_ids: set[str] | None,
) -> StatusReport:
    """One artifact's status + "why". Absent file -> MISSING; present-but-unchecked ->
    PRESENT. When ``validate`` is set, a present file resolves to INVALID (fails its schema)
    or, if it passes, to UNRESOLVED when ``present_ids`` is given and one of its dependency
    ids isn't in it — otherwise OK. ``present_ids`` is the set of ids the entry may resolve
    against (a phase's own ids; for a scratch item, scratch ids plus the loaded phase's)."""
    resolved = resolve_path(base_dir, entry.path)
    if not resolved.exists():
        return StatusReport(ArtifactStatus.MISSING, f"File not found: {entry.path}")
    if not validate:
        return StatusReport(ArtifactStatus.PRESENT, "Present — not yet validated (Validate phase)")
    validator = _VALIDATORS.get(role_of(entry.id))
    if validator is not None:
        result = validator(resolved)
        if not result.ok:
            return StatusReport(ArtifactStatus.INVALID, _issues_detail(result.issues))
    if present_ids is not None:
        missing = _missing_dependencies(entry, resolved, present_ids)
        if missing:
            return StatusReport(ArtifactStatus.UNRESOLVED, "Not indexed: " + ", ".join(missing))
    return StatusReport(ArtifactStatus.OK)


def _missing_dependencies(entry: _Entry, resolved: Path, present_ids: set[str]) -> list[str]:
    """The entry's dependency ids that aren't in ``present_ids`` (order preserved)."""
    observation = load_observation(resolved) if isinstance(entry, ObservationEntry) else None
    return [dep for dep in dependency_ids(entry, observation=observation) if dep not in present_ids]


def _issues_detail(issues: tuple[str, ...]) -> str:
    """A short 'why' for an INVALID row from its schema issues."""
    shown = "; ".join(issues[:_MAX_ISSUES])
    more = len(issues) - _MAX_ISSUES
    return f"Invalid: {shown}" + (f" (+{more} more)" if more > 0 else "")


def phase_status_report(
    manifest: PhaseManifest,
    base_dir: Path | str,
    *,
    validate: bool = False,
    extra_ids: set[str] | None = None,
) -> dict[str, StatusReport]:
    """Every artifact id -> its :class:`StatusReport` (status + "why"). ``validate=False`` is
    the cheap on-load existence pass; ``validate=True`` runs per-type format validation *and*
    the dependency check — each entry's referenced ids must resolve within ``manifest``'s own
    ids plus ``extra_ids``. A phase passes no ``extra_ids`` (it resolves against itself); the
    scratch area passes the loaded phase's ids, so scratch resolves against scratch + phase."""
    present_ids = (manifest_ids(manifest) | (extra_ids or set())) if validate else None
    return {
        e.id: artifact_report(base_dir, e, validate=validate, present_ids=present_ids)
        for e in _all_entries(manifest)
    }


def phase_statuses(
    manifest: PhaseManifest, base_dir: Path | str, *, validate: bool = False
) -> dict[str, ArtifactStatus]:
    """Every artifact id -> its status (the :func:`phase_status_report` status, sans "why")."""
    return {
        artifact_id: report.status
        for artifact_id, report in phase_status_report(
            manifest, base_dir, validate=validate
        ).items()
    }
