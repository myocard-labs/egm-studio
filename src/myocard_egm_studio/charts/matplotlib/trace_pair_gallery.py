"""``trace-pair-gallery`` recipe — an Nx2 grid of paired raw traces.

F-1.5.7, the synthetic-vs-IAFDB matched-trace gallery: each row pairs a source
(synthetic) trace with its most-similar trace from a pool bank (IAFDB), so a
reader can eyeball realism. Label-free — the pairing is over signal-level
egm-features (:mod:`...analysis.similarity`: per-feature nearest neighbour,
ADR-020; the joint multi-feature metric is the deferred open question).

This recipe is pure plotting: it receives a :class:`..inputs.TracePairGallery`
(the loader does the matching + pulls the raw signals) and lays the pairs out as
N rows x 2 columns — source on the left, match on the right, each row optionally
annotated with the feature value it was matched on. Amplitude y-ticks are hidden:
the gallery is for comparing morphology, and the two banks may not even share an
amplitude unit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.figure import Figure
from matplotlib.layout_engine import ConstrainedLayoutEngine
from numpy.typing import NDArray

from myocard_egm_studio.charts.matplotlib.inputs import TracePairGallery
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec

_FIG_WIDTH_IN = 6.0
_ROW_HEIGHT_IN = 1.15
_MIN_FIG_HEIGHT_IN = 1.8
_TRACE_LW = 0.8
_ANNOT_FONTSIZE = 7
#: Space between gallery rows (constrained-layout hspace, a fraction of panel
#: height), so each pair is visually separated from the one below.
_ROW_HSPACE = 0.45
#: Fraction of each panel's y-range left empty at the top, so the row annotation
#: sits above the waveform rather than on top of it.
_ANNOT_HEADROOM = 0.35


def _xlabel(fs_hz: float | None) -> str:
    return "time (s)" if fs_hz else "sample"


def _draw_trace(ax: Axes, signal: NDArray[np.float64], *, fs_hz: float | None, color: str) -> None:
    """Plot one waveform; hide the y-axis (amplitude scale isn't the comparison)."""
    x = np.arange(signal.size) / fs_hz if fs_hz else np.arange(signal.size, dtype=np.float64)
    ax.plot(x, signal, color=color, linewidth=_TRACE_LW)
    ax.set_yticks([])
    # Leave headroom at the top of the panel for the row annotation.
    bottom, top = ax.get_ylim()
    ax.set_ylim(bottom, top + _ANNOT_HEADROOM * (top - bottom))


@register("trace-pair-gallery")
def trace_pair_gallery(data: TracePairGallery, spec: FigureSpec) -> Figure:
    """Render the ``trace-pair-gallery`` figure. See the module docstring."""
    pairs = data.pairs
    if not pairs:
        raise ValueError("trace-pair-gallery needs at least one TracePair.")
    n = len(pairs)
    height = max(_ROW_HEIGHT_IN * n, _MIN_FIG_HEIGHT_IN)

    with paper_style():
        figure = Figure(
            figsize=(_FIG_WIDTH_IN, height),
            layout=ConstrainedLayoutEngine(hspace=_ROW_HSPACE),
        )
        # squeeze=False -> always a 2-D (n, 2) array, so n == 1 still indexes [r, c].
        # sharex="col": a column's traces share a length, so only the bottom row
        # shows the (shared) x ticks.
        axes = figure.subplots(n, 2, sharex="col", squeeze=False)
        for r, pair in enumerate(pairs):
            _draw_trace(axes[r, 0], pair.left, fs_hz=data.left_fs_hz, color=color_for(0))
            _draw_trace(axes[r, 1], pair.right, fs_hz=data.right_fs_hz, color=color_for(1))
            if pair.annotation:
                axes[r, 0].text(
                    0.02,
                    0.98,
                    pair.annotation,
                    transform=axes[r, 0].transAxes,
                    fontsize=_ANNOT_FONTSIZE,
                    va="top",
                    ha="left",
                )
        axes[0, 0].set_title(data.left_title)
        axes[0, 1].set_title(data.right_title)
        axes[-1, 0].set_xlabel(_xlabel(data.left_fs_hz))
        axes[-1, 1].set_xlabel(_xlabel(data.right_fs_hz))
    return figure
