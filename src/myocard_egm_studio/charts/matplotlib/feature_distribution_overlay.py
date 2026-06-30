"""``feature-distribution-overlay`` recipe — per-feature distribution comparison.

The project's primary sim-realism diagnostic (F-1.5.2): a small-multiples grid,
one panel per egm-features bundle feature, overlaying each group's distribution
(e.g. synthetic vs IAFDB). When exactly two groups are compared, each panel is
annotated with a scalar distance between them.

Data is a list of :class:`..inputs.FeatureGroup` (``{feature: values}`` per
group), built by ``figures/loaders.load_feature_groups`` from the per-trace
view-model. All groups share the same feature keys.

Per panel:

- **Density, not counts.** Banks differ wildly in size (a few hundred synthetic
  traces vs tens of thousands of IAFDB segments), so each curve is a *density*:
  a KDE (the smooth default) or, when a feature is too degenerate for a KDE
  (fewer than two distinct values in some group), a density-histogram fallback.
  All groups in a panel share one x-range so the curves are comparable.
- **Distance annotation.** With exactly two groups the panel shows the
  per-feature distance between them — KS (unitless, default) or Wasserstein —
  the same primitives ``analysis/distributions`` exposes and that F-1.5.3 later
  aggregates. With one or 3+ groups the annotation is skipped (a pairwise
  distance isn't well-defined).
- **Axes.** The x-axis is labeled with the feature's unit (Hz, mV, ...) when it
  has one (``FeatureGroup.units`` from ``view_model.feature_units`` — so
  ``peak_to_peak`` is mV only for a raw-mV bank); count / entropy / fractal
  features are unitless and unlabeled. The y-axis is *probability density* (each
  curve integrates to 1, not a per-trace fraction), which is why the per-panel
  y-scales differ — a feature spread over a wider range sits lower.

Styling keys (``spec.styling``): ``kind`` (``"kde"`` | ``"histogram"``, default
``"kde"``), ``bins`` (histogram bin count, default 40), ``annotate``
(``"ks"`` | ``"wasserstein"`` | ``"none"``, default ``"ks"``). An unrecognised
``kind`` / ``annotate`` warns and falls back (to ``"histogram"`` / ``"ks"``)
rather than silently picking a branch. Note this config-level ``kind`` is
distinct from the *per-panel* fall back to a histogram when a feature is too
degenerate for a KDE — that one is data-driven, not a typo, so it stays quiet.

Layout key (``spec.layout``): ``features`` — an explicit ordered list of feature
names to show, to curate a paper figure down to the informative ones (unknown
names warn and are skipped); omit it to show every feature. Panels are framed (a
box each) and spaced so a dense grid stays legible.
"""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from myocard_egm_studio.analysis import distributions
from myocard_egm_studio.charts.matplotlib.inputs import FeatureGroup
from myocard_egm_studio.charts.matplotlib.registry import register
from myocard_egm_studio.charts.matplotlib.selection import select_layout_features
from myocard_egm_studio.charts.matplotlib.style import color_for, paper_style

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from myocard_egm_contracts._generated.python.figure_spec import FigureSpec
    from numpy.typing import NDArray

#: KDE evaluation-grid resolution per panel (points across the shared x-range).
_GRID_POINTS = 200

#: Per-panel figure size in inches (width, height). The whole grid is this times
#: the column / row count, sized so each panel stays readable once the
#: inter-panel spacing + per-panel border below are added.
_PANEL_WIDTH_IN = 2.6
_PANEL_HEIGHT_IN = 2.0

#: Extra spacing between panels, as a fraction of panel size, handed to the
#: constrained-layout engine (0 would pack them tight). Gives a dense
#: small-multiples grid room to breathe; pairs with the per-panel box border.
_PANEL_WSPACE = 0.10
_PANEL_HSPACE = 0.14

#: x-range pad applied when a feature is constant across every group, so a
#: degenerate panel still has a drawable, non-zero-width axis.
_DEGENERATE_PAD = 1.0

#: Accepted ``styling.kind`` / ``styling.annotate`` values + their defaults.
_VALID_KINDS = ("kde", "histogram")
_DEFAULT_KIND = "kde"
_FALLBACK_KIND = "histogram"  # always renderable; the safe landing for a bad kind
_VALID_ANNOTATIONS = ("ks", "wasserstein", "none")
_DEFAULT_ANNOTATE = "ks"
_DEFAULT_BINS = 40

#: Per-panel distance-annotation styling: axes-fraction position (upper-right),
#: font size, text color, and a semi-opaque rounded background so the label
#: stays legible where it overlaps the curves.
_ANNOT_POS = (0.97, 0.95)
_ANNOT_FONTSIZE = 7
_ANNOT_TEXT_COLOR = "0.2"
_ANNOT_BBOX = {"boxstyle": "round", "facecolor": "white", "alpha": 0.7, "edgecolor": "none"}


def _styling(spec: FigureSpec) -> tuple[str, int, str]:
    """Pull (kind, bins, annotate) from ``spec.styling``, validating the enums.

    An unrecognised ``kind`` / ``annotate`` *warns* and falls back rather than
    silently picking a branch, so a typo in a spec (e.g. ``"histgram"``) is
    visible instead of quietly rendering the wrong thing.
    """
    styling = spec.styling or {}

    kind = str(styling.get("kind", _DEFAULT_KIND))
    if kind not in _VALID_KINDS:
        warnings.warn(
            f"feature-distribution-overlay: unknown styling.kind {kind!r}; expected one "
            f"of {_VALID_KINDS}. Falling back to {_FALLBACK_KIND!r}.",
            stacklevel=2,
        )
        kind = _FALLBACK_KIND

    annotate = str(styling.get("annotate", _DEFAULT_ANNOTATE))
    if annotate not in _VALID_ANNOTATIONS:
        warnings.warn(
            f"feature-distribution-overlay: unknown styling.annotate {annotate!r}; expected "
            f"one of {_VALID_ANNOTATIONS}. Falling back to {_DEFAULT_ANNOTATE!r}.",
            stacklevel=2,
        )
        annotate = _DEFAULT_ANNOTATE

    bins = int(styling.get("bins", _DEFAULT_BINS))
    return kind, bins, annotate


def _finite(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """The finite entries of ``values`` (drop NaN / inf)."""
    return values[np.isfinite(values)]


def _panel_xrange(arrays: list[NDArray[np.float64]]) -> tuple[float, float] | None:
    """Pooled finite ``[min, max]`` across groups; ``None`` if nothing is finite."""
    pooled = np.concatenate([_finite(a) for a in arrays])
    if pooled.size == 0:
        return None
    lo, hi = float(pooled.min()), float(pooled.max())
    if hi <= lo:  # degenerate (all one value) — pad so a bar / curve is drawable
        hi = lo + _DEGENERATE_PAD
    return lo, hi


def _draw_feature_panel(
    ax: Axes,
    feature: str,
    data: list[FeatureGroup],
    *,
    kind: str,
    bins: int,
    annotate: str,
    units: dict[str, str],
) -> None:
    """Overlay each group's distribution for one feature, with optional distance."""
    arrays = [g.values[feature] for g in data]
    ax.set_title(feature)
    # Full box border per panel — the paper style drops top/right spines, but a
    # dense small-multiples grid reads better with each panel framed.
    for spine in ax.spines.values():
        spine.set_visible(True)
    unit = units.get(feature)
    if unit:  # label the x-axis only for features that carry a unit (Hz, mV, ...)
        ax.set_xlabel(unit)
    xr = _panel_xrange(arrays)
    if xr is None:  # nothing finite anywhere — leave the panel titled but empty
        return
    lo, hi = xr

    # KDE needs >= 2 distinct values in every group; otherwise fall back to a
    # density histogram for the whole panel so it stays internally consistent.
    use_kde = kind == "kde" and all(np.unique(_finite(a)).size >= 2 for a in arrays)
    if use_kde:
        grid = np.linspace(lo, hi, _GRID_POINTS)
        for i, arr in enumerate(arrays):
            _, density = distributions.kde(arr, grid=grid)
            ax.plot(grid, density, color=color_for(i))
    else:
        for i, arr in enumerate(arrays):
            if _finite(arr).size == 0:
                continue
            counts, edges = distributions.histogram(arr, bins=bins, range=(lo, hi), density=True)
            ax.stairs(counts, edges, color=color_for(i))

    ax.set_xlim(lo, hi)
    _annotate_distance(ax, arrays, annotate)


def _annotate_distance(ax: Axes, arrays: list[NDArray[np.float64]], annotate: str) -> None:
    """Per-panel scalar distance — only well-defined for exactly two groups."""
    if annotate == "none" or len(arrays) != 2:
        return
    try:
        if annotate == "wasserstein":
            text = f"W={distributions.wasserstein_distance(arrays[0], arrays[1]):.2g}"
        else:  # default: KS (unitless, comparable across features)
            text = f"KS={distributions.ks_distance(arrays[0], arrays[1]):.2f}"
    except ValueError:
        return  # a group had no finite values; skip rather than crash the figure
    ax.text(
        *_ANNOT_POS,
        text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=_ANNOT_FONTSIZE,
        color=_ANNOT_TEXT_COLOR,
        bbox=_ANNOT_BBOX,
    )


@register("feature-distribution-overlay")
def feature_distribution_overlay(data: list[FeatureGroup], spec: FigureSpec) -> Figure:
    """Render the ``feature-distribution-overlay`` figure. See the module docstring."""
    if not data:
        raise ValueError("feature-distribution-overlay needs at least one FeatureGroup.")
    all_features = list(data[0].values)
    if not all_features:
        raise ValueError("FeatureGroup.values is empty; no features to plot.")
    if any(set(g.values) != set(all_features) for g in data):
        raise ValueError(
            "all FeatureGroups must share the same feature keys; the loader builds "
            "them from view_model.FEATURE_COLUMNS."
        )
    features = select_layout_features(spec, all_features)
    kind, bins, annotate = _styling(spec)
    units = data[0].units or {}  # all groups share features; first group's units suffice

    n = len(features)
    ncols = math.ceil(math.sqrt(n))
    nrows = math.ceil(n / ncols)

    with paper_style():
        figure = Figure(figsize=(_PANEL_WIDTH_IN * ncols, _PANEL_HEIGHT_IN * nrows))
        figure.set_layout_engine("constrained", wspace=_PANEL_WSPACE, hspace=_PANEL_HSPACE)
        axes = np.atleast_1d(figure.subplots(nrows, ncols, squeeze=False)).ravel()
        for ax, feature in zip(axes[:n], features, strict=True):
            _draw_feature_panel(
                ax, feature, data, kind=kind, bins=bins, annotate=annotate, units=units
            )
        for ax in axes[n:]:
            ax.set_visible(False)  # blank the unused grid cells
        figure.supylabel("density")
        legend_handles = [
            Line2D([0], [0], color=color_for(i), label=group.name) for i, group in enumerate(data)
        ]
        figure.legend(handles=legend_handles, loc="outside upper center", ncol=len(data))
    return figure
