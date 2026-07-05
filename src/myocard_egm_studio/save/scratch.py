"""The scratch area as a real (unnumbered) phase manifest (Block 10h-2a).

Scratch is where saves made with no phase open land — and, once producer artifacts can be
staged there (2b), where loaded-but-unindexed banks / runs live too. To give it the full
organization and actions of a phase, scratch *is* a phase: a ``<scratch>/manifest.json``
(a :class:`PhaseManifest` with a sentinel phase number) over the same ``observations/`` +
``figures/`` authored layout. The GUI renders it with the same PhaseTree; Promote moves an
entry plus its file into the loaded phase.

:func:`load_scratch` reads that manifest, migrating a pre-manifest scratch folder (loose
observation / figure files with no manifest, from the earlier flat model) on first read.
Framework-free.
"""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import (
    MANIFEST_FILENAME,
    PhaseManifest,
    load_figure_spec,
    load_observation,
    load_phase_dir,
)

from myocard_egm_studio.save.figure import FIGURES_DIR, figure_entry
from myocard_egm_studio.save.manifest import empty_manifest, save_manifest, with_entry
from myocard_egm_studio.save.observation import OBSERVATIONS_DIR, observation_entry

__all__ = ["SCRATCH_PHASE", "load_scratch", "scratch_manifest_path"]

#: Sentinel phase number for the scratch manifest — scratch is not a numbered phase, but a
#: PhaseManifest requires one. The value is inert (never surfaced as a phase label).
SCRATCH_PHASE = 0.0


def scratch_manifest_path(scratch_dir: Path | str) -> Path:
    """Where the scratch manifest lives — ``<scratch>/manifest.json``."""
    return Path(scratch_dir) / MANIFEST_FILENAME


def load_scratch(scratch_dir: Path | str) -> PhaseManifest:
    """The scratch manifest: read from disk, or synthesized (and persisted) by migrating a
    pre-manifest scratch folder. An empty / absent scratch yields an entry-less manifest."""
    base = Path(scratch_dir)
    if scratch_manifest_path(base).exists():
        return load_phase_dir(base)
    manifest = _from_loose_files(base)
    if manifest.observations or manifest.figures:
        save_manifest(manifest, base)  # persist the one-time migration off the flat model
    return manifest


def _from_loose_files(scratch_dir: Path) -> PhaseManifest:
    """Build a scratch manifest by indexing any loose observation / figure files."""
    manifest = empty_manifest(SCRATCH_PHASE)
    obs_dir = scratch_dir / OBSERVATIONS_DIR
    if obs_dir.is_dir():
        for path in sorted(obs_dir.glob("*.json")):
            manifest = with_entry(
                manifest, "observations", observation_entry(load_observation(path))
            )
    fig_dir = scratch_dir / FIGURES_DIR
    if fig_dir.is_dir():
        for path in sorted(fig_dir.glob("*.json")):
            manifest = with_entry(manifest, "figures", figure_entry(load_figure_spec(path)))
    return manifest
