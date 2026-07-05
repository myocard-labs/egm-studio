"""Add / remove entries in a phase manifest + write it (Block 10, ADR-021).

egm-studio is the canonical manifest curator: as observations / figure specs are saved
into a phase (and, in B10g, producer artifacts are indexed or removed), the manifest is
re-written here. One generic :func:`with_entry` / :func:`remove_entry` pair serves every
section — adding is idempotent (a same-id entry replaces the old one, so re-saving
updates in place). The end-of-phase ``validate_manifest.py`` release gate lives in
intracardiac-platform, not here — it is not run per write.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from myocard_egm_data.phases import MANIFEST_FILENAME, PhaseManifest, write_phase_manifest

if TYPE_CHECKING:
    from myocard_egm_data.phases import (
        EgmBankEntry,
        FigureEntry,
        ModelEntry,
        NoiseBankEntry,
        ObservationEntry,
        PaperEntry,
        TrainingRunEntry,
    )

    #: Any manifest pointer entry — every one carries an ``id`` (the dedup key).
    _Entry = (
        EgmBankEntry
        | NoiseBankEntry
        | TrainingRunEntry
        | ModelEntry
        | ObservationEntry
        | FigureEntry
        | PaperEntry
    )

#: The manifest's list-valued sections (each holds one artifact type's entries).
_Section = Literal[
    "egm_banks", "noise_banks", "training_runs", "models", "observations", "figures", "papers"
]

__all__ = ["empty_manifest", "remove_entry", "save_manifest", "with_entry"]


def empty_manifest(phase: float) -> PhaseManifest:
    """A fresh, entry-less ``in_progress`` phase manifest (File ▸ New phase creates one)."""
    return PhaseManifest.model_validate(
        {"schema_version": "1", "phase": phase, "status": "in_progress"}
    )


def with_entry(manifest: PhaseManifest, section: _Section, entry: _Entry) -> PhaseManifest:
    """A copy of ``manifest`` with ``entry`` in ``section`` (replacing a same-id one)."""
    kept = [e for e in (getattr(manifest, section) or ()) if e.id != entry.id]
    return manifest.model_copy(update={section: [*kept, entry]})


def remove_entry(manifest: PhaseManifest, section: _Section, entry_id: str) -> PhaseManifest:
    """A copy of ``manifest`` with the ``section`` entry whose id is ``entry_id`` removed."""
    kept = [e for e in (getattr(manifest, section) or ()) if e.id != entry_id]
    return manifest.model_copy(update={section: kept or None})


def save_manifest(manifest: PhaseManifest, phase_dir: Path | str) -> Path:
    """Write ``manifest`` to ``<phase_dir>/<MANIFEST_FILENAME>``."""
    return write_phase_manifest(Path(phase_dir) / MANIFEST_FILENAME, manifest)
