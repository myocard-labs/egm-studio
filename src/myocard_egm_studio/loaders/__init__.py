"""egm-studio's data-loading layer — figure-input adapters + phase resolution.

Turns artifact ids into the in-memory inputs downstream code draws:

- :mod:`.figure_inputs` — the figure-data loaders: ``resolve_recipe_data`` (spec +
  a ``{artifact_id: path}`` map -> the recipe's prepared input) and the permanent
  bank -> recipe-input adapters (e.g. :func:`prediction_group_from_bank`).
- :mod:`.manifest` — :func:`bank_paths_from_phase`, which builds that
  ``{artifact_id: path}`` map from a phase folder's ``manifest.json`` (via
  egm-data's Block 6 reader), replacing the hand-supplied ``--bank`` / ``--banks``
  map for manifest-driven rendering.

This lives outside ``figures/`` so the render layer stays pure plotting (it takes
already-prepared data). All file reads go through egm-data — never raw file I/O.
[architecture.md "The three-layer rendering split"]
"""

from __future__ import annotations

from myocard_egm_studio.loaders.feature_group import (
    confusion_by_source,
    confusion_from_frame,
    feature_group_from_frame,
    feature_groups_by_source,
    prediction_group_from_frame,
    prediction_groups_by_source,
    scatter_series_by_source,
    scatter_series_from_frame,
)
from myocard_egm_studio.loaders.figure_inputs import (
    LOADERS,
    BankPaths,
    LoaderNotRegisteredError,
    RecipeLoaderFn,
    UnmappedBankIdError,
    load_bar_chart_distances,
    load_curation_summary_table,
    load_feature_groups,
    load_group_banks,
    load_prediction_groups,
    load_trace_pair_gallery,
    load_training_curve,
    prediction_group_from_bank,
    register_loader,
    resolve_recipe_data,
    training_curve_from_run,
)
from myocard_egm_studio.loaders.manifest import (
    bank_paths_from_manifest,
    bank_paths_from_phase,
    resolve_bank_paths,
)

__all__ = [
    "LOADERS",
    "BankPaths",
    "LoaderNotRegisteredError",
    "RecipeLoaderFn",
    "UnmappedBankIdError",
    "bank_paths_from_manifest",
    "bank_paths_from_phase",
    "confusion_by_source",
    "confusion_from_frame",
    "feature_group_from_frame",
    "feature_groups_by_source",
    "load_bar_chart_distances",
    "load_curation_summary_table",
    "load_feature_groups",
    "load_group_banks",
    "load_prediction_groups",
    "load_trace_pair_gallery",
    "load_training_curve",
    "prediction_group_from_bank",
    "prediction_group_from_frame",
    "prediction_groups_by_source",
    "register_loader",
    "resolve_bank_paths",
    "resolve_recipe_data",
    "scatter_series_by_source",
    "scatter_series_from_frame",
    "training_curve_from_run",
]
