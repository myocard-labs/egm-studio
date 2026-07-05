"""What each phase artifact depends on — the ids it references (Block 10 curator).

One source of truth for "which other artifacts must be present for this one to resolve".
Used by dependency-aware phase verification (an entry whose referenced ids aren't in the
manifest is *unresolved*), by the auto-add-dependencies feature, and by cross-scope
resolution between the scratch area and a loaded phase.

Only **backward** references count as dependencies — what an artifact was made *from* or
*consumes*: a figure's ``consumes_*``, a run's ``trained_on_bank``, a model's
``trained_from_run``, a derived bank's ``source_bank`` / ``model``, a paper's ``figures``.
Forward outputs (a run's ``produced_model``) are not dependencies. Producer-artifact deps
live on the manifest entry; an observation's live inside its file (referenced parents /
models plus the banks in its ``view_state`` / ``traces``), so those take the loaded
:class:`Observation`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from myocard_egm_data.phases import (
    EgmBankEntry,
    FigureEntry,
    ModelEntry,
    NoiseBankEntry,
    Observation,
    ObservationEntry,
    PaperEntry,
    PhaseManifest,
    TrainingRunEntry,
)

__all__ = [
    "dependency_ids",
    "entry_dependency_ids",
    "manifest_ids",
    "observation_dependency_ids",
]

_Entry = (
    EgmBankEntry
    | NoiseBankEntry
    | TrainingRunEntry
    | ModelEntry
    | ObservationEntry
    | FigureEntry
    | PaperEntry
)


class _HasRoot(Protocol):
    """A RootModel id (``ArtifactId`` / ``FigureId``) — its string is ``.root``."""

    root: str


def _roots(values: Iterable[_HasRoot] | None) -> list[str]:
    """The ``.root`` string of each RootModel id in an optional list."""
    return [value.root for value in values or ()]


def _dedup(ids: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication."""
    return list(dict.fromkeys(ids))


def entry_dependency_ids(entry: _Entry) -> list[str]:
    """The ids ``entry`` references at the manifest-entry level (order-preserved, de-duped).

    Observations carry no deps on the entry — they live in the file, so an
    :class:`ObservationEntry` returns ``[]`` here; use :func:`observation_dependency_ids`.
    """
    ids: list[str] = []
    if isinstance(entry, EgmBankEntry):
        ids += [ref for ref in (entry.source_bank, entry.model) if ref]
    elif isinstance(entry, TrainingRunEntry):
        if entry.trained_on_bank:
            ids.append(entry.trained_on_bank)
    elif isinstance(entry, ModelEntry):
        if entry.trained_from_run:
            ids.append(entry.trained_from_run)
    elif isinstance(entry, FigureEntry):
        ids += _roots(entry.consumes_banks)
        ids += _roots(entry.consumes_models)
        ids += _roots(entry.consumes_observations)
    elif isinstance(entry, PaperEntry):
        ids += _roots(entry.figures)
    # NoiseBankEntry + ObservationEntry contribute nothing at the entry level.
    return _dedup(ids)


def observation_dependency_ids(observation: Observation) -> list[str]:
    """The ids an observation depends on: its banks + referenced models / parent observations.

    Banks are derived (ADR-017) from ``view_state.banks_loaded`` plus each ``traces[].bank``;
    models + parent observations come from ``references``.
    """
    ids: list[str] = []
    if observation.view_state is not None:
        ids += _roots(observation.view_state.banks_loaded)
    ids += [trace.bank for trace in observation.traces or ()]
    if observation.references is not None:
        ids += _roots(observation.references.models)
        ids += _roots(observation.references.observations)
    return _dedup(ids)


def dependency_ids(entry: _Entry, *, observation: Observation | None = None) -> list[str]:
    """Dependency ids for any entry; pass the loaded ``observation`` for an ObservationEntry."""
    if isinstance(entry, ObservationEntry):
        return observation_dependency_ids(observation) if observation is not None else []
    return entry_dependency_ids(entry)


def manifest_ids(manifest: PhaseManifest) -> set[str]:
    """Every artifact id indexed in ``manifest`` (across all sections)."""
    sections = (
        manifest.egm_banks,
        manifest.noise_banks,
        manifest.training_runs,
        manifest.models,
        manifest.observations,
        manifest.figures,
        manifest.papers,
    )
    return {entry.id for section in sections for entry in section or ()}
