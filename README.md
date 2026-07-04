# myocard-egm-studio

> Desktop application for intracardiac EGM signal exploration, ML
> training-result diagnostics, and reproducible paper-figure generation.

Part of the [myocard-labs](https://github.com/myocard-labs) cardiac
signal-processing toolkit.

---

## Why

`myocard-egm-studio` is the consumer-facing desktop app of the myocard-labs
stack. It loads the HDF5 banks, JSON training records, and predictions banks
the producers write — always through `myocard-egm-data` against
`myocard-egm-contracts` schemas, never raw file I/O — and turns them into an
interactive analysis surface plus publication-ready figures.

Three modes from one shell:

- **Signal exploration** — query, filter, and inspect EGM traces by any
  combination of trace-level features (peak-to-peak, sample entropy, dominant
  frequency, ...). Filter-and-sort-first, not browse-the-whole-bank.
- **ML diagnostics** — open a training run (`run.json` + `metrics.csv` +
  predictions bank), inspect failure cases, and surface the most informative
  examples by predicted probability or model disagreement.
- **Paper-figure prep** — build publication-quality, reproducible figures from
  per-figure JSON specs, iterated interactively and regenerable headlessly.

A three-layer rendering split keeps the figure code framework-agnostic:
`analysis/` (pure numpy / pandas / scipy / egm-features computation — no Qt, no
matplotlib) feeds `charts/` (matplotlib for static export, pyqtgraph for the
GUI), which `figures/` exposes as a thin headless `render()`. The Qt shell
is a frontend on top; the same `render()` powers the `egm-studio-render` CLI
with no shell — so the figure path runs in notebooks and CI without a display.

Unlike the leaf libraries, egm-studio sits at the bottom of the dependency
graph: it consumes `myocard-egm-contracts`, `myocard-egm-data`, and
`myocard-egm-features`, and reads the banks the producers (`egm-classifier`,
`synthetic-egm-pipeline`, `iafdb-pipeline`) write — but depends on none of the
producers directly.

---

## Install

From PyPI (when published):

```bash
pip install myocard-egm-studio
```

From source during pre-1.0 iteration:

```bash
pip install git+https://github.com/myocard-labs/egm-studio.git
```

Editable install for development:

```bash
git clone https://github.com/myocard-labs/egm-studio.git
cd egm-studio
pip install -e ".[dev]"
pre-commit install
```

Runtime deps: `myocard-egm-contracts`, `myocard-egm-data`,
`myocard-egm-features` (pinned to git tags pre-1.0), plus `matplotlib`,
`numpy`, `pandas`, `scipy`, and — added with the Block 4 Qt shell — `PySide6`
and `pyqtgraph`.

---

## Programmatic usage

egm-studio is primarily a desktop app, but its figure-generation core is
framework-agnostic and importable — the same `render` the GUI and the
`egm-studio-render` CLI call:

```python
from myocard_egm_data.banks import load_classifier_bank
from myocard_egm_data.phases import load_figure_spec
from myocard_egm_studio.figures import render
from myocard_egm_studio.loaders import prediction_group_from_bank

# A figure_spec names a recipe + the bank ids its groups draw from. Recipes are
# pure plotting, so render() takes the already-prepared data; build it from a
# predictions bank with the matching adapter.
spec = load_figure_spec("figure_specs/fig_prediction_histogram.json")
group = prediction_group_from_bank(load_classifier_bank("preds_synth.h5"), name="Synthetic val")
render(spec, data=[group])
```

The same renderer is a console script. A spec carries bank *ids*, not paths;
until the Block 7 phase-manifest resolves them, map each id to a file by hand
(a proto-manifest) with repeated `--bank ID=PATH` or a `--banks` JSON map:

```bash
# One bank id -> one file:
egm-studio-render fig_prediction_histogram.json \
  --bank lpred_synth_val_2026-06-25=preds_synth.h5 --bank upred_iafdb_2026-06-15=preds_iafdb.h5

# ...or a {bank_id: path} JSON map, plus an output override:
egm-studio-render fig_prediction_histogram.json --banks banks.json -o figure.pdf
```

`examples/bank_paths.example.json` is a starter map — copy it to a local
(git-ignored) `banks.json`, fill in absolute paths, and grow it as you render
each recipe. An already-rendered output is skipped unless you pass `--overwrite`.

The analysis layer stands alone too — pure functions over the egm-features
view-model, no GUI required:

```python
from myocard_egm_studio.analysis import distributions

ks = distributions.ks_distance(synthetic_feature_values, iafdb_feature_values)
```

---

## Module map

| Module | What's in it |
|---|---|
| `myocard_egm_studio.analysis` | Pure data computation (no rendering, no Qt): `distributions` (CDF / KS / Wasserstein / histogram / KDE), `aggregation` (between-group feature distance), `similarity` (per-feature nearest). |
| `myocard_egm_studio.view_model` | Prepared, Qt-free view data. `build_view_model` — the unified per-trace table joining identity + bank metadata + egm-features columns — `combine` (`combine_view_models` — pool loaded banks into one frame under a unique global `row_id`, the multi-bank result-list + detail key), `summary` (`bank_summary` — the Flow A landing's count / class balance / provenance), plus the Phase-tree view models: `phase_groups` (manifest → the ten role groups), `phase_status` (per-artifact existence + validation), `phase_actions` (right-click policy), `artifact_metadata` (file-level metadata). |
| `myocard_egm_studio.charts.matplotlib` | The publication (static) rendering backend + the recipe registry the dispatch fills. |
| `myocard_egm_studio.charts.pyqtgraph` | The interactive (GUI-embedded) rendering backend — pyqtgraph chart widgets that reuse `analysis/` and the shared `charts.inputs` / `charts.palette`, so a chart matches its matplotlib twin — plus a GUI-only `draw_feature_scatter` (a live `(feat_x, feat_y)` scatter coloured by source, no matplotlib twin). |
| `myocard_egm_studio.figures` | `render(spec, *, data) -> Path` — the thin headless dispatch over `charts/matplotlib`. Pure rendering; the data-loading step lives in `loaders/`. |
| `myocard_egm_studio.loaders` | Data-loading (ids/paths → in-memory inputs): `figure_inputs` (spec + `{id: path}` → recipe inputs + the permanent bank → recipe-input adapters), `feature_group` (`feature_group_from_frame` + `feature_groups_by_source` — view-model-frame → charts `FeatureGroup`(s), shared by the figure loader + the GUI summary grid; the by-source split feeds the multi-bank overlay — plus `scatter_series_by_source`, the same split into id-carrying `ScatterSeries` for the scatter view), and `manifest` (`bank_paths_from_phase` — a phase's `manifest.json` → `{artifact_id: path}`). |
| `myocard_egm_studio.gui` | The PySide6 desktop shell (Block 4): `app` (the `egm-studio` entry), `shell` (ADR-025 layout — collapsible sidebars + 3-mode switch), `theme` (dark / light / vibrant QSS), `preferences` (persisted theme via QSettings). `widgets/` holds the Block 5 trace-display primitive, the Block 6 right-rail Phase artifact tree, and the Block 7 composable filter / result list / `feature_grid` (the ADR-018 responsive distribution grid, which overlays one KDE / histogram curve per source with a legend + toggle) / `feature_scatter` (the interactive `(feat_x, feat_y)` scatter with axis pickers) / `bank_list` (the loaded-banks roster) / a shared `SourceLegend`; `views/signal_exploration` assembles the Signal-exploration mode as Summary (per-bank stats + the overlaid grid), Explore (filter → list → detail) and Scatter (click a point → the Explore detail) sub-tabs. Loading many banks pools them under one `row_id`, with a progress dialog spanning extraction + the view build. |
| `myocard_egm_studio.cli` | Console-script entry points: `render` (`egm-studio-render`). |

The Qt shell (`gui/`) landed in Block 4 (layout + theming); Block 5 added the
trace-display widgets (`gui/widgets/trace.py`) and the `charts/pyqtgraph/`
backend; Block 6 added the read-only Phase artifact tree
(`gui/widgets/phase_tree.py`, fed by the `view_model` phase modules); the mode
views that assemble them land in Blocks 7–10.
The figure-data loaders now live in `loaders/`; `egm-studio-render --phase
FOLDER` resolves a spec's bank ids through the phase manifest (the Block 6
reader), with `--bank` / `--banks` as the ad-hoc override — see
[`project/roadmap.md`](project/roadmap.md).

---

## Tests

```bash
pytest                  # full suite
pytest --cov            # with coverage
ruff check .            # lint
ruff format --check .   # format check
mypy                    # type check
```

CI runs the same checks on Python 3.10, 3.11, and 3.12 — see
`.github/workflows/ci.yml`. The pytest-qt GUI tests run headless under Qt's
**offscreen** platform — CI installs the Qt system libraries and sets
`QT_QPA_PLATFORM=offscreen`; set that variable too if you run the suite on a
machine with no display.

---

## Project status

Pre-v0.1.0; built across 14 blocks (see
[`project/roadmap.md`](project/roadmap.md)). **Blocks 2–6 have shipped.** The
headless figure pipeline (Blocks 2–3): the `charts/matplotlib/` foundation, the
`render(spec, *, data)` contract, the figure-data loaders (`egm-studio-render
--bank/--banks`), and all eight Phase-1.5 P0 recipes — `prediction-histogram`,
`feature-distribution-overlay`, `bar-chart-with-deltas`, `roc-curve-multi-line`,
`calibration-reliability-diagram`, `trace-pair-gallery`, `summary-table`, and
`training-curve` — render real banks with snapshot tests. The **Qt shell**
(Block 4): `egm-studio` launches the ADR-025 layout — collapsible sidebars, the
3-mode segmented control, and dark / light / vibrant themes that persist across
launches. **Block 5** added the interactive trace-display primitive — a
`TraceContainer` stacking N traces on a shared, pannable X-axis with a
time-scale slider and a metadata-driven selector — plus the `charts/pyqtgraph/`
backend (a feature-distribution chart visually equivalent to its matplotlib twin
over the same `analysis/` output). **Block 6** front-loads the meta-repo
integration: a read-only right-rail Phase tree that loads a phase's
`manifest.json` (through egm-data) into the ten role-based artifact groups, marks
each artifact with an existence / validation status dot, and offers role-aware
right-click actions — Explore signal plus a Show-metadata view that reads the
artifact's own file. The mode views that assemble these into end-user tools begin
in Block 7, so the shell opens but isn't yet a complete analysis tool. Pins
`myocard-egm-contracts v0.5.2`, `myocard-egm-data v0.4.2`, `myocard-egm-features
v0.1.1`.

- For the design rationale (the 25 ADRs, the three-layer rendering split, the
  layout + save models), see [`project/architecture.md`](project/architecture.md)
  and the ADR log [`project/design.md`](project/design.md).
- For the block-by-block implementation plan, see
  [`project/roadmap.md`](project/roadmap.md).
- The full user manual lands in Block 13 at `docs/usage.md`.
- For the broader refactor context, see
  `intracardiac-platform/project/project_plan.md`.

---

## Citation

If you use this software in academic work, please cite:

```bibtex
@software{klein_myocard_egm_studio_2026,
  author  = {Klein, Daniel},
  title   = {myocard-egm-studio: desktop analysis, ML diagnostics, and
             reproducible paper figures for intracardiac EGM data},
  year    = {2026},
  url     = {https://github.com/myocard-labs/egm-studio},
}
```

---

## License

MIT — see [LICENSE](LICENSE). Third-party software-license acknowledgements are
in [NOTICE](NOTICE).
