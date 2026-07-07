"""Generate the docs/usage.md screenshots headlessly (offscreen Qt).

Drives a real ``MainWindow`` off-screen and grabs the **whole shell** (menu bar +
mode switcher + side rails + main area) for each mode/state, then writes PNGs into
``docs/screenshots/`` under the names the manual's slots expect. Under
``QT_QPA_PLATFORM=offscreen`` the shots are clean widget content, no OS chrome.
Dark theme, 1200x820.

Run (from the repo root, in the offscreen-Qt venv). Groups run independently so a
single invocation stays quick:

    python scripts/capture_screenshots.py            # all groups
    python scripts/capture_screenshots.py signal ml  # just these

Demo data comes from ``banks/``. The training-curve panel (10) is fed synthesized
curves; everything else is real bank data. A fresh shell is built per mode group so
each only carries its relevant banks.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from myocard_egm_studio.charts.inputs import TrainingCurve
from myocard_egm_studio.gui.app import build_app
from myocard_egm_studio.gui.preferences import load_theme
from myocard_egm_studio.gui.theme import DEFAULT_THEME, apply_theme
from myocard_egm_studio.view_model.filtering import Condition, FilterSpec

REPO = Path(__file__).resolve().parent.parent
BANKS = REPO / "banks"
OUT = REPO / "docs" / "screenshots"
SIZE = (1200, 820)

_app = None


def _ctx():
    global _app
    if _app is None:
        _app = build_app([])
        apply_theme(_app, load_theme(DEFAULT_THEME))
    return _app


def _pump(n: int = 6) -> None:
    app = _ctx()
    for _ in range(n):
        app.processEvents()


def _wait(seconds: float) -> None:
    """Pump the event loop for ``seconds`` so a background worker (the Flow C preview
    resolve, a recalc) can finish and paint before we grab."""
    app = _ctx()
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)


def _new_window():
    from myocard_egm_studio.gui.shell import MainWindow

    _ctx()
    win = MainWindow()
    win.resize(*SIZE)
    win.show()
    _pump()
    return win


def _save(widget, name: str) -> None:
    widget.resize(*SIZE)
    _pump()
    OUT.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(OUT / name))
    print("  wrote", name)


def _open(win, fname: str, *, replace: bool) -> None:
    win._open_bank_explore(str(BANKS / fname), replace=replace)


def _first_row_id(frame) -> int:
    return int(frame["row_id"].iloc[0])


def _training_curve(seed: int) -> TrainingCurve:
    ep = np.arange(1, 31)
    rng = np.random.default_rng(seed)
    train = 0.7 * np.exp(-ep / 8) + 0.03 + rng.normal(0, 0.008, ep.size)
    val = 0.72 * np.exp(-ep / 8) + 0.06 + rng.normal(0, 0.012, ep.size)
    auroc = 0.5 + 0.49 * (1 - np.exp(-ep / 6)) + rng.normal(0, 0.004, ep.size)
    return TrainingCurve(
        epochs=ep,
        loss={"train": train, "val": val},
        metric={"AUROC": auroc},
        metric_name="AUROC",
        best_epoch=int(ep.size - 3),
    )


# --- Signal exploration (Flow A): 03 04 05 06 ---------------------------------
def group_signal() -> None:
    win = _new_window()
    _open(win, "synthegm_v1_baseline_1.classifier.h5", replace=True)
    _open(win, "synthegm_v1_noise_mixed_1.classifier.h5", replace=False)
    ev = win._explore_view

    ev.show_summary()
    _save(win, "03-signal-summary.png")

    ev.show_explore()
    _save(win, "04-signal-explore.png")

    # 05 detail + cross-bank compare: select a trace, then run the other-bank finder so
    #   the detail shows the pair (waveforms + per-feature deltas).
    rid = _first_row_id(ev._frame)
    ev.result_list.select_row_ids([rid])
    ev._detail.run_finder(0, rid)  # 0 = "Find similar in other bank"
    _pump()
    _save(win, "05-signal-detail.png")

    # 06 scatter with continuous axes (avoids the integer banding of zero_crossings)
    ev._tabs.setCurrentIndex(2)
    ev._scatter._x_combo.setCurrentText("spectral_centroid")
    ev._scatter._y_combo.setCurrentText("higuchi_fractal_dimension")
    _pump()
    _save(win, "06-signal-scatter.png")


# --- Noise (ADR-027): 07 ------------------------------------------------------
def group_noise() -> None:
    win = _new_window()
    win._open_noise_view(str(BANKS / "iafdb_noise_v1.h5"), "nbank_iafdb_v1")
    _pump(8)
    _save(win, "07-noise-mode.png")


# --- ML diagnostics (Flow B): 08 09 10 11 -------------------------------------
def group_ml() -> None:
    win = _new_window()
    _open(win, "lpred_synth_small.classifier.h5", replace=True)
    _open(win, "v1_baseline_1_test_pred.classifier.h5", replace=False)
    win._show_mode(2)  # ML diagnostics
    dv = win._diagnostics_view

    dv._tabs.setCurrentIndex(0)
    _save(win, "08-ml-output.png")
    dv._tabs.setCurrentIndex(1)
    _save(win, "09-ml-metrics.png")

    dv.set_runs([("v1", _training_curve(1)), ("v1.5", _training_curve(2))])
    dv._tabs.setCurrentIndex(2)
    _save(win, "10-ml-training.png")

    # 11 explore misclassifications: filter to the failures (FP/FN) through the real
    #   filter panel, then select one + find its nearest correctly-classified peer.
    spec = FilterSpec(
        (
            Condition("correctness_bucket", "==", "FP"),
            Condition("correctness_bucket", "==", "FN"),
        ),
        combine="or",
    )
    win._filter_panel.set_spec(spec)
    win._on_recalculate(spec)
    _wait(3)
    dv._tabs.setCurrentIndex(3)
    failures = win._explore_df[win._explore_df["correctness_bucket"].isin(["FP", "FN"])]
    if not failures.empty:
        rid = _first_row_id(failures)
        dv.result_list.select_row_ids([rid])
        dv._detail.run_finder(0, rid)  # 0 = nearest correctly-classified peer
        _pump()
    _save(win, "11-ml-explore.png")


# --- Paper-figure prep (Flow C): 12 -------------------------------------------
def group_figure() -> None:
    win = _new_window()
    win._show_mode(3)  # paper figures
    fv = win._figure_view
    # Map the spec's (dated) bank ids to small local banks so the preview renders;
    # the IAFDB group uses a synthetic stand-in for speed (illustrative shot only).
    fv.set_bank_paths(
        {
            "tbank_synthegm_v1_baseline_1_2026-06-27": str(
                BANKS / "synthegm_v1_baseline_1.classifier.h5"
            ),
            "upred_iafdb_sanchez_2026-06-27": str(
                BANKS / "synthegm_v1_noise_mixed_1.classifier.h5"
            ),
        }
    )
    fv.load_spec(REPO / "examples" / "feature_distribution_overlay_spec.json", preview=True)
    _wait(18)  # wait out the worker-thread resolve (feature extraction on 2 banks) + paint
    _save(win, "12-figure-prep.png")


# --- Shell-level: 01 first-launch, 02 overview, 14 phase tree -----------------
def group_shell() -> None:
    win = _new_window()
    _save(win, "01-first-launch.png")

    _open(win, "lpred_synth_small.classifier.h5", replace=True)
    _wait(3)
    _save(win, "02-shell-overview.png")

    win._load_phase_into_tree(str(REPO / "examples" / "example_phase"))
    _pump()
    _save(win, "14-phase-tree.png")


# --- Save-observation dialog: 13 ----------------------------------------------
def group_save() -> None:
    from myocard_egm_studio.gui.save_observation_dialog import SaveObservationDialog

    _ctx()
    dlg = SaveObservationDialog(
        summary=(
            "2 banks loaded  ·  filter: source == synthetic AND sample_entropy > 1.5  "
            "·  3 traces selected"
        ),
        parent_observations=[
            "obs_courtemanche_entropy_tail_2026-07-01",
            "obs_v1_5_desaturation_2026-07-03",
        ],
        title="Courtemanche adds a synthetic-only high-entropy region",
        description=(
            "The Courtemanche cell-model swap pushes sample_entropy into a range IAFDB "
            "never reaches; those high-entropy synthetic traces cluster on their own in "
            "the (sample_entropy, peak_to_peak) scatter — a possible realism regression "
            "to watch before training."
        ),
    )
    dlg.resize(560, 420)
    _pump()
    OUT.mkdir(parents=True, exist_ok=True)
    dlg.grab().save(str(OUT / "13-save-observation.png"))
    print("  wrote 13-save-observation.png")


GROUPS = {
    "signal": group_signal,
    "noise": group_noise,
    "ml": group_ml,
    "figure": group_figure,
    "shell": group_shell,
    "save": group_save,
}


def main() -> int:
    wanted = sys.argv[1:] or list(GROUPS)
    for name in wanted:
        print(f"[{name}]")
        GROUPS[name]()
    print(f"done -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
