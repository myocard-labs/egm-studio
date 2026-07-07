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

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from myocard_egm_data.banks import load_classifier_bank
from myocard_egm_data.phases import PhaseManifest, load_phase_dir


def bank_paths_from_manifest(manifest: PhaseManifest, base_dir: Path | str) -> dict[str, Path]:
    """Every artifact id in ``manifest`` -> its path resolved against ``base_dir``."""
    base = Path(base_dir)
    return {entry.id: base / entry.path for entry in _entries(manifest)}


def bank_paths_from_phase(phase_dir: Path | str) -> dict[str, Path]:
    """Every artifact id in the phase's manifest -> its resolved on-disk path."""
    base = Path(phase_dir)
    return bank_paths_from_manifest(load_phase_dir(base), base)


def resolve_bank_paths(
    dirs: Path | str | Sequence[Path | str], source_ids: Sequence[str]
) -> tuple[list[Path], list[str]]:
    """Resolve loaded-bank ``source_ids`` (from an observation) to bank files, searching
    ``dirs`` in order — one phase for a phase observation, or ``[scratch, phase]`` for a
    scratch one (cross-scope, 2c).

    A bank's view-model ``source`` id is its stamped ``bank.id`` (else its file stem).
    Normally that equals its manifest *entry* id (the stable-id invariant), so the entry-id
    map resolves it directly and no bank is read. When the two have drifted apart, we fall
    back to reading each egm bank's own id. Returns ``(paths in request order, unresolved)``.
    """
    base_dirs = [Path(dirs)] if isinstance(dirs, str | Path) else [Path(d) for d in dirs]
    resolved: dict[str, Path] = {}
    for base in base_dirs:  # earlier dirs win (scratch before phase)
        for sid, path in _safe_bank_paths(base).items():
            resolved.setdefault(sid, path)
    unresolved = {sid for sid in source_ids if sid not in resolved}
    for base in base_dirs:
        if not unresolved:
            break
        for sid, path in _egm_bank_paths_by_source_id(base, unresolved).items():
            resolved.setdefault(sid, path)
        unresolved = {sid for sid in source_ids if sid not in resolved}
    paths = [resolved[sid] for sid in source_ids if sid in resolved]
    missing = [sid for sid in source_ids if sid not in resolved]
    return paths, missing


def _safe_bank_paths(base: Path) -> dict[str, Path]:
    """``bank_paths_from_phase`` for a dir that may have no manifest (-> empty)."""
    try:
        return bank_paths_from_phase(base)
    except Exception:  # no / unreadable manifest at this dir — contributes nothing
        return {}


def _egm_bank_paths_by_source_id(base: Path, wanted: set[str]) -> dict[str, Path]:
    """Map each egm bank's loaded ``source`` id (``bank.id`` or file stem) -> path, for
    ids in ``wanted`` — reading banks, stopping once all are found, skipping unreadable
    files. Only reached when an id doesn't match a manifest entry id (the drift case).
    """
    found: dict[str, Path] = {}
    try:
        egm_banks = load_phase_dir(base).egm_banks or ()
    except Exception:  # no / unreadable manifest at this dir
        return found
    for entry in egm_banks:
        if len(found) == len(wanted):
            break
        path = base / entry.path
        try:
            source_id = load_classifier_bank(path).id or path.stem
        except Exception:  # unreadable / missing file — skip, it just stays unresolved
            continue
        if source_id in wanted:
            found[source_id] = path
    return found


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
