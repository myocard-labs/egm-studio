"""Shared skeleton for egm-studio-*authored* artifacts (Block 10).

Observations and figure specs are the two artifacts egm-studio itself *writes* into a
phase (as opposed to producer artifacts — banks, runs, models — which it only indexes).
Both land at ``<phase>/<subdir>/<id>.json`` and share the same manifest-entry preamble,
so that common shape lives here; each type's writer is then just its assembly + the
type-specific relationship fields. Framework-free (no Qt, no per-type knowledge).
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import TypeVar

#: The package name stamped on every egm-studio-authored manifest entry.
PACKAGE = "egm-studio"

_ModelT = TypeVar("_ModelT")


def authored_path(phase_dir: Path | str, subdir: str, artifact_id: str) -> Path:
    """Where an authored artifact lives under a phase: ``<phase>/<subdir>/<id>.json``."""
    return Path(phase_dir) / subdir / f"{artifact_id}.json"


def save_authored(model: _ModelT, path: Path, writer: Callable[[Path, _ModelT], Path]) -> Path:
    """Write ``model`` to ``path`` via its egm-data ``writer``, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return writer(path, model)


def base_entry_fields(
    artifact_id: str, path: str, *, usage_tag: str | None, usage_notes: str | None
) -> dict[str, object]:
    """The manifest-entry preamble shared by every egm-studio-authored artifact.

    Per-type entry builders spread this and add their relationship fields (a figure's
    ``consumes_banks`` / ``consumes_observations``, an observation carries none).
    """
    return {
        "id": artifact_id,
        "path": path,
        "produced_by_package": PACKAGE,
        "produced_by_version": version("myocard-egm-studio"),
        "usage_tag": usage_tag,
        "usage_notes": usage_notes,
    }
