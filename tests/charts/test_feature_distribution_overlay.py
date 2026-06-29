"""Tests for the ``feature-distribution-overlay`` matplotlib recipe.

A snapshot over the real 11-feature grid (compares only under ``pytest --mpl``;
a smoke test otherwise — see ``test_prediction_histogram`` for the baseline
policy), plus logic tests over small synthetic feature sets that don't depend on
any baseline image.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from matplotlib.figure import Figure
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.feature_distribution_overlay import (
    feature_distribution_overlay,
)
from myocard_egm_studio.charts.matplotlib.inputs import FeatureGroup

_TOL = 20.0


def _spec(
    *, styling: dict[str, object] | None = None, layout: dict[str, object] | None = None
) -> FigureSpec:
    """Minimal valid feature-distribution-overlay FigureSpec."""
    payload: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_feature_overlay_test",
        "description": "feature-distribution-overlay recipe test spec",
        "recipe": "feature-distribution-overlay",
        "output": {"format": "png", "path": "out.png"},
    }
    if styling is not None:
        payload["styling"] = styling
    if layout is not None:
        payload["layout"] = layout
    return FigureSpec.model_validate(payload)


def _groups(*, keys: tuple[str, ...], n_groups: int = 2, seed: int = 0) -> list[FeatureGroup]:
    """``n_groups`` FeatureGroups over ``keys``, each shifted + differently sized."""
    rng = np.random.default_rng(seed)
    groups: list[FeatureGroup] = []
    for g in range(n_groups):
        size = 200 + 100 * g
        values = {k: rng.normal(0.4 * g, 1.0 + 0.2 * g, size=size) for k in keys}
        groups.append(FeatureGroup(name=f"group{g}", values=values))
    return groups


def _realistic_groups() -> list[FeatureGroup]:
    """Two groups over the real 11 FEATURE_COLUMNS — the F-1.5.2 shape."""
    from myocard_egm_studio.view_model import FEATURE_COLUMNS, feature_units

    rng = np.random.default_rng(0)
    synth = {c: rng.normal(0.0, 1.0, size=400) for c in FEATURE_COLUMNS}
    iafdb = {c: rng.normal(0.6, 1.3, size=900) for c in FEATURE_COLUMNS}
    units = feature_units("mv")
    return [
        FeatureGroup("Synthetic", synth, units=units),
        FeatureGroup("IAFDB", iafdb, units=units),
    ]


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


@pytest.mark.mpl_image_compare(baseline_dir="baseline", tolerance=_TOL)
def test_feature_overlay_two_groups() -> Figure:
    """The canonical 11-panel synthetic-vs-IAFDB overlay with KS annotations."""
    return feature_distribution_overlay(_realistic_groups(), _spec(styling={"annotate": "ks"}))


# --------------------------------------------------------------------------- #
# Logic
# --------------------------------------------------------------------------- #


def _visible_axes(fig: Figure) -> list[Any]:
    return [ax for ax in fig.axes if ax.get_visible()]


def _has_distance_text(fig: Figure, prefix: str) -> bool:
    return any(t.get_text().startswith(prefix) for ax in fig.axes for t in ax.texts)


def test_one_visible_panel_per_feature() -> None:
    """The grid shows exactly one visible panel per feature (extras hidden)."""
    fig = feature_distribution_overlay(_groups(keys=("a", "b", "c")), _spec())
    assert len(_visible_axes(fig)) == 3


def test_empty_data_raises() -> None:
    """No groups is a caller error."""
    with pytest.raises(ValueError, match="at least one FeatureGroup"):
        feature_distribution_overlay([], _spec())


def test_mismatched_feature_keys_raises() -> None:
    """Groups must share the same feature keys."""
    good = _groups(keys=("a", "b"))[0]
    bad = FeatureGroup(name="other", values={"a": np.zeros(10), "x": np.zeros(10)})
    with pytest.raises(ValueError, match="same feature keys"):
        feature_distribution_overlay([good, bad], _spec())


def test_degenerate_feature_falls_back_to_histogram() -> None:
    """A constant feature (KDE-singular) renders via the histogram fallback rather
    than raising — the panel still draws."""
    rng = np.random.default_rng(2)
    flat = FeatureGroup("flat", {"f": np.zeros(50), "g": rng.normal(size=50)})
    varied = FeatureGroup("varied", {"f": rng.normal(size=50), "g": rng.normal(size=50)})
    fig = feature_distribution_overlay([flat, varied], _spec(styling={"kind": "kde"}))
    assert isinstance(fig, Figure)


def test_distance_annotation_only_for_two_groups() -> None:
    """KS annotation appears with exactly two groups, and not with three."""
    two = feature_distribution_overlay(_groups(keys=("a", "b"), n_groups=2), _spec())
    assert _has_distance_text(two, "KS=")
    three = feature_distribution_overlay(_groups(keys=("a", "b"), n_groups=3), _spec())
    assert not _has_distance_text(three, "KS=")


def test_wasserstein_annotation_when_requested() -> None:
    """``annotate='wasserstein'`` switches the per-panel distance label."""
    fig = feature_distribution_overlay(
        _groups(keys=("a", "b")), _spec(styling={"annotate": "wasserstein"})
    )
    assert _has_distance_text(fig, "W=")


def test_panel_xlabels_from_units() -> None:
    """A unit-bearing feature gets its unit as the x-label; unitless features none."""
    groups = [
        FeatureGroup(g.name, g.values, units={"peak_to_peak": "mV"})
        for g in _groups(keys=("peak_to_peak", "zero_crossings"))
    ]
    fig = feature_distribution_overlay(groups, _spec())
    xlabel_by_title = {ax.get_title(): ax.get_xlabel() for ax in fig.axes if ax.get_visible()}
    assert xlabel_by_title["peak_to_peak"] == "mV"
    assert xlabel_by_title["zero_crossings"] == ""


def test_layout_features_selects_subset_in_order() -> None:
    """layout.features renders only the named features, in the requested order."""
    fig = feature_distribution_overlay(
        _groups(keys=("a", "b", "c")), _spec(layout={"features": ["c", "a"]})
    )
    titles = [ax.get_title() for ax in _visible_axes(fig)]
    assert titles == ["c", "a"]


def test_layout_features_unknown_warns_and_skips() -> None:
    """An unknown feature name warns and is skipped; valid ones still render."""
    with pytest.warns(UserWarning, match=r"unknown layout\.features"):
        fig = feature_distribution_overlay(
            _groups(keys=("a", "b")), _spec(layout={"features": ["a", "zzz"]})
        )
    assert [ax.get_title() for ax in _visible_axes(fig)] == ["a"]


def test_layout_features_all_unknown_raises() -> None:
    """If no requested feature exists, that's an error (nothing to plot)."""
    with pytest.raises(ValueError, match="none of the requested"):
        feature_distribution_overlay(_groups(keys=("a", "b")), _spec(layout={"features": ["zzz"]}))


def test_unknown_kind_warns_and_falls_back() -> None:
    """A typo in styling.kind warns (not a silent branch) and still renders."""
    with pytest.warns(UserWarning, match=r"unknown styling\.kind"):
        fig = feature_distribution_overlay(
            _groups(keys=("a", "b")), _spec(styling={"kind": "histgram"})
        )
    assert isinstance(fig, Figure)


def test_unknown_annotate_warns_and_falls_back_to_ks() -> None:
    """A typo in styling.annotate warns and falls back to the KS default."""
    with pytest.warns(UserWarning, match=r"unknown styling\.annotate"):
        fig = feature_distribution_overlay(
            _groups(keys=("a", "b")), _spec(styling={"annotate": "kolmogorov"})
        )
    assert _has_distance_text(fig, "KS=")
