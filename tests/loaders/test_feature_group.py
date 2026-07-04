"""Unit tests for loaders.feature_group_from_frame (frame -> charts FeatureGroup)."""

from __future__ import annotations

from myocard_egm_data.banks import ClassifierBank

from myocard_egm_studio.loaders import feature_group_from_frame
from myocard_egm_studio.view_model import FEATURE_COLUMNS, build_view_model


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


def test_units_track_amp_type(tiny_classifier_bank: ClassifierBank) -> None:
    """Units come from the bank's amp_type: peak_to_peak is mV for a raw-mV bank,
    the spectral features are Hz, and the unitless features are absent."""
    group = feature_group_from_frame(build_view_model(tiny_classifier_bank, source="Synthetic"))
    assert group.units is not None
    assert group.units["peak_to_peak"] == "mV"
    assert group.units["spectral_centroid"] == "Hz"
    assert "sample_entropy" not in group.units
