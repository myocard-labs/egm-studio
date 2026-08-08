"""Copy a producer artifact into the phase folder so the phase is self-contained (B17).

Before this, indexing a bank recorded an **absolute pointer** at wherever the producer
left it. That makes a phase folder unopenable on another machine, and unmovable on this
one. B17's rule is that a phase owns its artifacts: the file is copied under
``phases/phase_<N>/<type>/`` and the manifest records a **relative** path, so the folder
can be moved, archived or handed over whole.

**HDF5 is never committed.** ``*.h5`` / ``*.hdf5`` are gitignored in intracardiac-platform,
so a phase folder is self-contained *on disk*, not in git: what is committed is the
manifest plus provenance, and the banks are regenerated or pulled from a release. That is
why a missing in-phase bank reads as *unresolved* rather than as an error.

Three mechanics the authored-artifact path (figures / observations, already relative)
never needed:

- **Sibling files travel with their artifact.** Two kinds. A noise bank's
  ``<stem>_run_record.json`` carries the id its ``.h5`` lacks, so copying the ``.h5`` alone
  would produce a bank nothing can identify — that one is a filename convention, found here.
  A synthetic bank additionally *declares* its companions (the θ bank, the noise bank it was
  mixed with) as relative paths resolved beside itself; those are read out of the file by
  the caller and passed in as ``companions``.
- **Re-indexing is idempotent.** An artifact already inside the phase is re-pointed, not
  re-copied — otherwise re-adding a 500 MB bank silently duplicates it.
- **Removal deletes only the in-phase copy.** The producer's original is left alone; it is
  not ours to delete.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "SUBDIR_BY_ROLE",
    "copy_into_phase",
    "phase_relative",
]

#: Where each artifact role's files live under the phase folder. Authored artifacts keep
#: the ``figures`` / ``observations`` names ``save.figure`` / ``save.observation`` already
#: use, so the layout is one scheme rather than two.
SUBDIR_BY_ROLE: dict[str, str] = {
    "training_bank": "banks",
    "pretraining_bank": "banks",
    "labeled_prediction_bank": "banks",
    "unlabeled_prediction_bank": "banks",
    "noise_bank": "banks",
    "training_run": "runs",
    "model": "models",
    "observation": "observations",
    "figure": "figures",
    # Papers live in intracardiac-papers and are arguably the *output* of a phase rather
    # than data it holds — the phase folder exists to carry what the paper is written
    # *from*. Mapped anyway because the copy is non-destructive: the paper repo keeps its
    # original either way, so an indexed paper costs a duplicate and no correctness. If
    # the "does a paper belong in the phase?" question is settled the other way, drop this
    # row and indexing one raises rather than inventing a location.
    "paper": "papers",
}

#: Suffix of the sidecar a noise bank's id lives in (the iafdb export convention). It must
#: travel with the ``.h5``: the bank file carries no id of its own before B20.
_NOISE_RECORD_SUFFIX = "_run_record.json"


def phase_relative(path: Path, phase_dir: Path) -> str:
    """``path`` as a manifest value: relative when inside ``phase_dir``, else absolute.

    The asymmetry is the point. An in-phase artifact is recorded relatively so the folder
    stays movable; one that genuinely lives elsewhere keeps its absolute path, which ties
    the manifest to this machine and is exactly why B17 copies things in.
    """
    try:
        return str(path.resolve().relative_to(phase_dir.resolve()))
    except ValueError:
        return str(path)


def copy_into_phase(
    source: Path | str,
    phase_dir: Path | str,
    role_name: str,
    *,
    companions: Iterable[Path | str] = (),
) -> Path:
    """Copy ``source`` into ``phase_dir``'s subfolder for ``role_name``; return the copy.

    Idempotent: a file already inside the phase folder is returned untouched rather than
    copied onto itself, so re-indexing costs nothing and cannot duplicate a large bank.

    ``companions`` are files the artifact *declares* and resolves beside itself — a
    synthetic bank's θ companion and the noise bank it was mixed with. They are copied
    next to it so those relative references still resolve from inside the phase. A declared
    companion that is missing beside the source is skipped rather than raising: it is
    already unresolvable where it is, and refusing to index the bank over it would be worse
    than carrying the same gap forward.

    Raises
    ------
    FileNotFoundError
        If ``source`` does not exist — better than creating a phase entry pointing at a
        file that was never copied.
    ValueError
        If ``role_name`` has no known subfolder, rather than inventing one.
    """
    src = Path(source)
    phase = Path(phase_dir)
    if not src.exists():
        raise FileNotFoundError(f"cannot copy {src} into the phase: it does not exist")
    subdir = SUBDIR_BY_ROLE.get(role_name)
    if subdir is None:
        raise ValueError(f"no phase subfolder is defined for artifact role {role_name!r}")

    destination = phase / subdir / src.name
    if _already_inside(src, phase):
        return src

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, destination)
    for sibling in _siblings(src, companions):
        shutil.copy2(sibling, destination.parent / sibling.name)
    return destination


def _already_inside(path: Path, phase_dir: Path) -> bool:
    """Whether ``path`` already lives under ``phase_dir``."""
    try:
        path.resolve().relative_to(phase_dir.resolve())
    except ValueError:
        return False
    return True


def _siblings(source: Path, companions: Iterable[Path | str] = ()) -> list[Path]:
    """Files that must travel with ``source`` for it to stay usable, de-duplicated.

    The convention-found run record plus whatever the caller read out of the artifact. Both
    are filtered to what actually exists beside the source, and ``source`` itself is dropped
    in case a declared companion points back at it.
    """
    found = [source.with_name(source.stem + _NOISE_RECORD_SUFFIX)]
    found += [Path(companion) for companion in companions]
    unique = dict.fromkeys(path.resolve() for path in found)
    return [path for path in unique if path.exists() and path != source.resolve()]
