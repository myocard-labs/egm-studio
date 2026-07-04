"""pytest-qt tests for the responsive feature-distribution grid (feature_grid, B7.7b).

Structure + behaviour, not pixels (ADR-013): one panel per feature, the scale
factor clamps + resizes panels + reports itself, and a theme restyle rebuilds.
Runs headless under the offscreen QPA platform.
"""

from __future__ import annotations

import pytest
from myocard_egm_data.banks import ClassifierBank
from pytestqt.qtbot import QtBot

from myocard_egm_studio.gui.theme.plots import chart_style
from myocard_egm_studio.gui.widgets import FeatureDistributionGrid
from myocard_egm_studio.loaders import feature_group_from_frame
from myocard_egm_studio.view_model import FEATURE_COLUMNS, build_view_model


def _grid(qtbot: QtBot, bank: ClassifierBank) -> FeatureDistributionGrid:
    grid = FeatureDistributionGrid()
    qtbot.addWidget(grid)
    grid.set_group(feature_group_from_frame(build_view_model(bank, source="Synthetic")))
    return grid


def test_one_panel_per_feature(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    grid = _grid(qtbot, tiny_classifier_bank)
    assert len(grid.panels) == len(FEATURE_COLUMNS)


def test_scale_factor_clamps_and_resizes(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    """The scale factor clamps to ADR-018's range; larger scale => wider panels."""
    grid = _grid(qtbot, tiny_classifier_bank)
    grid.set_scale_factor(0.1)  # below the minimum
    small_scale, small_w = grid.scale_factor(), grid.panels[0].maximumWidth()
    grid.set_scale_factor(9.0)  # above the maximum
    assert small_scale == pytest.approx(0.6)
    assert grid.scale_factor() == pytest.approx(2.0)
    assert grid.panels[0].maximumWidth() > small_w


def test_scale_slider_reports_factor(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    """Moving the slider emits scaleChanged with the resolved factor."""
    grid = _grid(qtbot, tiny_classifier_bank)
    seen: list[float] = []
    grid.scaleChanged.connect(seen.append)
    grid._scale_slider.setValue(grid._scale_slider.maximum())
    assert seen and seen[-1] == pytest.approx(2.0)


def test_restyle_rebuilds_panels(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    grid = _grid(qtbot, tiny_classifier_bank)
    grid.set_style(chart_style("light"))
    assert len(grid.panels) == len(FEATURE_COLUMNS)
