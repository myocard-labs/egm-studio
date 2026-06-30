"""Tests for the shared ``layout.features`` selection helper.

Exercised through both call sites too (feature-distribution-overlay's
``test_layout_features_*`` + the bar-chart loader's subset assertion); these
pin the helper directly.
"""

from __future__ import annotations

import pytest
from myocard_egm_data.phases import FigureSpec

from myocard_egm_studio.charts.matplotlib.selection import select_layout_features

_AVAILABLE = ["alpha", "beta", "gamma"]


def _spec(features: object | None = None) -> FigureSpec:
    payload: dict[str, object] = {
        "schema_version": "1",
        "id": "fig_selection_test",
        "description": "layout.features selection test",
        "recipe": "feature-distribution-overlay",
        "output": {"format": "png", "path": "out.png"},
    }
    if features is not None:
        payload["layout"] = {"features": features}
    return FigureSpec.model_validate(payload)


def test_absent_returns_all_in_order() -> None:
    """No layout.features -> all available names, in order."""
    assert select_layout_features(_spec(), _AVAILABLE) == _AVAILABLE


def test_subset_in_requested_order() -> None:
    """A subset is returned in the requested order, not the available order."""
    assert select_layout_features(_spec(["gamma", "alpha"]), _AVAILABLE) == ["gamma", "alpha"]


def test_unknown_warns_and_skips() -> None:
    """An unknown name warns and is dropped; valid ones remain."""
    with pytest.warns(UserWarning, match=r"unknown layout\.features"):
        assert select_layout_features(_spec(["alpha", "zzz"]), _AVAILABLE) == ["alpha"]


def test_all_unknown_raises() -> None:
    """No valid names is an error, not a warn-and-continue."""
    with pytest.raises(ValueError, match="none of the requested"):
        select_layout_features(_spec(["zzz"]), _AVAILABLE)


def test_non_list_raises() -> None:
    """layout.features must be a list (a bare string is rejected)."""
    with pytest.raises(ValueError, match="must be a list"):
        select_layout_features(_spec("alpha"), _AVAILABLE)
