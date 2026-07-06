"""Block 11 profiling harness — where do the seconds go on a bank load?

Runs the real pipeline stages and reports per-stage wall time + memory:
  read (load_classifier_bank) -> extract (build_view_model) -> traces_from_bank
  -> combine_view_models -> the downstream set_results rebuild (summary-grid data
  prep + KDE, scatter series, result-table population).

Extraction is modelled from a small probe (per-trace ms, extrapolated) so we don't
wait minutes; the downstream stages run on synthetic frames at IAFDB scale (cheap,
no extraction) to test the large->small freeze hypothesis. Pass --bank PATH to run
read+extract+traces on a real bank instead of the probe.
"""

from __future__ import annotations

import argparse
import resource
import time

import numpy as np
import pandas as pd

# --- helpers ---------------------------------------------------------------


def _rss_mb() -> float:
    # ru_maxrss is KB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _timed(label: str, fn):
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    print(f"  {label:<34} {dt * 1000:9.1f} ms   (peak RSS {_rss_mb():7.0f} MB)")
    return out, dt


def _synth_bank(n_traces: int, t: int):
    """A tiny ClassifierBank with random traces, for the extraction probe."""
    from myocard_egm_data.banks import ClassifierBank, ClassifierBankMetaData, ClassifierTrace

    rng = np.random.default_rng(0)
    bid = "tbank_profile_probe_2026-07-06"
    traces = []
    for i in range(n_traces):
        sig = (np.sin(2 * np.pi * 5 * np.arange(t) / t) + rng.standard_normal(t) * 0.05).astype(
            np.float32
        )
        traces.append(
            ClassifierTrace(
                bank_id=bid,
                signal=sig,
                freq_hz=1000.0,
                amp_type="mv",
                split=None,
                label_truth=i % 2,
                prediction=None,
                trace_metadata={"patient_id": f"P{i % 20:02d}", "sim_id": i},
            )
        )
    md = ClassifierBankMetaData(bank_id=bid, bank_type="synthetic", bank_path="x", bank_metadata={})
    return ClassifierBank(id=bid, banks=[md], traces=traces, labels={0: "healthy", 1: "fibrotic"})


def _synth_frame(n: int, source: str) -> pd.DataFrame:
    """A per-bank view-model frame at N rows (random features), no extraction needed."""
    from myocard_egm_studio.view_model.builder import FEATURE_COLUMNS

    rng = np.random.default_rng(abs(hash(source)) % (2**32))
    data = {
        "trace_idx": np.arange(n),
        "source": source,
        "source_bank_id": source,
        "source_bank_type": "iafdb",
        "label": (np.arange(n) % 2),
        "label_name": np.where(np.arange(n) % 2 == 0, "healthy", "fibrotic"),
        "amp_type": "mv",
        "split": None,
        "patient_id": [f"P{i % 20:02d}" for i in range(n)],
        "sim_id": np.arange(n),
    }
    for col in FEATURE_COLUMNS:
        data[col] = rng.standard_normal(n).astype(np.float64)
    return pd.DataFrame(data)


# --- stages ----------------------------------------------------------------


def probe_extraction() -> None:
    from myocard_egm_studio.view_model.builder import build_view_model

    print("\n[EXTRACTION cost model] build_view_model on a probe bank")
    for t in (500, 1000):
        n = 32
        bank = _synth_bank(n, t)
        t0 = time.perf_counter()
        build_view_model(bank, source="probe")
        dt = time.perf_counter() - t0
        per = dt / n * 1000
        print(f"  T={t:<5} {n} traces: {dt * 1000:8.1f} ms total   ->  {per:6.1f} ms/trace")
        if t == 1000:
            for big_n in (2_000, 8_000, 66_000):
                print(f"      extrapolated to N={big_n:>6}:  {per * big_n / 1000:8.1f} s")


def probe_read(n: int, t: int) -> None:
    import tempfile
    from pathlib import Path

    from myocard_egm_data.banks import load_classifier_bank, write_classifier_bank

    print(f"\n[READ] write+load a synthetic HDF5 bank (N={n}, T={t})")
    bank = _synth_bank(n, t)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bank.h5"
        _timed("write_classifier_bank", lambda: write_classifier_bank(bank, p))
        _timed("load_classifier_bank (read)", lambda: load_classifier_bank(p))


def probe_real_bank(path: str) -> None:
    """The true read -> extract -> traces path on a real bank (exact, not extrapolated)."""
    from myocard_egm_data.banks import load_classifier_bank

    from myocard_egm_studio.view_model.builder import build_view_model

    print(f"\n[REAL BANK] {path}")
    bank, _ = _timed("load_classifier_bank (read)", lambda: load_classifier_bank(path))
    n = len(bank.traces)
    t = len(bank.traces[0].signal) if n else 0
    print(f"  traces: {n:,}   trace length T={t}")
    frame, dt = _timed(
        "build_view_model (extract features)", lambda: build_view_model(bank, source="real")
    )
    if n:
        print(f"  ->  {dt / n * 1000:.2f} ms/trace   (frame: {len(frame.index):,} rows)")


def probe_downstream(n_large: int, n_small: int) -> None:
    from myocard_egm_studio.loaders import feature_groups_by_source, scatter_series_by_source
    from myocard_egm_studio.view_model.combine import combine_view_models

    print(
        f"\n[DOWNSTREAM rebuild] the large->small freeze suspect (large={n_large}, small={n_small})"
    )
    large = _synth_frame(n_large, "iafdb_large")
    small = _synth_frame(n_small, "synthetic_small")
    print(
        f"  large frame memory (deep):        {large.memory_usage(deep=True).sum() / 1e6:7.1f} MB"
    )

    combined, _ = _timed(
        "combine_view_models([large, small])", lambda: combine_view_models([large, small])
    )
    print(f"  combined rows: {len(combined.index):,}")
    _timed("feature_groups_by_source (KDE prep)", lambda: feature_groups_by_source(combined))
    _timed("scatter_series_by_source", lambda: scatter_series_by_source(combined))
    return combined


def probe_gui(combined: pd.DataFrame) -> None:
    print("\n[GUI rebuild] offscreen table + summary-grid render on the combined frame")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    from myocard_egm_studio.charts.pyqtgraph import DEFAULT_STYLE
    from myocard_egm_studio.gui.widgets import FeatureDistributionGrid, ResultList
    from myocard_egm_studio.loaders import feature_groups_by_source

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    rl = ResultList()
    _timed("ResultList.set_frame (table populate)", lambda: rl.set_frame(combined))
    grid = FeatureDistributionGrid(DEFAULT_STYLE)
    groups = feature_groups_by_source(combined)
    _timed("FeatureDistributionGrid.set_groups (KDE)", lambda: grid.set_groups(groups))
    app.processEvents()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--large", type=int, default=66_000)
    ap.add_argument("--small", type=int, default=500)
    ap.add_argument("--read-n", type=int, default=4_000)
    ap.add_argument("--read-t", type=int, default=1_000)
    ap.add_argument("--skip-gui", action="store_true")
    ap.add_argument("--bank", default=None, help="run the true read+extract path on a real bank")
    args = ap.parse_args()

    print(f"start RSS: {_rss_mb():.0f} MB")
    if args.bank:
        probe_real_bank(args.bank)
    else:
        probe_extraction()
        probe_read(args.read_n, args.read_t)
    combined = probe_downstream(args.large, args.small)
    if not args.skip_gui:
        probe_gui(combined)
    print(f"\nfinal peak RSS: {_rss_mb():.0f} MB")


if __name__ == "__main__":
    main()
