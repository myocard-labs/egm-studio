"""Resolve a phase's manifest into the ``{artifact_id: path}`` map loaders consume.

Block 6's egm-data reader (:func:`load_phase_dir`) turns a phase folder into a
typed :class:`PhaseManifest`; :func:`bank_paths_from_phase` maps every artifact id
in it to its on-disk path. That's the same ``{artifact_id: path}`` shape the CLI
used to build by hand from ``--bank`` / ``--banks`` — so ``egm-studio-render
--phase <folder>`` renders a phase's specs without a hand-written map.

Every manifest section is included (banks, runs, models, noise, figures, papers),
since a figure_spec can name a bank *or* a run id (the training-curve loader) or a
noise bank (the curation-summary loader). Paths are resolved relative to the phase
folder; an absolute path in the manifest wins (pathlib join semantics).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from myocard_egm_data.phases import PhaseManifest, load_phase_dir


def bank_paths_from_phase(phase_dir: Path | str) -> dict[str, Path]:
    """Every artifact id in the phase's manifest -> its resolved on-disk path."""
    base = Path(phase_dir)
    return {entry.id: base / entry.path for entry in _entries(load_phase_dir(base))}


def _entries(manifest: PhaseManifest) -> list[Any]:
    """Flatten every manifest section into one list of pointer entries."""
    sections = (
        manifest.egm_banks,
        manifest.noise_banks,
        manifest.training_runs,
        manifest.models,
        manifest.observations,
        manifest.figures,
        manifest.papers,
    )
    return [entry for section in sections for entry in (section or ())]
