"""Unit tests for loaders.feature_group_from_frame (frame -> charts FeatureGroup)."""

from __future__ import annotations

from myocard_egm_data.banks import ClassifierBank

from myocard_egm_studio.loaders import feature_group_from_frame, feature_groups_by_source
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
