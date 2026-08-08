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

import os
import shutil
from collections.abc import Callable, Iterable
from pathlib import Path

from myocard_egm_studio.view_model.builder import ProgressFn

__all__ = [
    "SUBDIR_BY_ROLE",
    "CopyCancelled",
    "copy_into_phase",
    "phase_relative",
]

#: Read/write block size. Large enough that a 500 MB bank is ~125 writes rather than
#: thousands, small enough that cancel is felt immediately — the cancel flag and the
#: progress callback are both checked once per block.
_CHUNK_BYTES = 4 * 1024 * 1024

#: Free space demanded *beyond* the bytes actually being copied. A copy that fills the
#: volume to the last byte leaves a machine that cannot write the manifest it is about to
#: write, so the check refuses a little early rather than technically-succeeding.
_FREE_SPACE_MARGIN_BYTES = 64 * 1024 * 1024

#: Suffix of the in-progress file. The copy writes here and renames on completion, so a
#: cancelled or failed copy can never be mistaken for a whole artifact — the phase folder
#: only ever contains complete files under their real names.
_PARTIAL_SUFFIX = ".partial"


class CopyCancelled(Exception):
    """The user cancelled a copy. Not a failure: callers report it as such, not as an error."""


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
    progress: ProgressFn | None = None,
    cancelled: Callable[[], bool] | None = None,
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

    Banks run 100-500 MB, so the copy is **chunked**: ``progress`` is called with
    ``(bytes_done, bytes_total)`` across the whole set, and ``cancelled`` is polled once
    per block. Space is checked up front and every file lands atomically, so the three ways
    this can end — done, cancelled, out of space — all leave the phase folder holding
    whole files or nothing, never a truncated bank under a real name.

    Raises
    ------
    FileNotFoundError
        If ``source`` does not exist — better than creating a phase entry pointing at a
        file that was never copied.
    ValueError
        If ``role_name`` has no known subfolder, rather than inventing one.
    OSError
        If the volume cannot hold the copy. Raised *before* anything is written.
    CopyCancelled
        If ``cancelled`` returned true. Partial output is removed first.
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

    to_copy = [src, *_siblings(src, companions)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    _require_free_space(to_copy, destination.parent)

    total = sum(path.stat().st_size for path in to_copy)
    done = 0
    written: list[Path] = []
    try:
        for path in to_copy:
            done = _copy_file(
                path,
                destination.parent / path.name,
                done=done,
                total=total,
                progress=progress,
                cancelled=cancelled,
            )
            written.append(destination.parent / path.name)
    except BaseException:
        # Cancelled, out of space, or interrupted: an artifact copied only in part is worse
        # than one absent, because the manifest entry never gets written to explain it.
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return destination


def _require_free_space(sources: Iterable[Path], destination_dir: Path) -> None:
    """Refuse a copy the volume cannot hold, before a single byte is written.

    Running out of space mid-copy is recoverable here (the partial file is removed) but it
    wastes the whole transfer of a 500 MB bank to discover something knowable in advance.
    """
    needed = sum(path.stat().st_size for path in sources)
    free = shutil.disk_usage(destination_dir).free
    if free < needed + _FREE_SPACE_MARGIN_BYTES:
        raise OSError(
            f"not enough free space to copy into the phase: {_mb(needed)} needed "
            f"(plus {_mb(_FREE_SPACE_MARGIN_BYTES)} headroom), {_mb(free)} free on "
            f"{destination_dir}"
        )


def _copy_file(
    source: Path,
    destination: Path,
    *,
    done: int,
    total: int,
    progress: ProgressFn | None,
    cancelled: Callable[[], bool] | None,
) -> int:
    """Copy one file in blocks; return the new cumulative byte count.

    Written to ``<name>.partial`` and renamed on completion, so the destination name only
    ever appears once the bytes are all there. ``os.replace`` is atomic within a filesystem,
    which is the case here — the partial sits in the folder it is destined for.
    """
    partial = destination.with_name(destination.name + _PARTIAL_SUFFIX)
    try:
        with source.open("rb") as reader, partial.open("wb") as writer:
            while chunk := reader.read(_CHUNK_BYTES):
                if cancelled is not None and cancelled():
                    raise CopyCancelled(f"copy of {source.name} was cancelled")
                writer.write(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    os.replace(partial, destination)
    shutil.copystat(source, destination)  # mtime / mode, as shutil.copy2 did
    return done


def _mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):,.0f} MB"


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
