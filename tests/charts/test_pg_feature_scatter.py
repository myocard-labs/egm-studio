"""Tests for the pyqtgraph feature scatter (charts/pyqtgraph/feature_scatter).

Structure + behaviour, not pixels (ADR-013): one scatter item per source, each
point exposes its ``row_id`` (so a click resolves to a trace), non-finite points
drop, and the axis labels carry units. Runs headless under the offscreen QPA.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pytestqt.qtbot import QtBot

from myocard_egm_studio.charts.inputs import ScatterSeries
from myocard_egm_studio.charts.pyqtgraph import draw_feature_scatter


def _series() -> list[ScatterSeries]:
    rng = np.random.default_rng(0)
    return [
        ScatterSeries(
            name=name,
            values={
                "peak_to_peak": rng.normal(shift, 1.0, 12),
                "sample_entropy": rng.normal(0.0, 1.0, 12),
            },
            ids=np.arange(start, start + 12, dtype=np.int64),
            units={"peak_to_peak": "mV"},
        )
        for name, shift, start in (("A", 0.0, 0), ("B", 0.6, 12))
    ]


def _plot(qtbot: QtBot) -> pg.PlotWidget:
    """A live PlotWidget the caller must keep referenced (holds the axes' C++ objects)."""
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    return widget


def test_draws_one_item_per_series(qtbot: QtBot) -> None:
    plot = _plot(qtbot)
    items = draw_feature_scatter(
        plot.getPlotItem(), _series(), x="peak_to_peak", y="sample_entropy"
    )
    assert len(items) == 2
    assert all(isinstance(item, pg.ScatterPlotItem) for item in items)


def test_points_carry_row_ids(qtbot: QtBot) -> None:
    """Each drawn point exposes its global row_id via the ScatterPlotItem data."""
    plot = _plot(qtbot)
    items = draw_feature_scatter(
        plot.getPlotItem(), _series(), x="peak_to_peak", y="sample_entropy"
    )
    assert [int(p.data()) for p in items[1].points()] == list(range(12, 24))


def test_non_finite_points_dropped(qtbot: QtBot) -> None:
    """A NaN/inf in either drawn axis drops the point (and its id) from the item."""
    plot = _plot(qtbot)
    series = [
        ScatterSeries(
            name="A",
            values={"x": np.array([1.0, np.nan, 3.0]), "y": np.array([1.0, 2.0, np.inf])},
            ids=np.array([10, 11, 12], dtype=np.int64),
        )
    ]
    (item,) = draw_feature_scatter(plot.getPlotItem(), series, x="x", y="y")
    assert [int(p.data()) for p in item.points()] == [10]  # only the first is finite in both


def test_axis_labels_use_units(qtbot: QtBot) -> None:
    widget = _plot(qtbot)  # bind the widget (not just the plot item) so the axes survive
    plot = widget.getPlotItem()
    draw_feature_scatter(plot, _series(), x="peak_to_peak", y="sample_entropy")
    assert "mV" in plot.getAxis("bottom").labelText  # x carries a unit
    assert plot.getAxis("left").labelText == "sample_entropy"  # y is unitless


def test_empty_series_clears(qtbot: QtBot) -> None:
    plot = _plot(qtbot)
    assert draw_feature_scatter(plot.getPlotItem(), [], x="peak_to_peak", y="sample_entropy") == []


def _big_series(n: int) -> list[ScatterSeries]:
    rng = np.random.default_rng(1)
    return [
        ScatterSeries(
            name="A",
            values={"x": rng.normal(0.0, 1.0, n), "y": rng.normal(0.0, 1.0, n)},
            ids=np.arange(n, dtype=np.int64),
        )
    ]


def test_max_points_none_plots_every_point(qtbot: QtBot) -> None:
    plot = _plot(qtbot)
    (item,) = draw_feature_scatter(plot.getPlotItem(), _big_series(200), x="x", y="y")
    assert len(item.points()) == 200  # default: decimation off, every point drawn


def test_max_points_caps_each_source(qtbot: QtBot) -> None:
    plot = _plot(qtbot)
    (item,) = draw_feature_scatter(
        plot.getPlotItem(), _big_series(200), x="x", y="y", max_points=50
    )
    assert len(item.points()) == 50  # subsampled down to the cap


def test_decimation_subset_is_deterministic(qtbot: QtBot) -> None:
    """The fixed seed keeps the subsample stable across redraws (no jitter on refilter)."""
    plot = _plot(qtbot)
    series = _big_series(200)
    (a,) = draw_feature_scatter(plot.getPlotItem(), series, x="x", y="y", max_points=50)
    (b,) = draw_feature_scatter(plot.getPlotItem(), series, x="x", y="y", max_points=50)
    assert sorted(int(p.data()) for p in a.points()) == sorted(int(p.data()) for p in b.points())
