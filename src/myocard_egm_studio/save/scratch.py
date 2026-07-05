"""List egm-studio-authored artifacts sitting in the scratch folder (Block 10e).

Scratch mirrors a phase's authored layout — ``<scratch>/observations/<id>.json`` and
``<scratch>/figures/<id>.json`` — but has *no* manifest: it's a holding area for saves
made with no phase open. This scans those two folders so the GUI can show the pile and
promote items into a phase. Framework-free (pure filesystem).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from myocard_egm_studio.save.figure import FIGURES_DIR
from myocard_egm_studio.save.observation import OBSERVATIONS_DIR

__all__ = ["ScratchArtifact", "scratch_artifacts"]

ArtifactKind = Literal["observation", "figure"]
#: Which scratch subdir holds each kind (mirrors the authored-save layout).
_SUBDIRS: tuple[tuple[str, ArtifactKind], ...] = (
    (OBSERVATIONS_DIR, "observation"),
    (FIGURES_DIR, "figure"),
)


@dataclass(frozen=True)
class ScratchArtifact:
    """One artifact file in the scratch folder: its id, kind, and path."""

    id: str
    kind: ArtifactKind
    path: Path


def scratch_artifacts(scratch_dir: Path | str) -> list[ScratchArtifact]:
    """Every observation + figure spec file under ``scratch_dir`` (observations first, by id)."""
    base = Path(scratch_dir)
    found: list[ScratchArtifact] = []
    for subdir, kind in _SUBDIRS:
        folder = base / subdir
        if folder.is_dir():
            found += [ScratchArtifact(p.stem, kind, p) for p in sorted(folder.glob("*.json"))]
    return found
