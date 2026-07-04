"""Unit tests for loaders.feature_group + scatter_series builders (frame -> charts inputs)."""

from __future__ import annotations

import numpy as np
from myocard_egm_data.banks import ClassifierBank

from myocard_egm_studio.loaders import (
    feature_group_from_frame,
    feature_groups_by_source,
    prediction_group_from_frame,
    prediction_groups_by_source,
    scatter_series_by_source,
)
from myocard_egm_studio.view_model import FEATURE_COLUMNS, build_view_model, combine_view_models


def test_feature_group_carries_all_features(tiny_classifier_bank: ClassifierBank) -> None:
    """The group exposes exactly the 11 feature columns, one (N,) array each."""
    frame = build_view_model(tiny_classifier_bank, source="Synthetic")
    group = feature_group_from_frame(frame)
    assert set(group.values) == set(FEATURE_COLUMNS)
    assert all(arr.shape == (tiny_classifier_bank.n_traces,) for arr in group.values.values())


def test_name_defaults_to_source_then_override(tiny_classifier_bank: ClassifierBank) -> None:
    """``name`` defaults to the frame's ``source`` label; an explicit name wins."""
    frame = build_view_model(tiny_classifier_bank, source="Synthetic")
    assert feature_group_from_frame(frame).name == "Synthetic"
    assert feature_group_from_frame(frame, name="IAFDB").name == "IAFDB"


def test_groups_by_source_splits_per_bank(
    tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    """A combined multi-bank frame splits into one group per source, in load order."""
    combined = combine_view_models(
        [
            build_view_model(tiny_classifier_bank, source="A"),
            build_view_model(tiny_unlabeled_bank, source="B"),
        ]
    )
    groups = feature_groups_by_source(combined)
    assert [g.name for g in groups] == ["A", "B"]
    assert all(set(g.values) == set(FEATURE_COLUMNS) for g in groups)


def test_groups_by_source_single_and_empty(tiny_classifier_bank: ClassifierBank) -> None:
    frame = build_view_model(tiny_classifier_bank, source="Synthetic")
    (only,) = feature_groups_by_source(frame)
    assert only.name == "Synthetic"
    assert feature_groups_by_source(frame.iloc[0:0]) == []


def test_units_track_amp_type(tiny_classifier_bank: ClassifierBank) -> None:
    """Units come from the bank's amp_type: peak_to_peak is mV for a raw-mV bank,
    the spectral features are Hz, and the unitless features are absent."""
    group = feature_group_from_frame(build_view_model(tiny_classifier_bank, source="Synthetic"))
    assert group.units is not None
    assert group.units["peak_to_peak"] == "mV"
    assert group.units["spectral_centroid"] == "Hz"
    assert "sample_entropy" not in group.units


def test_scatter_series_by_source_carries_global_ids(
    tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    """One series per source, each carrying the global row_id slice (for click->trace)."""
    combined = combine_view_models(
        [
            build_view_model(tiny_classifier_bank, source="A"),
            build_view_model(tiny_unlabeled_bank, source="B"),
        ]
    )
    series = scatter_series_by_source(combined)
    assert [s.name for s in series] == ["A", "B"]
    assert all(set(s.values) == set(FEATURE_COLUMNS) for s in series)
    n_a = tiny_classifier_bank.n_traces
    assert series[0].ids.tolist() == list(range(n_a))  # bank A owns row_id 0..n_a-1
    assert series[1].ids.tolist() == list(range(n_a, n_a + tiny_unlabeled_bank.n_traces))


def test_scatter_series_units_and_empty(tiny_classifier_bank: ClassifierBank) -> None:
    frame = combine_view_models([build_view_model(tiny_classifier_bank, source="Synthetic")])
    (only,) = scatter_series_by_source(frame)
    assert only.name == "Synthetic"
    assert only.ids.tolist() == list(range(tiny_classifier_bank.n_traces))
    assert only.units is not None and only.units["peak_to_peak"] == "mV"
    assert scatter_series_by_source(frame.iloc[0:0]) == []


def test_prediction_group_carries_probs(tiny_predictions_bank: ClassifierBank) -> None:
    """The group pulls predicted_prob as one [0, 1] (N,) array; labels stay unset (B8e)."""
    frame = build_view_model(tiny_predictions_bank, source="v1")
    group = prediction_group_from_frame(frame)
    assert group.name == "v1"
    assert group.probs.shape == (tiny_predictions_bank.n_traces,)
    assert group.labels is None  # the Output overlay compares sources, not classes
    assert np.all((group.probs >= 0.0) & (group.probs <= 1.0))


def test_prediction_groups_by_source_splits_and_empty(
    tiny_predictions_bank: ClassifierBank, tiny_unlabeled_predictions_bank: ClassifierBank
) -> None:
    """One PredictionGroup per source, in load order; an empty frame yields none."""
    combined = combine_view_models(
        [
            build_view_model(tiny_predictions_bank, source="v1"),
            build_view_model(tiny_unlabeled_predictions_bank, source="v1.5"),
        ]
    )
    groups = prediction_groups_by_source(combined)
    assert [g.name for g in groups] == ["v1", "v1.5"]
    assert prediction_groups_by_source(combined.iloc[0:0]) == []
