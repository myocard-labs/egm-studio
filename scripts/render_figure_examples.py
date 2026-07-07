"""Render good-vs-bad example figures for the usage.md figure-reading guide (§4).

Feeds each of the eight matplotlib recipes synthetic *good* and *bad* data through its
real example spec, so the manual shows exactly what a healthy vs. a problem figure looks
like. Output → ``docs/screenshots/figures/``. No Qt (matplotlib/Agg only).

    python scripts/render_figure_examples.py
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np
from myocard_egm_data.phases import load_figure_spec

import myocard_egm_studio.charts.matplotlib  # noqa: F401  (registers the recipes)
from myocard_egm_studio.charts.inputs import (
    BarChartData,
    FeatureGroup,
    PredictionGroup,
    TableData,
    TracePair,
    TracePairGallery,
    TrainingCurve,
)
from myocard_egm_studio.charts.matplotlib.registry import RECIPES
from myocard_egm_studio.charts.matplotlib.style import paper_style

REPO = Path(__file__).resolve().parent.parent
EX = REPO / "examples"
OUT = REPO / "docs" / "screenshots" / "figures"
RNG = np.random.default_rng(0)
LABELS = {0: "healthy", 1: "fibrotic"}
FEATURES = [
    "peak_to_peak",
    "zero_crossings",
    "activation_position",
    "sec_peak_count",
    "spectral_centroid",
    "spectral_entropy",
    "dominant_frequency",
    "sample_entropy",
    "shannon_entropy",
    "lempel_ziv_complexity",
    "higuchi_fractal_dimension",
]


def render(recipe: str, spec_file: str, data: object, out: str) -> None:
    spec = load_figure_spec(str(EX / spec_file))
    fig = RECIPES[recipe](data, spec)
    OUT.mkdir(parents=True, exist_ok=True)
    with paper_style():
        fig.savefig(str(OUT / out), dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", out)


# --- prediction-histogram -----------------------------------------------------
def _preds(name: str, probs: np.ndarray, labels: np.ndarray) -> PredictionGroup:
    return PredictionGroup(name, probs.astype(np.float64), labels.astype(np.int64), LABELS)


def prediction_histogram() -> None:
    n = 1500
    lab = RNG.integers(0, 2, n)
    good = np.where(lab == 1, RNG.beta(6, 1.6, n), RNG.beta(1.6, 6, n))  # bimodal
    bad = RNG.beta(28, 1.3, n)  # saturated near 1 regardless of label
    render(
        "prediction-histogram",
        "prediction_histogram_spec.json",
        [_preds("Model", good, lab)],
        "prediction-histogram-good.png",
    )
    render(
        "prediction-histogram",
        "prediction_histogram_spec.json",
        [_preds("Model", bad, lab)],
        "prediction-histogram-bad.png",
    )


# --- roc-curve-multi-line -----------------------------------------------------
def roc_curve_multi_line() -> None:
    n = 2000
    lab = RNG.integers(0, 2, n)
    strong = np.clip(np.where(lab == 1, RNG.beta(6, 2, n), RNG.beta(2, 6, n)), 1e-3, 1 - 1e-3)
    chance = np.clip(RNG.beta(2, 2, n), 1e-3, 1 - 1e-3)  # independent of label
    render(
        "roc-curve-multi-line",
        "roc_curve_multi_line_spec.json",
        [_preds("v1.5", strong, lab)],
        "roc-curve-multi-line-good.png",
    )
    render(
        "roc-curve-multi-line",
        "roc_curve_multi_line_spec.json",
        [_preds("v1", chance, lab)],
        "roc-curve-multi-line-bad.png",
    )


# --- calibration-reliability-diagram ------------------------------------------
def calibration_reliability_diagram() -> None:
    n = 3000
    probs = np.clip(RNG.beta(2, 2, n), 0.02, 0.98)
    cal = (RNG.random(n) < probs).astype(np.int64)  # calibrated: y ~ Bernoulli(prob)
    over_p = 0.5 + (probs - 0.5) * 0.35  # truth pulled toward 0.5 -> model over-confident
    over = (RNG.random(n) < over_p).astype(np.int64)
    render(
        "calibration-reliability-diagram",
        "calibration_reliability_diagram_spec.json",
        [_preds("calibrated", probs, cal)],
        "calibration-reliability-diagram-good.png",
    )
    render(
        "calibration-reliability-diagram",
        "calibration_reliability_diagram_spec.json",
        [_preds("over-confident", probs, over)],
        "calibration-reliability-diagram-bad.png",
    )


# --- feature-distribution-overlay ---------------------------------------------
def feature_distribution_overlay() -> None:
    def groups(divergent: bool) -> list[FeatureGroup]:
        iafdb = {f: RNG.normal(0.0, 1.0, 1500).astype(np.float64) for f in FEATURES}
        if divergent:
            synth = {f: RNG.normal(1.3, 0.6, 1500).astype(np.float64) for f in FEATURES}
        else:
            synth = {f: RNG.normal(0.05, 1.0, 1500).astype(np.float64) for f in FEATURES}
        return [FeatureGroup("Synthetic", synth), FeatureGroup("IAFDB", iafdb)]

    render(
        "feature-distribution-overlay",
        "feature_distribution_overlay_spec.json",
        groups(False),
        "feature-distribution-overlay-good.png",
    )
    render(
        "feature-distribution-overlay",
        "feature_distribution_overlay_spec.json",
        groups(True),
        "feature-distribution-overlay-bad.png",
    )


# --- bar-chart-with-deltas ----------------------------------------------------
def bar_chart_with_deltas() -> None:
    cats = [
        "peak_to_peak",
        "zero_crossings",
        "spectral_centroid",
        "sample_entropy",
        "higuchi_fd",
        "shannon_entropy",
    ]

    def bar(values: list[float]) -> BarChartData:
        return BarChartData(
            categories=cats,
            values=np.array(values, dtype=np.float64),
            baseline_index=0,
            value_label="KS distance to IAFDB",
        )

    render(
        "bar-chart-with-deltas",
        "bar_chart_with_deltas_spec.json",
        bar([0.06, 0.08, 0.05, 0.09, 0.07, 0.05]),
        "bar-chart-with-deltas-good.png",
    )
    render(
        "bar-chart-with-deltas",
        "bar_chart_with_deltas_spec.json",
        bar([0.41, 0.55, 0.37, 0.62, 0.48, 0.5]),
        "bar-chart-with-deltas-bad.png",
    )


# --- trace-pair-gallery -------------------------------------------------------
def _wave(*, width: float, noise: float) -> np.ndarray:
    t = np.linspace(0, 1, 200)
    spike = np.exp(-((t - 0.4) ** 2) / (2 * width**2))
    w = np.gradient(spike)  # bipolar-ish
    w = w / np.max(np.abs(w))
    return (w + RNG.normal(0, noise, t.size)).astype(np.float64)


def trace_pair_gallery() -> None:
    def gallery(similar: bool) -> TracePairGallery:
        pairs = []
        for _ in range(4):
            left = _wave(width=0.02, noise=0.02)
            right = _wave(width=0.02, noise=0.03) if similar else _wave(width=0.06, noise=0.09)
            delta = 0.03 if similar else 0.41
            pairs.append(
                TracePair(left=left, right=right, annotation=f"Δpeak_to_peak = {delta:.2f}")
            )
        return TracePairGallery(
            pairs=pairs,
            left_title="Synthetic",
            right_title="IAFDB",
            left_fs_hz=1000.0,
            right_fs_hz=1000.0,
        )

    render(
        "trace-pair-gallery",
        "trace_pair_gallery_spec.json",
        gallery(True),
        "trace-pair-gallery-good.png",
    )
    render(
        "trace-pair-gallery",
        "trace_pair_gallery_spec.json",
        gallery(False),
        "trace-pair-gallery-bad.png",
    )


# --- training-curve -----------------------------------------------------------
def training_curve() -> None:
    ep = np.arange(1, 31)

    def curve(overfit: bool) -> TrainingCurve:
        train = 0.7 * np.exp(-ep / 8) + 0.03 + RNG.normal(0, 0.006, ep.size)
        if overfit:
            val = 0.7 * np.exp(-ep / 6) + 0.05 + np.maximum(0, ep - 12) * 0.018
            best = 12
        else:
            val = 0.72 * np.exp(-ep / 8) + 0.06 + RNG.normal(0, 0.01, ep.size)
            best = int(ep.size - 3)
        auroc = 0.5 + 0.49 * (1 - np.exp(-ep / 6))
        return TrainingCurve(
            epochs=ep.astype(np.int64),
            loss={"train": train.astype(np.float64), "val": val.astype(np.float64)},
            metric={"AUROC": auroc.astype(np.float64)},
            metric_name="AUROC",
            best_epoch=best,
        )

    render("training-curve", "training_curve_spec.json", curve(False), "training-curve-good.png")
    render("training-curve", "training_curve_spec.json", curve(True), "training-curve-bad.png")


# --- summary-table (one example — a table has no good/bad) ---------------------
def summary_table() -> None:
    table = TableData(
        columns=["Record", "Channel", "Segments kept", "Dropped (saturated)", "Dropped (short)"],
        rows=[
            ["iaf1_svc", "CS 1-2", "1,284", "37", "12"],
            ["iaf1_svc", "CS 3-4", "1,301", "5", "9"],
            ["iaf2_svc", "CS 1-2", "1,190", "88", "14"],
            ["iaf2_svc", "CS 3-4", "1,255", "19", "7"],
        ],
        title="IAFDB noise curation summary",
    )
    render("summary-table", "iafdb_curation_summary_spec.json", table, "summary-table-example.png")


def main() -> int:
    for fn in (
        prediction_histogram,
        roc_curve_multi_line,
        calibration_reliability_diagram,
        feature_distribution_overlay,
        bar_chart_with_deltas,
        trace_pair_gallery,
        training_curve,
        summary_table,
    ):
        print(f"[{fn.__name__}]")
        fn()
    print(f"done -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
