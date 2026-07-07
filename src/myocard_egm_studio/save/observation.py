"""Assemble + write an Observation from egm-studio (Block 10, ADR-017).

An observation is prose (a required ``description``) plus an optional attached trace
list and optional egm-studio ``view_state`` (enough to reload the noticing later). It is
written as a standalone JSON file into the meta repo — a loaded phase's
``observations/`` folder, or the scratch dir — and indexed in the phase manifest by the
shell (:mod:`.manifest`).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from myocard_egm_data.phases import Observation, ObservationEntry, References, write_observation

from myocard_egm_studio.save.artifacts import authored_path, base_entry_fields, save_authored
from myocard_egm_studio.save.ids import observation_id, today_utc

if TYPE_CHECKING:
    from myocard_egm_contracts._generated.python.observation import TraceRef, ViewState

#: Subfolder of a phase where observation files live; also the manifest entry's path root.
OBSERVATIONS_DIR = "observations"


def build_observation(
    *,
    title: str,
    description: str,
    view_state: ViewState | None = None,
    traces: list[TraceRef] | None = None,
    references: References | None = None,
    today: str | None = None,
) -> Observation:
    """Build an :class:`Observation` — a generated ``obs_<slug>_<date>`` id + today's date.

    ``description`` (prose) is required; ``view_state`` / ``traces`` / ``references`` are
    optional (ADR-017). Bank refs are *derived* from ``view_state.banks_loaded`` +
    ``traces[].bank`` — there is no separate banks field.
    """
    day = today or today_utc()
    raw: dict[str, object] = {
        "schema_version": "1",
        "id": observation_id(title, today=day),
        "date": day,
        "title": title,
        "description": description,
    }
    if references is not None:
        raw["references"] = references.model_dump(mode="json", exclude_none=True)
    if traces:
        raw["traces"] = [trace.model_dump(mode="json") for trace in traces]
    if view_state is not None:
        raw["view_state"] = view_state.model_dump(mode="json", exclude_none=True)
    return Observation.model_validate(raw)


def update_observation(
    existing: Observation, *, title: str, description: str, references: References | None = None
) -> Observation:
    """An edit of ``existing`` — new ``title`` / ``description`` / ``references`` prose.

    The stable ``id`` and ``date`` are minted at creation and preserved, as are the
    captured ``view_state`` + ``traces`` (reload state, not edited here). ``references`` is
    replaced wholesale (``None`` clears the parent links).
    """
    return existing.model_copy(
        update={"title": title, "description": description, "references": references}
    )


def references_from(
    *, observations: Sequence[str] = (), models: Sequence[str] = ()
) -> References | None:
    """A :class:`References` from parent-observation + model ids, or ``None`` if both empty.

    Bank refs are intentionally never here — they are derived from ``view_state`` + traces.
    """
    if not observations and not models:
        return None
    return References.model_validate(
        {"observations": list(observations) or None, "models": list(models) or None}
    )


def observation_path(observation: Observation, phase_dir: Path | str) -> Path:
    """Where ``observation`` is written under ``phase_dir`` — ``observations/<id>.json``."""
    return authored_path(phase_dir, OBSERVATIONS_DIR, observation.id)


def save_observation(observation: Observation, phase_dir: Path | str) -> Path:
    """Write ``observation`` to ``<phase_dir>/observations/<id>.json`` (creating the dir)."""
    return save_authored(observation, observation_path(observation, phase_dir), write_observation)


def observation_entry(
    observation: Observation, *, usage_tag: str = "exploratory", usage_notes: str | None = None
) -> ObservationEntry:
    """The manifest entry for a saved observation (path relative to the phase dir)."""
    return ObservationEntry.model_validate(
        base_entry_fields(
            observation.id,
            f"{OBSERVATIONS_DIR}/{observation.id}.json",
            usage_tag=usage_tag,
            usage_notes=usage_notes,
        )
    )
