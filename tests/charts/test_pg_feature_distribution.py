"""Tests for the pyqtgraph feature-distribution recipe (charts/pyqtgraph).

The recipe reuses ``analysis/distributions`` (same as the matplotlib recipe), so
these check the widget assembles correctly and that both backends draw from the
one shared palette — the numeric curve tests already live with ``analysis``.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pytest
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import FeatureGroup
from myocard_egm_studio.charts.pyqtgraph import feature_distribution_overlay


def _groups() -> list[FeatureGroup]:
    feats = ("peak_to_peak", "sample_entropy")
    return [
        FeatureGroup(
            name=name,
            values={f: np.random.default_rng(seed).normal(shift, 1.0, 200) for f in feats},
            units={"peak_to_peak": "mV"},
        )
        for name, shift, seed in (("Synthetic", 0.0, 1), ("IAFDB", 0.5, 2))
    ]


def _panel_count(widget: pg.GraphicsLayoutWidget) -> int:
    """PlotItems in the layout — excludes the shared top legend row."""
    return sum(1 for item in widget.ci.items if isinstance(item, pg.PlotItem))


def test_builds_one_panel_per_feature(qtbot: QtBot) -> None:
    widget = feature_distribution_overlay(_groups())
    qtbot.addWidget(widget)
    assert _panel_count(widget) == 2


def test_features_arg_curates_panels(qtbot: QtBot) -> None:
    widget = feature_distribution_overlay(_groups(), features=["sample_entropy"])
    qtbot.addWidget(widget)
    assert _panel_count(widget) == 1


def test_histogram_kind_builds(qtbot: QtBot) -> None:
    widget = feature_distribution_overlay(_groups(), kind="histogram", annotate="wasserstein")
    qtbot.addWidget(widget)
    assert _panel_count(widget) == 2


def test_empty_input_rejected() -> None:
    with pytest.raises(ValueError, match="at least one FeatureGroup"):
        feature_distribution_overlay([])


def test_palette_shared_with_matplotlib_backend() -> None:
    """Both backends resolve group colours through the one charts.palette."""
    from myocard_egm_studio.charts.matplotlib.style import color_for as mpl_color_for
    from myocard_egm_studio.charts.palette import color_for as shared_color_for

    assert [mpl_color_for(i) for i in range(10)] == [shared_color_for(i) for i in range(10)]
