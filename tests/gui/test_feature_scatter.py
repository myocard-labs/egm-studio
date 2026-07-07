"""pytest-qt tests for the interactive feature scatter (gui/widgets/feature_scatter, B7.9b).

Structure + behaviour, not pixels (ADR-013): the axis combos fill from the feature
set, picking an axis redraws + reports the pair, a point click emits its row_id, and
a preference restore doesn't echo. Headless under the offscreen QPA platform.
"""

from __future__ import annotations

import numpy as np
from myocard_egm_data.banks import ClassifierBank
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import ScatterSeries
from myocard_egm_studio.gui.theme.plots import chart_style
from myocard_egm_studio.gui.widgets import FeatureScatterView
from myocard_egm_studio.loaders import scatter_series_by_source
from myocard_egm_studio.view_model import FEATURE_COLUMNS, build_view_model, combine_view_models


def _big_series(n: int) -> list[ScatterSeries]:
    """One source with ``n`` finite points across the feature set (bigger than any cap)."""
    rng = np.random.default_rng(2)
    return [
        ScatterSeries(
            name="A",
            values={feature: rng.normal(0.0, 1.0, n) for feature in FEATURE_COLUMNS},
            ids=np.arange(n, dtype=np.int64),
        )
    ]


def _series(*pairs: tuple[ClassifierBank, str]) -> list[ScatterSeries]:
    combined = combine_view_models([build_view_model(bank, source=src) for bank, src in pairs])
    return scatter_series_by_source(combined)


def _view(qtbot: QtBot, *pairs: tuple[ClassifierBank, str]) -> FeatureScatterView:
    view = FeatureScatterView()
    qtbot.addWidget(view)
    view.set_series(_series(*pairs))
    return view


def test_axis_combos_fill_and_default_to_first_two(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    assert view._x_combo.count() == len(FEATURE_COLUMNS)
    assert (view.x_feature(), view.y_feature()) == (FEATURE_COLUMNS[0], FEATURE_COLUMNS[1])


def test_one_scatter_item_per_source(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "A"), (tiny_unlabeled_bank, "B"))
    assert len(view.items) == 2
    assert not view._legend.isHidden()  # legend shown for 2+ sources


def test_changing_axis_redraws_and_emits(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    seen: list[tuple[str, str]] = []
    view.axesChanged.connect(lambda x, y: seen.append((x, y)))
    view._y_combo.setCurrentIndex(3)  # pick the 4th feature for Y
    assert view.y_feature() == FEATURE_COLUMNS[3]
    assert seen == [(FEATURE_COLUMNS[0], FEATURE_COLUMNS[3])]
    assert len(view.items) == 1  # one source, redrawn (not doubled)


def test_click_point_emits_row_id(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "A"), (tiny_unlabeled_bank, "B"))
    seen: list[int] = []
    view.pointClicked.connect(seen.append)
    item = view.items[1]  # bank B's cloud
    spot = item.points()[2]
    item.sigClicked.emit(item, [spot], None)  # pyqtgraph (item, points, ev)
    assert seen == [int(spot.data())]  # the clicked point's global row_id


def test_set_axes_restores_without_emitting(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    seen: list[tuple[str, str]] = []
    view.axesChanged.connect(lambda x, y: seen.append((x, y)))
    view.set_axes(FEATURE_COLUMNS[2], FEATURE_COLUMNS[4])
    assert (view.x_feature(), view.y_feature()) == (FEATURE_COLUMNS[2], FEATURE_COLUMNS[4])
    assert seen == []  # a restore must not echo back to the saver


def test_restyle_keeps_points(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    view.set_style(chart_style("light"))
    assert len(view.items) == 1


def test_empty_series_clears(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    view.clear()
    assert view.items == []


def test_new_data_recenters_the_view(qtbot: QtBot, tiny_classifier_bank: ClassifierBank) -> None:
    """Feeding new series auto-fits the view to the new data (not the old zoom)."""
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    vb = view._plot.getPlotItem().getViewBox()
    vb.setRange(xRange=(1000, 2000), padding=0)  # zoom far off the data
    view.set_series(_series((tiny_classifier_bank, "Synthetic")))
    assert vb.viewRange()[0][1] < 1000  # refit back toward the data


def test_recenter_button_refits_the_view(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank
) -> None:
    view = _view(qtbot, (tiny_classifier_bank, "Synthetic"))
    vb = view._plot.getPlotItem().getViewBox()
    vb.setRange(xRange=(1000, 2000), padding=0)
    view._recenter_button.click()
    assert vb.viewRange()[0][1] < 1000  # the button re-fits to the points


def test_decimation_off_by_default_plots_every_point(qtbot: QtBot) -> None:
    view = FeatureScatterView()
    qtbot.addWidget(view)
    view.set_series(_big_series(600))
    assert view._decimate_check.isChecked() is False
    assert view._points_spin.isEnabled() is False  # the level control is inert while off
    assert len(view.items[0].points()) == 600  # every point drawn


def test_enabling_decimation_caps_points_and_enables_the_level(qtbot: QtBot) -> None:
    view = FeatureScatterView()
    qtbot.addWidget(view)
    view.set_series(_big_series(600))
    view._points_spin.setValue(500)
    view._decimate_check.setChecked(True)
    assert view._points_spin.isEnabled() is True  # toggling on makes the level live
    assert len(view.items[0].points()) == 500  # subsampled to the cap
    view._decimate_check.setChecked(False)
    assert len(view.items[0].points()) == 600  # back to every point


def test_lowering_the_level_re_subsamples(qtbot: QtBot) -> None:
    """With decimation on, a cap above the data plots all; lowering it thins the cloud."""
    view = FeatureScatterView()
    qtbot.addWidget(view)
    view.set_series(_big_series(600))
    view._decimate_check.setChecked(True)  # default level (5000) > 600 -> no effect yet
    assert len(view.items[0].points()) == 600
    view._points_spin.setValue(500)
    assert len(view.items[0].points()) == 500  # a level change while on re-caps


def test_bring_to_front_raises_z_and_persists_across_redraw(
    qtbot: QtBot, tiny_classifier_bank: ClassifierBank, tiny_unlabeled_bank: ClassifierBank
) -> None:
    """Raising a source stacks it above the others by z-value, kept through a redraw."""
    view = _view(qtbot, (tiny_classifier_bank, "A"), (tiny_unlabeled_bank, "B"))
    view.bring_to_front("A")  # A loads first (drawn under B by default) -> raise it
    z = {s.name: item.zValue() for s, item in zip(view._series, view.items, strict=True)}
    assert z["A"] > z["B"]
    view.set_series(_series((tiny_classifier_bank, "A"), (tiny_unlabeled_bank, "B")))  # redraw
    z2 = {s.name: item.zValue() for s, item in zip(view._series, view.items, strict=True)}
    assert z2["A"] > z2["B"]  # still in front after the rebuild
