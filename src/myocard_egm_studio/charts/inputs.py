"""Prepared recipe inputs — the data contract between loaders and recipes.

A recipe is pure plotting: it takes one of these already-prepared inputs (never
a bank path or a raw HDF5 file) plus the FigureSpec, and returns a Figure. The
headless renderer's data-loading step (Block 7) is what turns a spec's
``inputs.groups`` bank ids into these structures; until that lands, tests and
callers build them in memory.

They live at the ``charts/`` level (not under a backend, not in egm-contracts):
both the matplotlib and pyqtgraph backends consume the same prepared inputs, so
one loader can feed either. They're egm-studio-internal figure-data shapes rather
than a cross-repo schema. One input type per recipe family.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "BarChartData",
    "FeatureGroup",
    "PredictionGroup",
    "TableData",
    "TracePair",
    "TracePairGallery",
    "TrainingCurve",
]


@dataclass(frozen=True)
class PredictionGroup:
    """One named group of model output probabilities for ``prediction-histogram``.

    Attributes
    ----------
    name
        Legend / panel label (e.g. ``"Synthetic val"``, ``"IAFDB"``).
    probs
        ``(N,)`` predicted probability of the positive class, in ``[0, 1]``.
    labels
        Optional ``(N,)`` integer truth labels. When present the recipe facets
        the histogram by class; ``None`` (the IAFDB shape) draws one
        distribution with no class split.
    label_names
        Optional ``{int: str}`` map for the class legend (e.g.
        ``{0: "healthy", 1: "fibrotic"}``). Used only when ``labels`` is set.
    """

    name: str
    probs: NDArray[np.float64]
    labels: NDArray[np.int64] | None = None
    label_names: dict[int, str] | None = None


@dataclass(frozen=True)
class FeatureGroup:
    """One named group's per-feature value arrays for ``feature-distribution-overlay``.

    Attributes
    ----------
    name
        Legend / source label (e.g. ``"Synthetic v1.5"``, ``"IAFDB"``).
    values
        ``{feature_name: (N,) float array}`` — one entry per egm-features bundle
        column. Every group in a figure shares the same feature keys (the loader
        builds them from ``view_model.FEATURE_COLUMNS``); ``N`` may differ across
        groups (banks differ in size), which is why each panel is
        density-normalized rather than count-based.
    units
        Optional ``{feature_name: unit}`` for the subset of features that carry a
        unit (e.g. ``{"peak_to_peak": "mV", "spectral_centroid": "Hz"}``);
        features absent are unitless. The loader fills it via
        ``view_model.feature_units`` (so ``peak_to_peak`` tracks the bank's
        ``amp_type``) and the recipe labels each panel's x-axis from it.
    """

    name: str
    values: dict[str, NDArray[np.float64]]
    units: dict[str, str] | None = None


@dataclass(frozen=True)
class BarChartData:
    """A single bar series for the ``bar-chart-with-deltas`` recipe.

    Generic by design — the F-1.5.3 loader fills it with per-intervention
    aggregate sim-realism distances, but the same recipe is reused for counts,
    accuracies, etc. (one value per category).

    Attributes
    ----------
    categories
        One label per bar (e.g. the intervention / synthetic-variant names).
    values
        ``(K,)`` bar heights, aligned with ``categories``.
    errors
        Optional ``(K,)`` symmetric error-bar magnitudes, aligned with values.
    baseline_index
        Optional index into ``categories`` whose value is the delta reference.
        When set, the recipe draws a reference line at that value and annotates
        every other bar with its signed change from it (the "deltas").
    value_label
        y-axis label for the bar heights (e.g. ``"mean KS distance to IAFDB"``).
    """

    categories: list[str]
    values: NDArray[np.float64]
    errors: NDArray[np.float64] | None = None
    baseline_index: int | None = None
    value_label: str = ""


@dataclass(frozen=True)
class TracePair:
    """One row of the ``trace-pair-gallery``: a source trace beside its match.

    Attributes
    ----------
    left
        ``(L,)`` raw waveform samples of the source trace (e.g. a synthetic EGM).
    right
        ``(R,)`` raw waveform samples of the matched trace (e.g. its nearest
        IAFDB EGM). ``L`` and ``R`` may differ — the two banks need not share a
        sample count — but within a column every trace shares the bank's length.
    annotation
        Optional per-row label (e.g. the matched feature value + the gap to it),
        drawn in the row's left panel.
    """

    left: NDArray[np.float64]
    right: NDArray[np.float64]
    annotation: str = ""


@dataclass(frozen=True)
class TracePairGallery:
    """Prepared input for ``trace-pair-gallery`` — an Nx2 grid of paired traces.

    Attributes
    ----------
    pairs
        One :class:`TracePair` per gallery row. The loader selects a spread of
        source traces (along the match feature) and pairs each with its nearest
        trace in the pool bank.
    left_title
        Header for the left (source) column — the source group name (e.g.
        ``"Synthetic"``).
    right_title
        Header for the right (pool) column — the pool group name (e.g.
        ``"IAFDB"``).
    left_fs_hz
        Sample rate of the left column's bank, for a seconds x-axis; ``None``
        plots against sample index.
    right_fs_hz
        Sample rate of the right column's bank. Separate from ``left_fs_hz``
        because the two banks can differ in sample rate.
    """

    pairs: list[TracePair]
    left_title: str = "left"
    right_title: str = "right"
    left_fs_hz: float | None = None
    right_fs_hz: float | None = None


@dataclass(frozen=True)
class TableData:
    """A simple table for the ``summary-table`` recipe.

    Generic by design — the loader fills it with whatever it summarizes (the
    F-1.5.10 IAFDB curation provenance for now). Cells are pre-formatted strings,
    so the producer owns number formatting + units; the recipe only lays them out.

    Attributes
    ----------
    columns
        Column headers, drawn as a bold, shaded header row.
    rows
        One ``list[str]`` per body row; each row must have one cell per column.
    title
        Optional caption drawn above the grid.
    """

    columns: list[str]
    rows: list[list[str]]
    title: str = ""


@dataclass(frozen=True)
class TrainingCurve:
    """Per-epoch training curves for the ``training-curve`` recipe.

    Attributes
    ----------
    epochs
        ``(E,)`` epoch numbers — the shared x-axis of both panels.
    loss
        ``{series: (E,) values}`` loss curves for the top panel (e.g.
        ``{"train": ..., "val": ...}``). Non-finite entries (a missing epoch
        value) render as gaps.
    metric
        ``{series: (E,) values}`` selection-metric curves for the bottom panel
        (e.g. ``{"val": auroc}``).
    metric_name
        y-axis label for the metric panel (e.g. ``"AUROC"``).
    best_epoch
        Optional epoch number to mark with a vertical line (the selected /
        early-stopping epoch); ``None`` draws no marker.
    """

    epochs: NDArray[np.int64]
    loss: dict[str, NDArray[np.float64]]
    metric: dict[str, NDArray[np.float64]]
    metric_name: str = "metric"
    best_epoch: int | None = None
