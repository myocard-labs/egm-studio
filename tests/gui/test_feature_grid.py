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


def test_set_groups_overlays_and_shows_legend(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    """Two groups overlay into the same 11 panels and reveal the legend."""
    grid = FeatureDistributionGrid()
    qtbot.addWidget(grid)
    a = feature_group_from_frame(build_view_model(tiny_classifier_bank, source="A"))
    b = feature_group_from_frame(build_view_model(tiny_unlabeled_bank, source="B"))
    grid.set_groups([a, b])
    assert len(grid.panels) == len(FEATURE_COLUMNS)  # overlaid, not doubled
    assert not grid._legend.isHidden()  # legend shown for 2+ groups
    grid.set_group(a)  # a single group hides the legend again
    assert grid._legend.isHidden()


def test_kind_defaults_to_kde_and_toggles(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    grid = _grid(qtbot, tiny_classifier_bank)
    assert grid.kind() == "kde"  # default
    seen: list[str] = []
    grid.kindChanged.connect(seen.append)
    grid._kind_combo.setCurrentIndex(1)  # Histogram
    assert grid.kind() == "histogram"
    assert seen == ["histogram"]


def test_set_groups_reports_progress_per_panel(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    """set_groups(progress=cb) ticks once per drawn panel — the Block 11 rebuild pump."""
    grid = FeatureDistributionGrid()
    qtbot.addWidget(grid)
    group = feature_group_from_frame(build_view_model(tiny_classifier_bank, source="Synthetic"))
    seen: list[tuple[int, int]] = []
    grid.set_groups([group], progress=lambda done, total: seen.append((done, total)))
    n = len(FEATURE_COLUMNS)
    assert seen == [(i + 1, n) for i in range(n)]  # (1,n)…(n,n), one per panel


def test_recenter_button_refits_panels(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    grid = _grid(qtbot, tiny_classifier_bank)
    vb = grid.panels[0].getPlotItem().getViewBox()
    vb.setRange(xRange=(1000, 2000), padding=0)  # zoom a panel far off its data
    grid._recenter_button.click()
    assert vb.viewRange()[0][1] < 1000  # re-fit toward the panel's data
