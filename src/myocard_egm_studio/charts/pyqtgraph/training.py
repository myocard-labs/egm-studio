"""pyqtgraph ``training-curves`` overlay for Flow B — loss + metric vs epoch (B8f).

The GUI twin of the matplotlib ``training-curve`` recipe, extended from one run to a
multi-run overlay (the walkthrough's "add v1 baseline as a second run"): a top loss
panel over a bottom selection-metric panel, sharing the epoch x-axis. A single run
colours train vs val loss distinctly (the overfitting read) and marks the best /
early-stopping epoch; a multi-run overlay colours by run (val-loss + val-metric per
run) to stay legible. Non-finite epoch values render as gaps (``connect="finite"``).
"""

from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6 import QtCore, QtGui

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle


def _style_axes(plot: pg.PlotItem, style: PgChartStyle) -> None:
    pen = pg.mkPen(style.foreground)
    for name in ("left", "bottom"):
        axis = plot.getAxis(name)
        axis.setPen(pen)
        axis.setTextPen(pen)


def _dashed(color: str) -> QtGui.QPen:
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setStyle(QtCore.Qt.PenStyle.DashLine)
    pen.setCosmetic(True)  # dash measured in device pixels, not scaled by the view transform
    return pen


def training_curves_overlay(
    runs: Sequence[tuple[str, TrainingCurve]], *, style: PgChartStyle = DEFAULT_STYLE
) -> pg.GraphicsLayoutWidget:
    """Render the loss + metric training panels for one or more runs.

    ``runs`` is ``(run name, TrainingCurve)`` in load order, coloured by
    ``color_for(i)`` to match the roster. Empty ``runs`` yields the bare linked
    panels (the landing state).
    """
    widget = pg.GraphicsLayoutWidget()
    widget.setBackground(style.background)
    loss_plot = widget.addPlot(row=0, col=0)
    metric_plot = widget.addPlot(row=1, col=0)
    metric_plot.setXLink(loss_plot)
    for plot in (loss_plot, metric_plot):
        _style_axes(plot, style)
    loss_plot.addLegend(labelTextColor=style.foreground)
    loss_plot.setLabel("left", "loss", color=style.foreground)
    metric_plot.setLabel("bottom", "epoch", color=style.foreground)

    metric_name = "metric"
    if len(runs) == 1:
        # One run: colour train vs val distinctly (the overfitting read) + mark the best epoch.
        name, curve = runs[0]
        if curve.epochs.size:
            train_loss = curve.loss.get("train")
            val_loss = curve.loss.get("val")
            if train_loss is not None:
                loss_plot.plot(
                    curve.epochs, train_loss, pen=color_for(0), name="train", connect="finite"
                )
            if val_loss is not None:
                loss_plot.plot(
                    curve.epochs, val_loss, pen=color_for(1), name="val", connect="finite"
                )
            for series in curve.metric.values():
                metric_plot.plot(curve.epochs, series, pen=color_for(1), connect="finite")
            if curve.best_epoch is not None:
                loss_plot.addLine(x=curve.best_epoch, pen=_dashed(style.foreground))
                metric_plot.addLine(x=curve.best_epoch, pen=_dashed(style.foreground))
            metric_name = curve.metric_name
    else:
        # Multiple runs: colour by run (val-loss + val-metric per run) to keep the overlay legible.
        for i, (name, curve) in enumerate(runs):
            if curve.epochs.size == 0:
                continue
            color = color_for(i)
            val_loss = curve.loss.get("val")
            if val_loss is not None:
                loss_plot.plot(curve.epochs, val_loss, pen=color, name=name, connect="finite")
            for series in curve.metric.values():
                metric_plot.plot(curve.epochs, series, pen=color, connect="finite")
            metric_name = curve.metric_name
    metric_plot.setLabel("left", metric_name, color=style.foreground)
    return widget
