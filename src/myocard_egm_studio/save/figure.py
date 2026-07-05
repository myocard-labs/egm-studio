"""Place a figure spec into a phase + derive its manifest entry (Block 10d).

A figure spec is an egm-studio-authored artifact: it lands at ``<phase>/figures/<id>.json``
and is indexed by a ``FigureEntry``. Unlike an observation, the spec itself is built by
the Flow C form (not here) — this module only writes it to the canonical location and
derives the entry's relationship fields: ``consumes_banks`` from the spec's input groups,
``consumes_observations`` from its ``illustrates_observations``. Shares the authored-save
skeleton (:mod:`.artifacts`) with the observation writer.
"""

from __future__ import annotations

from pathlib import Path

from myocard_egm_data.phases import FigureEntry, FigureSpec, write_figure_spec

from myocard_egm_studio.save.artifacts import authored_path, base_entry_fields, save_authored

#: Subfolder of a phase where figure spec files live; also the manifest entry's path root.
FIGURES_DIR = "figures"

__all__ = ["FIGURES_DIR", "figure_entry", "figure_spec_path", "save_figure_spec"]


def figure_spec_path(spec: FigureSpec, phase_dir: Path | str) -> Path:
    """Where ``spec`` is written under ``phase_dir`` — ``figures/<id>.json``."""
    return authored_path(phase_dir, FIGURES_DIR, spec.id)


def save_figure_spec(spec: FigureSpec, phase_dir: Path | str) -> Path:
    """Write ``spec`` to ``<phase_dir>/figures/<id>.json`` (creating the dir)."""
    return save_authored(spec, figure_spec_path(spec, phase_dir), write_figure_spec)


def figure_entry(
    spec: FigureSpec, *, usage_tag: str = "exploratory", usage_notes: str | None = None
) -> FigureEntry:
    """The manifest entry for a saved figure spec (relationship fields derived from it)."""
    fields = base_entry_fields(
        spec.id,
        f"{FIGURES_DIR}/{spec.id}.json",
        usage_tag=usage_tag,
        usage_notes=usage_notes,
    )
    fields["consumes_banks"] = _consumes_banks(spec) or None
    fields["consumes_observations"] = _consumes_observations(spec) or None
    return FigureEntry.model_validate(fields)


def _consumes_banks(spec: FigureSpec) -> list[str]:
    """The distinct bank ids the spec's input groups reference (order preserved)."""
    groups = (spec.inputs.groups if spec.inputs else None) or []
    return list(dict.fromkeys(group.bank_id for group in groups))


def _consumes_observations(spec: FigureSpec) -> list[str]:
    """The observation ids the spec illustrates (``illustrates_observations`` -> str)."""
    return [obs.root for obs in (spec.illustrates_observations or [])]
