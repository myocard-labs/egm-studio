"""Phase-artifact view-model — the Phase tree's ten display groups (Block 6).

A loaded phase manifest (egm-data :class:`PhaseManifest`) is projected into the
ten role-based display groups the right-rail Phase tree shows, each entry
flattened to a pointer row (id / path / producer + its relationship + usage
fields). Each artifact's role comes from egm-contracts' single-source vocabulary
(:func:`role_of` over the id prefix), so the four egm-bank roles fan out of the
manifest's single ``egm_banks`` list automatically; only the group *labels* and
*order* — a display concern — live here. Pure: no Qt; the Phase tree widget just
renders this.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from myocard_egm_contracts import Role, role_of
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

# Any of the seven manifest pointer models.
_Entry = (
    EgmBankEntry
    | NoiseBankEntry
    | TrainingRunEntry
    | ModelEntry
    | ObservationEntry
    | FigureEntry
    | PaperEntry
)

# The ten display groups, in pipeline order — one per Role. Labels + order live
# here (display); the id -> Role mapping stays in egm-contracts (role_of).
_GROUP_LABELS: tuple[tuple[Role, str], ...] = (
    (Role.training_bank, "Training banks"),
    (Role.pretraining_bank, "Pretraining banks"),
    (Role.labeled_prediction_bank, "Labeled prediction banks"),
    (Role.unlabeled_prediction_bank, "Unlabeled prediction banks"),
    (Role.noise_bank, "Noise banks"),
    (Role.training_run, "Training runs"),
    (Role.model, "Models"),
    (Role.observation, "Observations"),
    (Role.figure, "Figures"),
    (Role.paper, "Papers"),
)

# Core pointer fields rendered on their own; every other set field on an entry
# is a relationship / usage detail.
_CORE_FIELDS = frozenset({"id", "path", "produced_by_package", "produced_by_version"})


@dataclass(frozen=True)
class ArtifactRow:
    """One artifact's manifest pointer, flattened for display."""

    id: str
    path: str
    produced_by: str
    details: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ArtifactGroup:
    """One display group of the Phase tree (e.g. "Training banks")."""

    role: Role
    label: str
    rows: tuple[ArtifactRow, ...]

    @property
    def count(self) -> int:
        return len(self.rows)


def _humanize(field_name: str) -> str:
    return field_name.replace("_", " ").capitalize()


def _provenance(entry: _Entry) -> str:
    """Who produced the artifact, for display — ``"not recorded"`` when it is unstamped.

    ``produced_by_*`` became optional in egm-contracts v0.6.0 (B19), and a curator-indexed
    producer artifact carries neither: the files record no producing package or version, so
    ``save.producer`` omits the fields rather than stamping a sentinel. Read off the model
    rather than the dump, which drops absent fields entirely.
    """
    stamped = [part for part in (entry.produced_by_package, entry.produced_by_version) if part]
    return " ".join(stamped) or "not recorded"


def _row(entry: _Entry) -> ArtifactRow:
    # mode="json" renders enums (usage_tag), URLs, and id lists as plain strings.
    dumped = entry.model_dump(mode="json", exclude_none=True)
    details = tuple(
        (_humanize(name), ", ".join(map(str, value)) if isinstance(value, list) else str(value))
        for name, value in dumped.items()
        if name not in _CORE_FIELDS
    )
    return ArtifactRow(
        id=str(dumped["id"]),
        path=str(dumped["path"]),
        produced_by=_provenance(entry),
        details=details,
    )


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


def entries_by_id(manifest: PhaseManifest) -> dict[str, _Entry]:
    """Every artifact id -> its manifest pointer entry (for action dispatch)."""
    return {entry.id: entry for entry in _all_entries(manifest)}


def phase_artifact_groups(manifest: PhaseManifest) -> list[ArtifactGroup]:
    """The ten Phase-tree display groups for ``manifest``, in pipeline order.

    Every artifact is bucketed by its role (:func:`role_of` over the id prefix),
    so the four egm-bank roles split out of the single ``egm_banks`` list without
    a bespoke rule here. All ten groups are always returned (empty ones with
    ``count == 0``) so a phase's shape stays legible before every stage has
    produced something.
    """
    buckets: dict[Role, list[ArtifactRow]] = {role: [] for role, _label in _GROUP_LABELS}
    for entry in _all_entries(manifest):
        buckets[role_of(entry.id)].append(_row(entry))
    return [ArtifactGroup(role, label, tuple(buckets[role])) for role, label in _GROUP_LABELS]
