"""Add egm-studio-authored entries to a phase manifest + write it (Block 10, ADR-021).

egm-studio is the canonical manifest curator: when an observation or figure spec is
saved into a phase, its entry is added here and the manifest re-written. Adding is
idempotent — an entry with the same id replaces the old one, so re-saving updates in
place. (The end-of-phase ``validate_manifest.py`` release gate lives in
intracardiac-platform, not here — it is not run per write.)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from myocard_egm_data.phases import MANIFEST_FILENAME, write_phase_manifest

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.phase_manifest import (
        FigureEntry,
        ObservationEntry,
        PhaseManifest,
    )

__all__ = ["save_manifest", "with_figure", "with_observation"]


def with_observation(manifest: PhaseManifest, entry: ObservationEntry) -> PhaseManifest:
    """A copy of ``manifest`` with ``entry`` in its observations (replacing a same-id one)."""
    kept = [e for e in (manifest.observations or ()) if e.id != entry.id]
    return manifest.model_copy(update={"observations": [*kept, entry]})


def with_figure(manifest: PhaseManifest, entry: FigureEntry) -> PhaseManifest:
    """A copy of ``manifest`` with ``entry`` in its figures (replacing a same-id one)."""
    kept = [e for e in (manifest.figures or ()) if e.id != entry.id]
    return manifest.model_copy(update={"figures": [*kept, entry]})


def save_manifest(manifest: PhaseManifest, phase_dir: Path | str) -> Path:
    """Write ``manifest`` to ``<phase_dir>/<MANIFEST_FILENAME>``."""
    return write_phase_manifest(Path(phase_dir) / MANIFEST_FILENAME, manifest)
