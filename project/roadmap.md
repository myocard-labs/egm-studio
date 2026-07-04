# egm-studio — roadmap

Phased implementation plan for egm-studio, picking up after Block 0
(design phase) closes. Same conventions as the other myocard-labs
repos: each block has a scope, dependencies, and exit criteria; the
block list is kept in sync as work progresses.

> **As-shipped note (egm-contracts v0.5.0):** the linkage formats are **JSON,
> not YAML** (`manifest.json`, `observations/<id>.json`, figure spec `.json`);
> the observation prose field is `description`; the manifest stores banks as
> `egm_banks` + `noise_banks`. Read the YAML / `body` references below
> accordingly — see the reconciliation note in `project/architecture.md`.

> Architecture decisions all live in `project/design.md` (full ADRs)
> and `project/architecture.md` (current-state synthesis). This file
> is about **sequencing** — what we build, in what order, with what
> dependencies.

## Velocity target

**Total: ~10-13 days focused effort → ~1-1.5 weeks elapsed.**

Calibrated against actual project velocity (3 weeks of full-time
work has shipped the entire refactor + design phase; implementation
proceeds at AI-assisted pace with a fully locked design).

## Critical-path dependency

**`myocard-egm-contracts` v0.5.0 ships before Block 2 starts.**

v0.5.0 is the cross-artifact-linkage shipping wave (see
`intracardiac-platform/project/cross_artifact_linkage_design.md`) and
includes the schemas egm-studio needs:

- `figure_spec` (drives Block 2 + 3 figures pipeline)
- `observation` (drives Block 10 Save flow)
- `phase_manifest` (drives Blocks 6 + 10 Phase GUI)
- `model_metadata` extensions for stable IDs (drives Block 8 ML
  diagnostics)

Without v0.5.0 we'd be designing the schemas twice. Hold Block 2
until v0.5.0 is tagged in egm-contracts.

## Blocks

### Block 1 — Scaffold + design (done as Block 0.x)

Retroactively marked done; corresponds to Block 0.1 through Block 0.7
in `design.md`. The scaffold + 25 ADRs + reference_apps +
paper_figure_inventory + user_flow_walkthroughs + architecture +
roadmap are all in place.

**Status:** Done (Block 0 closes after step 0.7).

### Block 2 — `analysis/` module + `egm-studio-render` CLI skeleton

The pure-data foundation that both rendering backends consume. No
matplotlib, no pyqtgraph, no Qt in `analysis/`. See `architecture.md` "The
three-layer rendering split."

**Status:** Done (2026-06-28).

**Scope:**

- `analysis/` package with submodules per analytical concern
  (distributions, aggregation, similarity scaffolding). Pure functions over
  numpy / pandas / scipy / egm-features.
- `view_model/` — unified per-trace view-model construction
  (joins features + metadata; ML outcomes + similarity join in
  later blocks).
- `figures/render.py` thin dispatch skeleton (parses spec, looks up
  recipe, calls into `charts/matplotlib/` — empty registry at this
  block, fills as Block 3 adds recipes).
- `cli/render.py` — `egm-studio-render` console script (loads the spec
  JSON via egm-data's `phases.load_figure_spec`, calls dispatch, writes
  the file).
- pytest infrastructure for `analysis/` (unit tests, no display).
- `pyproject.toml` declares the `egm-studio-render` console script.

**Deps:**

- egm-contracts v0.5.1 (figure_spec schema)
- egm-features v0.1.1+ (per-trace extractors; v0.1.1 added the py.typed marker)
- egm-data v0.4.1+ (bank readers + `ClassifierBank.uniform_fs_hz()`, added v0.4.1)
- matplotlib

**Exit:**

- `pytest tests/analysis/` passes (unit tests for analytical primitives).
- `egm-studio-render --help` works.
- `egm-studio-render examples/stub_spec.json` returns a clear "no
  recipe registered" error from the empty dispatch (the plumbing is
  there, ready for Block 3 to fill).

**As built (deviations from the scope above):**

- Spec files are **JSON**, not YAML — the shipped `figure_spec` contract
  serializes as JSON (read via egm-data's `load_figure_spec`);
  `examples/stub_spec.json`.
- `similarity` lives at `analysis/similarity.py` (a per-feature nearest
  primitive); `architecture.md`'s module map was reconciled to match.
- `aggregation` ships the between-group distance functions only;
  `group_feature_summary` was dropped as unused by any P0 recipe. The
  per-group *value-arrays* helper the `feature-distribution-overlay` recipe
  needs lands in Block 3.
- Surfaced two sibling patch releases: egm-features **v0.1.1** (py.typed marker)
  and egm-data **v0.4.1** (`uniform_fs_hz` pushed down from the view-model
  builder).

**Estimated effort:** ~1 day.

### Block 3 — `charts/matplotlib/` backend + P0 recipes + snapshot tests

The first end-to-end vertical slice through the pipeline. Picks up
where Block 2 leaves off; ends with real figures rendering from
spec JSON files.

> **Status (P0 recipe set complete):** the matplotlib foundation has shipped — the recipe
> registry (`registry.py`, split out of `__init__` to avoid import cycles), the
> paper style (`style.py`: Okabe-Ito palette + embedded-font rcParams +
> `color_for`), the prepared-input dataclasses (`inputs.py`), the
> `render(spec, *, data, overwrite)` contract + existing-output skip, and the
> figure-data loaders (`loaders.py` + `egm-studio-render --bank/--banks`,
> brought forward from Block 7). All eight Phase-1.5 P0 recipes have shipped —
> **`prediction-histogram`**, **`feature-distribution-overlay`** (the primary
> sim-realism diagnostic, F-1.5.2: per-feature density overlay with
> KS/Wasserstein annotation, axis units, `layout.features` curation),
> **`bar-chart-with-deltas`** (F-1.5.3: per-variant aggregate distance to the
> IAFDB reference with baseline-relative deltas; a generic bar recipe), and
> **`roc-curve-multi-line`** (F-1.5.4: overlaid synthetic-val ROC curves +
> AUROC, on a new pure-numpy/scipy `analysis/metrics`; reuses the
> `prediction-histogram` loader via stacked registration), and
> **`calibration-reliability-diagram`** (F-1.5.5: per-model reliability curves +
> ECE, extending `analysis/metrics`; same loader reuse), and
> **`trace-pair-gallery`** (F-1.5.7: an N x 2 synthetic-vs-IAFDB matched-trace
> grid — new `TracePair` / `TracePairGallery` inputs + a dedicated loader, the
> first consumer of `analysis/similarity`), **`summary-table`** (F-1.5.10:
> generic `TableData` -> matplotlib table; the curation loader reads the
> `noise_bank_run_record` sidecar — the first non-bank loader — with
> `layout.fields` field curation), and **`training-curve`** (F-1.5.11: loss +
> val-metric vs epoch from a `training_run_record`, best epoch marked) — each with
> a snapshot test + example spec, plus shared helpers `select_from_available`
> (backing the `layout.features` + `layout.fields` curation) and
> `spec_fields.positive_label` (read identically by the loader and the ROC /
> calibration recipes). Beyond the eight recipes,
> **F-1.5.6** (per-intervention IAFDB de-saturation overlay) is also wired — it
> needed no new recipe, reusing `prediction-histogram`'s overlay mode with its own
> example spec + a multi-unlabeled-overlay test. **That completes the Phase-1.5
> P0 recipe set** — all eight reviewed one at a time (each a math look + snapshot
> + commit); P1 / P2 recipes are Post-v0.1.0 follow-ups and the interactive Qt GUI
> (Block 4) is next.

**Scope:**

- `charts/matplotlib/` package — implement all P0 recipes from
  `paper_figure_inventory.md` (Phase 1.5 paper, ~7-8 recipes), one per
  review cycle.
- Wire recipes into the `figures/render.py` dispatch registry.
- pytest-mpl snapshot tests for each recipe.
- Set matplotlib rcParams for vector PDF export with embedded
  TrueType fonts (`pdf.fonttype = 42`) per the paper-figure
  inventory.
- Sample spec JSON files in `examples/` that exercise each recipe.
- `figures/loaders.py` — bank → recipe-input adapters (e.g.
  `prediction_group_from_bank`), the renderer's data-loading step.
  Brought forward from Block 7 so real banks render *now*: the CLI
  `--bank ID=PATH` / `--banks map.json` flags supply a hand-written
  `{bank_id: path}` map (a proto-manifest). The adapters are permanent;
  Block 7 only swaps the map source for the phase manifest.

**Deps:**

- Block 2 done.

**Exit:**

- `egm-studio-render examples/<recipe>_spec.json --banks banks.json -o out.pdf`
  renders real banks for each P0 recipe (the `--banks` map stands in for
  the Block 7 phase-manifest resolution).
- pytest-mpl snapshot tests pass for all P0 recipes.
- Output PDFs have embedded vector text (verified by opening in a PDF
  reader + selecting text).

**Estimated effort:** ~1.5-2 days.

> **P1 / P2 / P3 recipes** (later phases' papers) get added in
> v0.x updates after v0.1.0 ships. v0.1 only covers what the Phase 1.5
> paper needs.

### Block 4 — Qt shell + theme

First Qt work. Establishes the layout shell and theming substrate
that all subsequent GUI blocks build on. No actual content yet —
placeholder panels prove the shell works.

**Scope:**

- `gui/app.py` — QApplication entry point + `egm-studio` console
  script wiring.
- `gui/shell.py` — resizable-column layout shell per ADR-025:
  draggable column separators; collapsible left + right sidebars;
  Activity-Bar-style icon strip when sidebars collapsed.
- `gui/theme/` — dark + light QSS per ADR-012; default dark; toggle
  via View menu.
- Menu bar with stub actions; mode-switching scaffold (3-mode
  segmented control).
- pytest-qt smoke tests: shell instantiates, sidebars collapse /
  expand, theme toggle works.

**Deps:**

- PySide6, pyqtgraph (peer-installed, not used yet here).

**Exit:**

- `egm-studio` launches a window with the empty layout shell.
- Dark / light theme toggle works.
- pytest-qt smoke tests pass headless (offscreen QPA; CI installs the Qt libs).

**Estimated effort:** ~1 day.

**Status:** Done (2026-07-01). Shipped as specified — `gui/app.py` + `gui/shell.py`
(ADR-025 layout: draggable columns, collapsible sidebars that fold to a ~40px
Activity-Bar strip), the 3-mode segmented control, `gui/theme/`, and pytest-qt
tests — plus two extras Daniel requested during review:
- **Three** themes, not just dark+light: dark (default) + light + a **vibrant**
  programmer-editor palette (ADR-012 amended).
- The selected theme **persists across launches** via Qt `QSettings`
  (`gui/preferences.py`), realising ADR-012's "user-preference theme key" and
  seeding the ADR-017 save-state.
Verified headless under the offscreen QPA platform (the sandbox has no xvfb).

### Block 5 — TraceWidget + container + `charts/pyqtgraph/` backend

The composable trace widget from ADR-024, plus the second rendering
backend for `charts/`. The GUI now has its core data-display primitive.

**Status:** Done (2026-07-01). `TraceWidget` + `TraceContainer` (ADR-024) with a
shared, pannable/zoomable X-axis, the time-scale slider, and a metadata-driven
trace selector; plus the `charts/pyqtgraph/` backend's `feature-distribution-overlay`,
visually equivalent to the Block 3 matplotlib figure over the same `analysis/`
output. A throwaway local demo (`examples/pyqtgraph_demo.py`, git-ignored — for
interactive checks until the shell hosts these views) opens either standalone.
The shared recipe-input dataclasses + Okabe-Ito palette moved to `charts/inputs.py` +
`charts/palette.py` (framework-free) so both backends share them without
`charts/pyqtgraph/` importing matplotlib.

**Scope:**

- `gui/widgets/trace.py` — `TraceWidget` (one trace + metadata) and
  `TraceContainer` (GraphicsLayoutWidget host for N TraceWidget
  instances with shared X-axis).
- Mouse pan + zoom on X-axis; time-scale slider widget bound to the
  same.
- `charts/pyqtgraph/` package — pyqtgraph variants of any P0 recipes
  that also need live display (typically the trace-render and
  feature-distribution recipes). Reuses `analysis/` for data prep.
- pytest-qt tests for TraceWidget instantiation, multi-trace
  stacking (verify N=2 + N=4 work), and shared-axis behavior.

**Deps:**

- Block 2 done (`analysis/` available for chart data prep).
- Block 4 done (Qt shell to host the widget in tests).

**Exit:**

- Demo script in `examples/` instantiates a TraceContainer with N
  traces and renders them in a standalone window.
- pytest-qt tests pass.
- pyqtgraph chart of a feature distribution looks visually equivalent
  to the matplotlib version from Block 3 (same `analysis/` output).

**Estimated effort:** ~1 day.

### Block 6 — Phase manifest reader + read-only Phase tree

Front-loads the meta-repo file-format integration so it's not a
surprise when Save lands later. Read-only Phase tree at this point;
write logic lands in Block 10.

**Status:** Done (2026-07-03).

**Scope:**

- `loaders/phase_manifest.py` — read `manifest.json`, validate
  via egm-contracts Pydantic model, expose typed manifest object.
- `gui/widgets/phase_tree.py` — right-rail artifact tree grouped by
  role-based bank type + non-bank artifacts (10 groups per the
  cross-artifact design). Counts shown next to group names whether
  collapsed or expanded. Click artifact → inline expansion (manifest
  pointer view).
- Stable-ID-aware navigation hooks (clicking a `tbank_` ID surfaces
  bank actions; clicking a `obs_` ID surfaces observation actions;
  etc.) — read-only for now, no Save.
- Drop-folder / menu-select for loading a phase.
- pytest unit tests for the manifest loader.

**Deps:**

- Block 4 done (shell to host the Phase tree).
- egm-contracts v0.5.0 (phase_manifest schema).
- A representative manifest.json fixture (can be hand-written
  for v0.1 testing).

**Exit:**

- Drop a phase folder into the app → manifest loads → artifact tree
  populates with counts.
- Clicking an artifact shows its manifest entry inline.
- pytest tests pass.

**As built (deviations from the scope above):**

- **The manifest reader lives in egm-data, not `loaders/phase_manifest.py`.**
  egm-data owns `load_phase_dir(folder)` (reads `manifest.json`); egm-contracts
  owns the *generated* role vocabulary (`Role` + `role_of`, single-sourced in
  `codegen/roles.json`). egm-studio keeps only the display / interaction layer —
  `view_model/phase_groups.py` (the ten role groups), `view_model/phase_status.py`
  (existence + on-demand schema validation), `view_model/phase_actions.py` (the
  right-click policy), and `view_model/artifact_metadata.py` (file-level
  metadata) — feeding `gui/widgets/phase_tree.py`. This keeps file I/O and the
  cross-language role vocabulary out of the GUI (invariant #1); coordinated
  egm-contracts v0.5.2 + egm-data v0.4.2.
- **Artifact status is shown, not just structure.** Each row carries a status
  dot — grey (present, unvalidated) / green (ok) / amber (invalid) / red
  (missing) — set on load (existence only) and refined by **File ▸ Validate
  phase** (full schema validation).
- **Right-click actions, not just inline expansion.** Every artifact has a
  role-aware menu — Explore signal (wired for the egm-bank roles), Show metadata
  (reads the file: a ClassifierBank summary, a noise-bank header, or pretty
  JSON), Reveal file, Copy id — with not-yet-built viewers greyed and tagged to
  the block that delivers them. The inline manifest-pointer rows remain.
- Loaded via **File ▸ Open phase**; a folder-drop is a later convenience.

**Estimated effort:** ~0.5-1 day.

### Block 7 — Flow A signal exploration

First complete user-facing flow. Brings together bank loading +
filter UI + TraceContainer into the signal-exploration view per
`user_flow_walkthroughs.md` Flow A.

**Scope:**

- `loaders/bank.py` — wrappers over egm-data bank readers
  (ClassifierBank, IAFDBBank, etc.).
- Manifest-driven figure rendering: resolve a figure_spec's
  `inputs.groups` bank ids to paths through the phase manifest and feed
  `figures/loaders.py` (seeded in Block 3), retiring the hand-supplied
  `--bank` / `--banks` map. (Open: whether the figure-input adapters in
  `figures/loaders.py` should fold into the top-level `loaders/` package
  here, leaving `figures/` pure rendering.)
- view_model construction joining bank metadata + features
  (`analysis/` from Block 2).
- `gui/widgets/filter.py` — composable filter UI per ADR-002 (trace
  features + bank metadata + manual sets; ML outcomes + similarity
  arrive in Block 8).
- `gui/views/signal_exploration.py` — Flow A view: load bank → filter
  → browse traces in TraceContainer.
- pytest-qt integration tests for the end-to-end flow.

**Deps:**

- Blocks 2, 4, 5 done.

**Exit:**

- Load a synthetic ClassifierBank → filter by `sample_entropy > 1.5`
  → matched traces appear in the TraceContainer.
- Filter UI composes multiple categories (feature + metadata).
- pytest-qt integration test passes.

**Estimated effort:** ~1-1.5 days.

**Scoping pass (2026-07-03) — full-walkthrough sub-block sequence.** Block 7
covers all of Flow A (not just the MVP exit above), built one reviewable slice at
a time. Decisions locked this pass:

- **Filter UI:** a new `gui/widgets/filter.py` over the joined view-model
  DataFrame (features + metadata) feeding a new sortable **result list** widget
  (`result_list.py`); the metadata `trace_selector` is retired (B7.5-cleanup) —
  separating "compose the query" from "scan / pick results" (the cleanest path
  into Block 8's ML-outcome columns).
- **Multi-bank:** single-bank MVP first; multi-bank is its own sub-block, not the
  core.
- **Data loading:** resolves the "Open" question above — **yes, consolidate.**
  `figures/loaders.py`'s data-loading folds into a top-level `loaders/` package
  (`figures/` stays pure rendering), and phase-manifest bank-id → path resolution
  is wired now that Block 6's reader exists.
- **Save (Flow A step 9):** deferred to Block 10 (unified Save schema, ADR-017).

Sub-blocks:

- **B7.1 — `loaders/` package.** Move the `figures/loaders` adapters into a
  top-level `loaders/`; add `loaders/bank.py` (egm-data reader wrappers) +
  phase-manifest `{bank_id: path}` resolution, retiring the `--bank` / `--banks`
  CLI map for manifest-driven rendering.
- **B7.2 — view-model into the GUI.** Back the filter / list with
  `build_view_model` (identity + metadata + the 11 features), plus a
  `data_source` / bank column (single-bank now; the multi-bank dimension lands in
  B7.8).
- **B7.3 — `gui/widgets/filter.py`.** Composable filter: numeric thresholds +
  categorical equality + boolean composition over the frame's columns (numeric
  vs categorical by dtype, plumbing hidden); emits the matching row set.
- **B7.4 — `gui/widgets/result_list.py`.** A new sortable table over the
  view-model (any feature / metadata column as the sort key, numeric-aware), fed
  by the filter; selection drives the detail view.
- **B7.5 — `gui/views/signal_exploration.py`.** Assemble load → filter → list →
  click → detail; wire the Signal-exploration mode button, the phase-tree
  **explore_signal** action, and File ▸ Open bank into it.
- **B7.6 — per-trace detail.** Waveform (Block 5 `TraceView`) + an 11-feature
  table + a metadata panel (sim_id, electrode_pair_id, fibrosis density, label);
  up-to-3-pane compare reuses `TraceContainer`. **← the MVP exit above.**
- **B7.7 — bank-summary landing.** Default post-load view: trace count, class
  balance, provenance + the 11-panel egm-features histogram grid, with **ADR-018
  responsive sizing** (per-panel min/max clamps + a preferences-persisted global
  scale factor + grid-wrap). Wires the phase-tree **view_feature_distributions**
  action. **✓ Shipped 2026-07-03** — `view_model/summary.py` + `loaders/feature_group.py`
  (a, pure) + `gui/widgets/feature_grid.py` (b, the ADR-018 grid) + Summary/Explore
  sub-tabs in the Flow A view + the `ui_scale` preference (c). Explore signal → the
  Explore tab, View feature distributions → the Summary tab.
- **B7.8 — multi-bank loading.** Load N banks at once; side-by-side / overlaid
  summaries; `data_source` becomes a real filter dimension (`data_source ==
  synthetic`).
- **B7.9 — feature scatter.** A 2-D `(feat_x, feat_y)` scatter over the current
  filter result — pan / zoom, per-point colour by `data_source`.
- **B7.10 — per-feature similarity + 3-pane compare.** "Find similar in other
  bank" via `analysis.similarity.nearest_along_feature` + a feature-axis dropdown
  → 3-pane compare-with-feature-deltas (shares the pair-comparison machinery with
  Block 8; ADR-020 per-feature only).

ADR formalized here: **ADR-018** (responsive thumbnail-grid sizing, B7.7) —
**accepted + implemented 2026-07-03**.
**Revised estimate:** ~3-4 days for the full walkthrough (was ~1-1.5 for the
MVP-only exit).

### Block 8 — Flow B ML diagnostics

Extends the view-model with predictions-bank outcomes; adds the
3-way comparison view that anchored Flow B in
`user_flow_walkthroughs.md`.

**Scope:**

- Predictions-bank loader (joins predictions onto the per-trace
  view-model: predicted_prob, predicted_class, correctness_bucket,
  per_trace_loss, calibration_residual).
- `analysis/similarity` — extend the Block 2 per-feature scaffold with
  the nearest-correct-pair + within-class-neighborhood diagnostics per
  ADR-020; UI dropdown selects the feature axis.
- `gui/views/ml_diagnostics.py` — Flow B view: "Load Evaluated Bank"
  unified entry, 3-way comparison (v1 / v1.5 / IAFDB output
  distributions), filter-by-ML-outcome, pair-comparison.
- Pair-comparison view in the two-column main area (per ADR-025).
- pytest tests for the view-model joins + similarity; pytest-qt for
  the view shell.

**Deps:**

- Block 7 done (shell + filter UI + TraceContainer).
- egm-classifier-produced predictions banks available (already
  shipped via egm-classifier v0.1.0).

**Exit:**

- "Compare v1 vs v1.5 IAFDB output distributions" workflow works
  end-to-end.
- Pair-comparison view shows two traces side-by-side with shared
  scaling.
- Nearest-correct-pair similarity computes in < 1 sec on
  representative banks.

**Estimated effort:** ~1 day.

### Block 9 — Flow C paper figure prep

GUI editor that wraps the headless `figures/` module from Block 3.
First implementation of ADR-019 live-preview (Qt sliders →
re-render).

**Scope:**

- `gui/views/paper_figure_prep.py` — form-based figure_spec editor
  with live preview.
- `@interact`-equivalent: Qt sliders bound to PyQtGraph or
  matplotlib redraw callbacks; debouncing on slider drag; manual
  "Run" button for expensive operations.
- "Render full" button that calls `figures.render()` for the
  full-quality export.
- Export flow: PDF / PNG / SVG with vector text (embedded fonts
  already wired in Block 3).
- Per-feature similarity dropdown for similarity-pair recipes.
- Round-trip test: edit spec → save YAML → reopen → same starting
  state.
- pytest-qt smoke tests; pytest-mpl already covers the headless
  path.

**Deps:**

- Blocks 3 + 7 done.

**Exit:**

- User can interactively iterate on a figure spec and see the preview
  update.
- Export produces a vector PDF identical to the headless renderer's
  output for the same spec.
- Round-trip works.

**Estimated effort:** ~0.5-1 day. Small because most of the heavy
lifting is in the figures/ module from Block 3 + the live-preview
pattern from ADR-019.

### Block 10 — Save flow + Phase manifest writes

Wires up egm-studio as the canonical manifest curator (ADR-021).
Block 6 set up the read-only Phase tree; this block adds the write
path.

**Scope:**

- `save/observation.py` — observation writer
  (`obs_<slug>_<date>.yaml`) per ADR-017.
- `save/manifest.py` — phase manifest reader + writer; stable-ID
  generator per ADR-022.
- Right-rail Phase GUI write logic (Save Observation, Save Trace
  Set inside observation, Save Figure Spec into phase + paper).
- Scratch mode: no phase loaded → save to
  `intracardiac-platform/project/scratch/`. "Promote to Phase"
  action moves + indexes.
- Phase manifest scan-and-validate hook (call into
  `intracardiac-platform/scripts/validate_manifest.py` after each
  write).
- pytest tests for save writers; pytest-qt for the Save Observation
  UI.

**Deps:**

- egm-contracts v0.5.0 (observation + phase_manifest schemas).
- Block 6 done (read-only Phase tree).
- Blocks 8 + 9 done (the things being saved exist).

**Exit:**

- User can save an observation from any view.
- Phase manifest updates correctly; scan-and-validate passes Check A
  (orphan detection).
- Scratch → Promote-to-Phase round-trip works.

**Estimated effort:** ~1-1.5 days.

### Block 11 — Design-phase doc updates (capture drift)

Sweep the design-phase docs for any drift introduced during
implementation. Per the living-document commitment in
`architecture.md`, fix-on-contact is the preferred mode; this block
is the safety net to catch anything that slipped.

**Scope:**

- `project/design.md` — flag any ADRs that ended up implemented
  differently than specced; add "Implementation note: ..." sub-
  sections where needed.
- `project/architecture.md` — flesh out additional detail (data-flow
  diagrams, expanded module-internals, concrete code examples)
  appropriate for the as-built state; reconcile any divergences from
  what was actually implemented.
- `project/paper_figure_inventory.md` — mark which recipes are
  actually shipped in v0.1.0 vs deferred to later versions.
- `project/user_flow_walkthroughs.md` — annotate any flow steps that
  ended up differently than the walkthrough.
- `project/reference_apps.md` — likely no changes needed; sanity
  check.

**Deps:**

- Blocks 2-10 done (need the implementation to compare against).

**Exit:**

- All five design-phase docs accurately reflect the as-built v0.1.0
  state.
- No "future tense" claims in architecture.md that didn't pan out.

**Estimated effort:** ~0.5 day.

### Block 12 — User documentation

The polished public face of the project. Daniel called this out
explicitly: "this is the main way other people will be able to access
my data and i want to take the time to make this projects user
documentation really good." Budget real time here.

**Scope:**

- `docs/usage.md` — full user manual covering:
  - Install + first launch
  - The three modes (signal exploration / ML diagnostics / paper
    figure prep) — each with screenshots and step-by-step
    walkthroughs
  - **Reading each figure** — a per-recipe interpretation guide (what each
    figure shows; how to read a good vs bad result), linking back to
    `docs/theory.md` for the math. Migrated here from theory.md §5, removed
    2026-07-01 to keep the theory doc pure math (Daniel's call)
  - Save Observation + Phase artifact tree workflow with screenshots
  - Headless `egm-studio-render` CLI usage
  - Keyboard shortcuts reference
  - Troubleshooting / FAQ
- `docs/` subfolder structure: `docs/screenshots/` for the captured
  images; `docs/walkthroughs/` if any walkthroughs grow long enough
  to deserve their own files.
- Top-level `README.md` — match the canonical egm-signal / egm-data
  structure (Why / Install / Programmatic usage / Module map / Tests
  / Project status / Citation / License).
- `CHANGELOG.md` — v0.1.0 entry with the full feature summary.

**Deps:**

- Blocks 2-10 done (functionality must be in place to screenshot).
- Block 11 done so user docs aren't built on a stale design.

**Exit:**

- A new user can install egm-studio, work through every documented
  flow, and successfully complete each one without external help.
- All three modes have screenshot-illustrated walkthroughs.
- README is approachable for someone landing on the GitHub page cold.

**Estimated effort:** ~1.5-2 days.

### Block 13 — Ship v0.1.0

Final pin-and-tag.

**Scope:**

- Pin all sibling-repo deps in `pyproject.toml` to their exact
  release versions.
- End-to-end smoke test: launch GUI, run each of the three flows
  from `user_flow_walkthroughs.md`, render a figure via the CLI.
- Final commit on `development` branch; merge `development` →
  `release` per [[project-branch-strategy]].
- Tag `v0.1.0` on `release` branch.
- Push tag.

**Deps:**

- All prior blocks done.

**Exit:**

- v0.1.0 tag on the `release` branch.
- All three user-flow walkthroughs runnable end-to-end.

**Estimated effort:** ~0.5 day.

## Total estimated effort summary

| # | Block | Days |
|---|---|---|
| 2 | analysis/ + render CLI skeleton | 1 |
| 3 | charts/matplotlib/ + P0 recipes | 1.5-2 |
| 4 | Qt shell + theme | 1 |
| 5 | TraceWidget + container + charts/pyqtgraph/ | 1 |
| 6 | Phase manifest reader + read-only tree | 0.5-1 |
| 7 | Flow A signal exploration | 1-1.5 |
| 8 | Flow B ML diagnostics | 1 |
| 9 | Flow C paper figure prep | 0.5-1 |
| 10 | Save flow + manifest writes | 1-1.5 |
| 11 | Design-phase doc updates | 0.5 |
| 12 | User documentation | 1.5-2 |
| 13 | Ship v0.1.0 | 0.5 |
| **Total** | | **~10-13 days focused, ~1-1.5 weeks elapsed** |

## Post-v0.1.0 follow-ups

Forward-looking items not in any v0.1 block. Each has a trigger
condition for when it becomes priority work.

| Item | Trigger | Approx. effort |
|---|---|---|
| P1 / P2 / P3 recipes (Phase 2+ paper figures) | Each paper enters writing phase | ~1-2 days per paper-worth |
| Figure-math theory doc (per recipe / spec) | All P0 recipes shipped (Block 3 done) — Daniel wants the math behind each spec written up in one place | Medium — covers what each recipe + `analysis` fn computes (ROC / AUROC, reliability / ECE, KS / Wasserstein / KDE distances, aggregate distance). Honor the theory-docs split: egm-classifier `docs/theory.md` owns the eval-metric derivations + operational guidance, egm-studio owns visual interpretation — so egm-studio documents the analysis-layer implementations and cross-links to egm-classifier for the ML-eval theory |
| Feature-extraction progress feedback | Feature-based recipes (feature-distribution-overlay, trace-pair-gallery, ...) are slow on real banks — the view-model build runs `bundle.extract_all` over every trace (the O(T^2) sample-entropy pass dominates) | Small — thread a `tqdm` / callback through `build_view_model` -> `extract_all`; possibly an egm-features param. Parallels the egm-classifier eval progress bar. **Callback plumbing + a cancelable GUI dialog shipped in B7-async (2026-07-03)** — `build_view_model(progress=...)` chunks `extract_all` and the shell wraps it in a QProgressDialog; the CLI/recipe `tqdm` surface remains |
| Feature-computation cache (reuse view-model tables across bank switches) | Flow A re-runs the O(T^2) `extract_all` pass every time a bank is (re)opened — switching away from a bank and back re-pays the whole cost. Worsens with multi-bank loading (B7.8) and large banks (the IAFDB unlabeled bank) | Small-medium — wrap the `build_view_model` call in `gui.sources.load_exploration` / `loaders`; the builder stays pure and is **already keyed by the stable `bank_id`**, so this is a loader-layer add with no builder / contract / egm-features change (⇒ deferring costs nothing). **Start in-memory, session-scoped**: a `{bank_id: DataFrame}` cache — feature tables are small (N×11 floats), so the cost being saved is CPU, not RAM, and an in-memory cache fully covers the switch-away-and-back case. Cache key = (`bank_id`, egm-features `__version__`, `FEATURE_COLUMNS`). Promote to on-disk parquet **only if** instant reopen across launches becomes a felt need — and only then take on cross-session invalidation (the version-keyed key + a bank-file fingerprint), which is exactly why session-scoped is the safe default |
| Weighted multi-feature distance — joint similarity + realism aggregate [ADR-020] | **Phase 1.5** (synthetic-realism research), scheduled after the refactor + egm-studio finish (Daniel's call 2026-07-01). Supersedes the per-feature v0.1 similarity + unweighted-KS aggregate once the realism study says which features matter — the weights are downstream of that investigation. A rigor upgrade to the realism *analysis*, NOT a Phase-1.5 *figure* blocker (F-1.5.2/3/7 work per-feature today) | Medium — one core, two applications: standardize each feature's distance by its pooled spread (theory.md §2.3, -> dimensionless), add config-sourced importance weights, then apply as (a) a joint nearest-neighbour metric for `trace-pair-gallery` (ADR-020 resolution) and (b) a weighted aggregate for `bar-chart-with-deltas`. Unlocks weighted **Wasserstein** (whole-distribution shift, not just the max CDF gap) over weighted KS. Needs a weight source + the joint-distance impl. Cross-cutting Phase-1.5 plan lives in intracardiac-platform/project/project_plan.md |
| Single-activation IAFDB windows for sim-vs-real comparison | Sim-vs-IAFDB feature / trace comparisons (F-1.5.2, F-1.5.7, ...) are confounded — IAFDB segments carry multiple activation waves, Phase-1 synthetic is single-beat (surfaced 2026-06-30 from F-1.5.7). See the inventory "Sim-real comparability prerequisite" | Medium — segment IAFDB to one-activation windows before feature extraction (a curation / windowing step; fix-location TBD: producer iafdb-pipeline segmentation vs an egm-studio comparison-loader hook). Resolves once multibeat synthetic lands (Phase 4) |
| LaTeX / markdown text export for summary-table | A paper wants an editable table (not an embedded image) — surfaced 2026-06-30 building F-1.5.10; the figure_spec `output.format` enum is pdf/png/svg only, so summary-table renders an image today | Medium — add a `tex` / `md` output format to egm-contracts' figure_spec (coordinated bump) + a text branch in `figures/render` (write `pandas.to_latex` / `to_markdown` of the TableData instead of `savefig`). egm-studio-side once the contract lands |
| Live-preview perf revision [ADR-019] | Real-bank perf forces a strategy change | ADR-NNN supersedes ADR-019 + impl |
| Bottom panel (JupyterLab "down area") [ADR-025 deferred] | Use case emerges that the column layout doesn't accommodate | Small impl |
| Multi-trace UI (TraceContainer used with N > 1) | Phase 4 multi-beat work begins | Small — substrate already in place |
| Phase 8+ live playback (task #311) | Phase 8 starts | Medium — animation loop + cursor primitives |
| Plugin architecture [ADR-006] | External contributors want to extend | Large refactor |
| Per-trace stable IDs in banks | Integer-index fragility causes a real reproducibility break | egm-contracts revision + cascade |
| HF Datasets for active bank sharing | Multi-collaborator GitHub-Releases workflow gets painful | Producer-repo changes; egm-studio unchanged |
| Web frontend | Daniel decides desktop-only is limiting | Large — `gui/` rewrite; reuses `figures/` + `loaders/` + `analysis/` + `charts/matplotlib/` |
| Rich "Show metadata" viewer (collapsible, syntax-highlit tree) | **Low priority.** The Block 6 metadata dialog is a plain read-only text pane (`gui/shell._show_metadata`); upgrade when metadata inspection becomes a frequent workflow. Imitate a browser's JSON viewer: collapsible/expandable nodes + a per-type colour scheme (keys / strings / numbers / bools / null) | Medium — a `QTreeView` + `QAbstractItemModel` JSON tree behind the existing content. Needs `view_model/artifact_metadata` to also expose a **structured** form (nested dict/tree), not just the flat string it returns today: the run/figure/observation records already have `model_dump()` dicts that map straight to a tree; the bank + noise summaries would need restructuring from hand-built strings into sections. Keep the text form as a copy-to-clipboard fallback |

## Inter-repo coordination

egm-studio's blocks interleave with work in other repos. The
critical-path picture:

```
                    ┌────────────────────────────┐
                    │ egm-contracts v0.5.0       │
                    │ (figure_spec, observation, │
                    │  phase_manifest, model_md  │
                    │  extensions)               │
                    └─────────────┬──────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
                  ▼               ▼               ▼
            ┌──────────┐    ┌──────────┐    ┌──────────┐
            │ egm-data │    │ egm-studio│   │intracard-│
            │ v0.4.0   │    │ Blocks   │   │platform  │
            │ (consume │    │ 2 + 3    │   │ scripts  │
            │  new     │    │ (analysis│   │ updates  │
            │  schemas)│    │  + charts│   └──────────┘
            └──────────┘    │  + CLI)  │
                            └────┬─────┘
                                 │
                                 ▼
                         egm-studio Blocks 4–13
                         (Qt shell, three modes,
                          Save flow, docs, ship)
```

egm-contracts v0.5.0 is the gating dependency. Once it shipped,
egm-data v0.4.0 and egm-studio Blocks 2 + 3 can proceed in parallel.

## Block-list maintenance

When a block closes:

1. Mark `[x]` complete with a date.
2. Re-review the remaining blocks for any drift the closing block
   introduced.
3. Fix-on-contact any architecture.md drift surfaced by the block
   (the living-document commitment); flag it for Block 11's sweep
   pass if a fuller fix isn't trivial.
4. Move to the next pending block.

When a new follow-up emerges:

- If it's in v0.1 scope, add it to the relevant block.
- If it's post-v0.1, add a row to the "Post-v0.1.0 follow-ups" table
  with a trigger condition.
