"""The unified per-trace view-model (ADR-002).

The architectural keystone: for any loaded bank, egm-studio builds one
composite per-trace table that joins identity + bank metadata + egm-features
columns. Every filter / sort / pair-comparison / distribution operation runs
against this table, so performance scales with result-set size, not bank size
[ADR-011].

Block 2 builds the features + metadata join (:func:`build_view_model`). ML
outcomes (predicted_prob, correctness_bucket, ...) join in Block 8 when a
predictions bank is loaded; similarity columns are computed on demand
(:mod:`..analysis.similarity`). This package owns the column contract; the
GUI loaders (Block 7) feed it typed egm-data banks.
"""

from __future__ import annotations

from myocard_egm_studio.view_model.builder import (
    FEATURE_COLUMNS,
    IDENTITY_COLUMNS,
    build_view_model,
    feature_units,
)
from myocard_egm_studio.view_model.filtering import (
    Condition,
    FilterColumn,
    FilterSpec,
    apply_filter,
    filter_columns,
)
from myocard_egm_studio.view_model.phase_groups import (
    ArtifactGroup,
    ArtifactRow,
    entries_by_id,
    phase_artifact_groups,
)
from myocard_egm_studio.view_model.trace_detail import DetailRow, TraceDetail, trace_detail

__all__ = [
    "FEATURE_COLUMNS",
    "IDENTITY_COLUMNS",
    "ArtifactGroup",
    "ArtifactRow",
    "Condition",
    "DetailRow",
    "FilterColumn",
    "FilterSpec",
    "TraceDetail",
    "apply_filter",
    "build_view_model",
    "entries_by_id",
    "feature_units",
    "filter_columns",
    "phase_artifact_groups",
    "trace_detail",
]
