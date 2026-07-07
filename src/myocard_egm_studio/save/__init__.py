"""The save flow — egm-studio as the meta-repo's canonical curator (Block 10).

egm-studio is the only consumer that *writes* artifacts back into the phase-organized
meta repo (intracardiac-platform). This package owns that write path, framework-free:

- :mod:`.ids` — compose stable ids for authored artifacts (``obs_<slug>_<date>``).
- :mod:`.observation` — assemble + write an Observation JSON into a phase's
  ``observations/`` folder (or the scratch dir), and build its manifest entry.
- :mod:`.manifest` — add an observation / figure entry to a phase manifest + write it.

The GUI (Save-observation dialog + Phase-tree actions) calls these; the end-of-phase
``validate_manifest.py`` release gate lives in intracardiac-platform. [ADR-017, ADR-021]
"""

from myocard_egm_studio.save.capture import capture_view_state, describe_filter, parse_filter
from myocard_egm_studio.save.figure import figure_entry, figure_spec_path, save_figure_spec
from myocard_egm_studio.save.ids import observation_id, slugify, today_utc, validate_artifact_id
from myocard_egm_studio.save.manifest import (
    empty_manifest,
    manifest_section,
    remove_entry,
    save_manifest,
    with_entry,
)
from myocard_egm_studio.save.observation import (
    build_observation,
    observation_entry,
    observation_path,
    references_from,
    save_observation,
    update_observation,
)
from myocard_egm_studio.save.producer import (
    bank_entry,
    model_entry,
    noise_bank_entry,
    run_entry,
)
from myocard_egm_studio.save.scratch import SCRATCH_PHASE, load_scratch, scratch_manifest_path

__all__ = [
    "SCRATCH_PHASE",
    "bank_entry",
    "build_observation",
    "capture_view_state",
    "describe_filter",
    "empty_manifest",
    "figure_entry",
    "figure_spec_path",
    "load_scratch",
    "manifest_section",
    "model_entry",
    "noise_bank_entry",
    "observation_entry",
    "observation_id",
    "observation_path",
    "parse_filter",
    "references_from",
    "remove_entry",
    "run_entry",
    "save_figure_spec",
    "save_manifest",
    "save_observation",
    "scratch_manifest_path",
    "slugify",
    "today_utc",
    "update_observation",
    "validate_artifact_id",
    "with_entry",
]
