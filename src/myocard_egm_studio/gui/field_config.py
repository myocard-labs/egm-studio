"""Curated, per-bank-type display / filter fields for the trace selector.

Trace metadata is mostly provenance; only a small, useful subset is worth showing
and filtering on, and that subset differs by bank type (synthetic carries
``sim_id`` / ``pair_index`` / ``stim_edge``; IAFDB carries ``patient_id`` /
``source_record`` / ``source_channel``). This is the app's display policy —
egm-studio is the executable-level consumer, so it lives in code and is versioned
with the bank schemas it tracks; it can be promoted to a config file later if
end-users ever need to customise it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

#: The universal per-trace class field the selector injects from ``label_truth``.
CLASS_FIELD = "class"

#: Curated field key -> human label. The allowlist: anything not here is hidden
#: (keeps the ~dozen provenance fields out of the selector).
FIELD_LABELS: dict[str, str] = {
    "patient_id": "Patient",
    "source_record": "Record",
    "source_channel": "Channel",
    "sim_id": "Sim",
    "pair_index": "Electrode pair",
    "electrode_pair_id": "Electrode pair",
    "stim_edge": "Stim edge",
    CLASS_FIELD: "Class",
}

#: Per-bank-type column / filter order (a subset of FIELD_LABELS). Unknown bank
#: types fall back to the FIELD_LABELS order intersected with the present fields.
DISPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "synthetic": ("sim_id", "pair_index", "electrode_pair_id", "stim_edge", CLASS_FIELD),
    "synthetic_egm_pipeline": ("sim_id", "pair_index", "stim_edge", CLASS_FIELD),
    "iafdb": ("patient_id", "source_record", "source_channel", CLASS_FIELD),
}


@dataclass(frozen=True)
class FieldSpec:
    """A displayed / filterable field: its metadata key + human column label."""

    key: str
    label: str


def fields_for(bank_type: str, present: Iterable[str]) -> list[FieldSpec]:
    """Curated (key, label) fields to show / filter for ``bank_type``, present in the data."""
    present_set = set(present)
    order = DISPLAY_FIELDS.get(bank_type, tuple(FIELD_LABELS))
    seen: set[str] = set()
    specs: list[FieldSpec] = []
    for key in order:
        if key in present_set and key in FIELD_LABELS and key not in seen:
            specs.append(FieldSpec(key, FIELD_LABELS[key]))
            seen.add(key)
    return specs
