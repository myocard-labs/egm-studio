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
- **ML diagnostics** — open an evaluated predictions bank and compare model
  runs across four tabs: output distributions (P(positive) per source), the
  metric suite (ROC, calibration, confusion), training curves, and an Explore
  tab that filters to the failure cases (FP / FN) and finds each one's nearest
  correctly-classified counterpart.
- **Paper-figure prep** — edit a per-figure JSON spec in a curated form beside a
  live WYSIWYG preview (a raster of the real recipe, pixel-identical to the export),
  then render to the spec's output. The same figures regenerate headlessly and from
  the Phase tree.

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
| `myocard_egm_studio.view_model` | Prepared, Qt-free view data. `build_view_model` — the unified per-trace table joining identity + bank metadata + egm-features columns (plus the `ml_outcomes` columns — predicted prob / class, correctness bucket, per-trace loss, calibration residual — when the bank carries predictions) — `combine` (`combine_view_models` — pool loaded banks into one frame under a unique global `row_id`, the multi-bank result-list + detail key), `summary` (`bank_summary` — the Flow A landing's count / class balance / provenance), `trace_detail` (the per-trace compare table, with per-feature deltas vs the source column), `similar` (`similar_in_other_sources` — the nearest trace in each other bank along a feature, over `analysis.similarity` — plus the Flow B finds `nearest_correct_pair` (a misclassification → its nearest correctly-classified opposite-label trace) and `within_class_neighborhood` (a trace's k nearest same-label peers)), plus the Phase-tree view models: `phase_groups` (manifest → the ten role groups), `phase_status` (per-artifact existence + validation), `phase_actions` (right-click policy), `artifact_metadata` (file-level metadata), `figure_output` (a figure spec's rendered-image path + per-figure existence, driving the dynamic Phase-tree figure menu). |
| `myocard_egm_studio.charts.matplotlib` | The publication (static) rendering backend + the recipe registry the dispatch fills. |
| `myocard_egm_studio.charts.pyqtgraph` | The interactive (GUI-embedded) rendering backend — pyqtgraph chart widgets that reuse `analysis/` and the shared `charts.inputs` / `charts.palette`, so a chart matches its matplotlib twin — plus GUI-only recipes with no matplotlib twin: `draw_feature_scatter` (a live `(feat_x, feat_y)` scatter coloured by source) and the Flow B primitives `output_distribution` (P(positive) per source), `metrics` (ROC / calibration / confusion, the last with a counts/overall%/row%/col% normalization), and `training` (loss + metric curves, train vs val by colour). |
| `myocard_egm_studio.figures` | `render(spec, *, data) -> Path` — the thin headless dispatch over `charts/matplotlib` — plus `preview_png` (the in-memory PNG raster the GUI preview shows, routed through the same `draw_figure` + `paper_style` pipeline as `render`, so preview is pixel-identical to the export). Pure rendering; the data-loading step lives in `loaders/`. |
| `myocard_egm_studio.loaders` | Data-loading (ids/paths → in-memory inputs): `figure_inputs` (spec + `{id: path}` → recipe inputs + the permanent bank → recipe-input adapters), `feature_group` (`feature_group_from_frame` + `feature_groups_by_source` — view-model-frame → charts `FeatureGroup`(s), shared by the figure loader + the GUI summary grid; the by-source split feeds the multi-bank overlay — plus `scatter_series_by_source`, the same split into id-carrying `ScatterSeries` for the scatter view), and `manifest` (`bank_paths_from_phase` — a phase's `manifest.json` → `{artifact_id: path}`). |
| `myocard_egm_studio.gui` | The PySide6 desktop shell (Block 4): `app` (the `egm-studio` entry), `shell` (ADR-025 layout — collapsible sidebars + 3-mode switch), `theme` (dark / light / vibrant QSS), `preferences` (persisted theme via QSettings). `widgets/` holds the Block 5 trace-display primitive, the Block 6 right-rail Phase artifact tree, and the Block 7 composable filter / result list / `feature_grid` (the ADR-018 responsive distribution grid, which overlays one KDE / histogram curve per source with a legend + toggle) / `feature_scatter` (the interactive `(feat_x, feat_y)` scatter with axis pickers) / `bank_list` (the loaded-banks roster) / a shared `SourceLegend`, and the Block 8 shared `explore_detail` (waveforms + Features / Model / Metadata table + pluggable finds, reused by both flows) plus the Flow B widgets `metrics_view` / `training_view` / `output_distribution` / `run_list`; `views/signal_exploration` assembles the Signal-exploration mode as Summary (per-bank stats + the overlaid grid), Explore (filter → list → detail, with a "find similar in other bank" per-feature compare — via the detail control or a result-list right-click) and Scatter (click a point → the Explore detail) sub-tabs, and `views/ml_diagnostics` assembles the ML-diagnostics mode as Output / Metrics / Training / Explore tabs over an evaluated bank — fed by the *same* Open-bank path (predictions auto-detected via `frame_eval_mode`) and narrowed by the *same* filter panel. The Block 9 Flow C widgets `figure_form` (the curated per-recipe spec editor) + `figure_preview` (the WYSIWYG raster panel) assemble in `views/paper_figure_prep`, which resolves a spec's banks off a worker thread and renders to the spec's own output (the Phase tree's Edit / View / Generate figure actions drive it). Loading many banks pools them under one `row_id`, with a progress dialog spanning extraction + the view build. |
| `myocard_egm_studio.cli` | Console-script entry points: `render` (`egm-studio-render`). |

The Qt shell (`gui/`) landed in Block 4 (layout + theming); Block 5 added the
trace-display widgets (`gui/widgets/trace.py`) and the `charts/pyqtgraph/`
backend; Block 6 added the read-only Phase artifact tree
(`gui/widgets/phase_tree.py`, fed by the `view_model` phase modules); the mode
views that assemble them shipped in Blocks 7 (Flow A signal exploration), 8
(Flow B ML diagnostics), and 9 (Flow C paper-figure prep); the save flow is Block 10.
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
[`project/roadmap.md`](project/roadmap.md)). **Blocks 2–9 have shipped.** The
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
artifact's own file. **Block 7** completes the Flow A signal-exploration mode:
multi-bank load → a composable filter (numeric + categorical, applied on an explicit
Recalculate, with a "match all that exist" mode for cross-bank fields) → a sortable
result list → per-trace detail, across a **Summary** tab (the ADR-018 distribution
grid + per-bank stats, both filter-responsive), a **Scatter** tab (2-D feature
scatter, click a point → the detail, per-bank bring-to-front), and an **Explore** tab
whose detail offers "find similar in other bank" — the nearest trace in each other
bank along a chosen feature, shown as a compare-with-feature-deltas. **Block 8**
adds the Flow B ML-diagnostics mode: the *same* Open-bank action auto-detects a
predictions bank and populates four tabs — **Output** (P(positive) per source, the
v1-vs-v1.5 headline), **Metrics** (ROC + calibration + a per-source confusion matrix
with a counts / overall% / row% / col% normalization, labelled sets only), **Training**
(loss + metric curves from an independent *Open training run* path, train vs val by
colour, a removable loaded-runs roster), and **Explore**, which reuses Flow A's detail
pane (extracted into a shared `ExploreDetail` widget) and the *same* Banks-&-filter
panel: filter to the failure cases (FP / FN) and each one still finds its nearest
correctly-classified counterpart. **Block 9** completes the Flow C paper-figure-prep
mode: a curated per-recipe form beside a live **WYSIWYG** preview — a raster of the real
matplotlib recipe (`figures.preview_png`), pixel-identical to the export by construction
(ADR-019 resolved to matplotlib, not pyqtgraph sliders). The resolve runs on a worker
thread so a large bank never freezes the window; edits debounce, expensive recipes gate
behind Refresh, and Render-full writes to the spec's own output (confirming an overwrite).
The Phase tree drives it — **Edit figure spec** opens it, **View figure** opens the
rendered image, **Generate** / **Regenerate** renders to disk — with a menu that turns
dynamic on whether the image exists. Pins
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
