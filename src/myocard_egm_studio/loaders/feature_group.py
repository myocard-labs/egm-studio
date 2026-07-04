"""Build a charts ``FeatureGroup`` from an in-memory view-model frame.

The single place that turns the per-trace view-model (identity + metadata +
egm-features columns) into the feature-only :class:`FeatureGroup` the
distribution charts consume. Shared by the figure loader
(:func:`..figure_inputs.load_feature_groups`, which builds the frame from a bank)
and the GUI's Flow A summary landing (B7.7, which already holds the frame), so
both produce identical group inputs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from myocard_egm_studio.charts.inputs import FeatureGroup
from myocard_egm_studio.view_model import FEATURE_COLUMNS, feature_units

__all__ = ["feature_group_from_frame"]


def feature_group_from_frame(frame: pd.DataFrame, *, name: str | None = None) -> FeatureGroup:
    """Pull the 11 ``FEATURE_COLUMNS`` out of ``frame`` as one named FeatureGroup.

    ``name`` labels the group (legend / provenance); it defaults to the frame's
    ``source`` column (stamped by ``build_view_model(source=...)``), else the
    source bank id, else ``"bank"``. Units track the bank's ``amp_type`` via
    :func:`myocard_egm_studio.view_model.feature_units`, so ``peak_to_peak`` reads
    as ``mV`` only for a raw-mV bank. The frame must carry the feature columns
    (built with ``with_features=True``).
    """
    values = {col: frame[col].to_numpy(dtype=np.float64) for col in FEATURE_COLUMNS}
    label = name or _first(frame, "source") or _first(frame, "source_bank_id") or "bank"
    return FeatureGroup(name=label, values=values, units=feature_units(_first(frame, "amp_type")))


def _first(frame: pd.DataFrame, column: str) -> str | None:
    """First non-null value of a column as ``str``, or None."""
    if column not in frame.columns:
        return None
    non_null = frame[column].dropna()
    return str(non_null.iloc[0]) if not non_null.empty else None
