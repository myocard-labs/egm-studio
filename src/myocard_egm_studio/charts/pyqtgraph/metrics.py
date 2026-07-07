"""pyqtgraph metric charts for Flow B — ROC, reliability, confusion (B8f).

GUI-embedded twins of the matplotlib metric recipes (``roc-curve-multi-line`` and
``calibration-reliability-diagram``) plus a confusion-matrix heatmap (``analysis``
owns the counts; there is no paper recipe for it yet). All reuse
:mod:`...analysis.metrics`, so the live panels match the paper figures exactly.

Labeled data only: ROC / reliability / confusion all need ground truth, which the
IAFDB shape lacks. The caller (Flow B in ``"full"`` mode) guarantees every group
carries truth; a group that is unlabeled — or whose current subset has a single
class, where the metric is undefined — is skipped rather than raised, since mode
gating is the view's job.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6 import QtCore, QtGui

from myocard_egm_studio.analysis import metrics
from myocard_egm_studio.charts.inputs import ConfusionCounts, PredictionGroup
from myocard_egm_studio.charts.palette import color_for
from myocard_egm_studio.charts.pyqtgraph.style import DEFAULT_STYLE, PgChartStyle

_LUT_SIZE = 256
_TEXT_FLIP = 0.5  # count text flips to the background colour above this cell intensity
_MARKER = 6.0  # reliability point marker size


def _style_axes(plot: pg.PlotItem, style: PgChartStyle) -> None:
    """Pen the left + bottom axes + fill the ViewBox in the theme colours.

    The ViewBox background is set explicitly (not just the widget's) so the letterbox
    strip an aspect-locked square leaves in a wider panel stays the theme background
    instead of pyqtgraph's light default.
    """
    pen = pg.mkPen(style.foreground)
    for name in ("left", "bottom"):
        axis = plot.getAxis(name)
        axis.setPen(pen)
        axis.setTextPen(pen)
    plot.getViewBox().setBackgroundColor(style.background)


def _dashed(style: PgChartStyle) -> QtGui.QPen:
    """A dashed foreground pen for the chance / perfect-calibration guide.

    Cosmetic so the dash pattern is measured in device pixels: a non-cosmetic dashed
    pen has its pattern scaled by the aspect-locked view transform, which smears the
    diagonal into a filled wedge instead of a dashed line.
    """
    pen = QtGui.QPen(QtGui.QColor(style.foreground))
    pen.setStyle(QtCore.Qt.PenStyle.DashLine)
    pen.setCosmetic(True)
    return pen


def draw_roc(
    plot: pg.PlotItem,
    groups: Sequence[PredictionGroup],
    *,
    positive_label: int = 1,
    style: PgChartStyle = DEFAULT_STYLE,
) -> None:
    """Overlay each labelled group's ROC curve (with AUROC) + the chance diagonal."""
    _style_axes(plot, style)
    plot.addLegend(offset=(-8, 8), labelTextColor=style.foreground)
    plot.setLabel("bottom", "False positive rate", color=style.foreground)
    plot.setLabel("left", "True positive rate", color=style.foreground)
    plot.plot([0.0, 1.0], [0.0, 1.0], pen=_dashed(style))
    for i, group in enumerate(groups):
        if group.labels is None:
            continue
        try:
            fpr, tpr = metrics.roc_curve(group.labels, group.probs, positive_label=positive_label)
            auc = metrics.auroc(group.labels, group.probs, positive_label=positive_label)
        except ValueError:
            continue  # a single-class subset — ROC is undefined
        plot.plot(fpr, tpr, pen=color_for(i), name=f"{group.name}  AUROC={auc:.3f}")
    plot.setXRange(0.0, 1.0, padding=0.02)
    plot.setYRange(0.0, 1.0, padding=0.02)
    plot.getViewBox().setAspectLocked(True)


def draw_calibration(
    plot: pg.PlotItem,
    groups: Sequence[PredictionGroup],
    *,
    positive_label: int = 1,
    n_bins: int = 10,
    style: PgChartStyle = DEFAULT_STYLE,
) -> None:
    """Overlay each labelled group's reliability curve (with ECE) + the ``y = x`` line."""
    _style_axes(plot, style)
    plot.addLegend(offset=(8, -8), labelTextColor=style.foreground)
    plot.setLabel("bottom", "Mean predicted probability", color=style.foreground)
    plot.setLabel("left", "Observed positive fraction", color=style.foreground)
    plot.plot([0.0, 1.0], [0.0, 1.0], pen=_dashed(style))
    for i, group in enumerate(groups):
        if group.labels is None:
            continue
        try:
            mean_pred, obs_freq, _ = metrics.reliability_curve(
                group.labels, group.probs, positive_label=positive_label, n_bins=n_bins
            )
            ece = metrics.expected_calibration_error(
                group.labels, group.probs, positive_label=positive_label, n_bins=n_bins
            )
        except ValueError:
            continue
        color = color_for(i)
        plot.plot(
            mean_pred,
            obs_freq,
            pen=color,
            symbol="o",
            symbolSize=_MARKER,
            symbolBrush=color,
            symbolPen=color,
            name=f"{group.name}  ECE={ece:.3f}",
        )
    plot.setXRange(0.0, 1.0, padding=0.02)
    plot.setYRange(0.0, 1.0, padding=0.02)
    plot.getViewBox().setAspectLocked(True)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    color = QtGui.QColor(hex_color)
    return color.red(), color.green(), color.blue()


def _lut(background: str, foreground: str) -> NDArray[np.ubyte]:
    """A background->foreground colour ramp — count 0 fades into the panel, the peak
    reads in the theme's ink, so the heatmap works on either theme."""
    start = np.array(_rgb(background), dtype=np.float64)
    end = np.array(_rgb(foreground), dtype=np.float64)
    t = np.linspace(0.0, 1.0, _LUT_SIZE)[:, None]
    return (start + t * (end - start)).astype(np.ubyte)


#: Confusion-matrix cell modes: raw counts, whole-matrix %, per-true-row %, per-pred-col %.
CONFUSION_NORMS: tuple[str, ...] = ("row", "col", "overall", "count")


def _normalized_confusion(matrix: NDArray[np.float64], normalize: str) -> NDArray[np.float64]:
    """The per-cell display value for a mode: raw counts, or a fraction in ``[0, 1]``.

    ``"row"`` divides by each true-class total (recall on the diagonal); ``"col"`` by
    each predicted-class total (precision on the diagonal); ``"overall"`` by the grand
    total; ``"count"`` returns the raw counts. Empty rows / columns give 0 (no divide).
    """
    if normalize == "count":
        return matrix
    if normalize == "overall":
        total = float(matrix.sum())
        if total <= 0:
            return matrix
        return np.asarray(matrix / total, dtype=np.float64)
    axis = 1 if normalize == "row" else 0
    sums = matrix.sum(axis=axis, keepdims=True)
    out = np.zeros_like(matrix)
    np.divide(matrix, sums, out=out, where=sums > 0)
    return out


def draw_confusion(
    plot: pg.PlotItem,
    data: ConfusionCounts,
    *,
    normalize: str = "row",
    style: PgChartStyle = DEFAULT_STYLE,
) -> None:
    """Draw one confusion matrix as a labelled heatmap (rows = true, cols = predicted).

    ``normalize`` (one of :data:`CONFUSION_NORMS`) picks the cell metric: ``"row"`` /
    ``"col"`` percentages (recall / precision on the diagonal), ``"overall"`` percentage
    of all traces, or raw ``"count"``. Cells always shade by *relative* intensity within
    the panel (the largest cell reads full in the theme ink), so the diagonal stands out
    regardless of mode; the label shows the chosen metric. The source name titles the
    panel — the metrics view tiles one per source.
    """
    if normalize not in CONFUSION_NORMS:
        raise ValueError(f"normalize must be one of {CONFUSION_NORMS}, got {normalize!r}.")
    matrix = np.asarray(data.matrix, dtype=np.float64)
    k = matrix.shape[0]
    plot.setTitle(data.name, color=style.foreground)
    values = _normalized_confusion(matrix, normalize)
    peak = float(values.max()) if values.size else 0.0
    shade = values / peak if peak > 0 else values  # relative -> the top cell reads full

    image = pg.ImageItem()
    image.setImage(shade.T)  # ImageItem indexes [x, y]: x = predicted col, y = true row
    image.setLookupTable(_lut(style.background, style.foreground))
    image.setLevels((0.0, 1.0))
    plot.addItem(image)

    view = plot.getViewBox()
    view.invertY(True)  # true class 0 at the top, like a standard confusion matrix
    view.setAspectLocked(True)
    ticks = [[(i + 0.5, str(data.labels[i])) for i in range(k)]]
    plot.getAxis("bottom").setTicks(ticks)
    plot.getAxis("left").setTicks(ticks)
    plot.setLabel("bottom", "predicted", color=style.foreground)
    plot.setLabel("left", "true", color=style.foreground)
    _style_axes(plot, style)

    is_pct = normalize != "count"
    for i in range(k):
        for j in range(k):
            ink = style.background if shade[i, j] > _TEXT_FLIP else style.foreground
            text = f"{values[i, j] * 100:.0f}%" if is_pct else str(int(values[i, j]))
            label = pg.TextItem(text, color=ink, anchor=(0.5, 0.5))
            label.setPos(j + 0.5, i + 0.5)
            plot.addItem(label)
    plot.setXRange(0.0, float(k), padding=0)
    plot.setYRange(0.0, float(k), padding=0)
