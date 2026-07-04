# egm-studio — architecture

The post-Block-0 "current state" reference for egm-studio. Distilled
from the 25 ADRs in `project/design.md` — read this for *what we're
building*; read `design.md` for *why we picked it*. ADR pointers
(`[ADR-N]`) appear inline so you can drill down on any decision.

> Block 1+ implementation work and forward-looking follow-ups live in
> `project/roadmap.md`.

> **As-shipped reconciliation (egm-contracts v0.5.0, 2026-06-27).** The
> cross-artifact-linkage formats shipped with surface changes from what this
> doc describes — the high-level architecture is unaffected, but read these
> deltas in (full list: `intracardiac-platform/project/cross_artifact_linkage_design.md`
> → Amendments):
> - **JSON, not YAML** (`manifest.json`, `observations/<id>.json`,
>   `figure_specs/<id>.json`; the render CLI reads a `.json` spec).
> - Observation prose field is **`description`** (not `body`); observations +
>   figure specs carry **no `phase` field**.
> - **`figure_spec`** requires a `description` and dropped `inventory_ref`.
> - The manifest stores banks as **`egm_banks` + `noise_banks`** (predictions
>   fold into `egm_banks`).
> - **Figure specs live in the meta repo** at `phases/figure_specs/<id>.json`
>   (decision 2026-06-27); only the rendered image goes to the paper repo. Any
>   "spec in the paper repo" wording below is superseded. Also: `recipe` is a
>   free-form string in the contract (egm-studio owns the recipe vocabulary),
>   not a schema enum.

## Living-document commitment

This file is the as-built reference and stays in lock-step with
the code. Update it whenever an implementation block surfaces an
architectural change (new module boundary, dependency shift, pattern
that didn't exist at design time). Roadmap Block 12
("Design-phase doc updates") runs late in the v0.1 sequence to do a
sweep before the tag, but **don't wait** for that block — fix-on-
contact while building. The final pre-tag pass also fills in the
deeper detail that's intentionally not in v0.1 of this doc (more
concrete examples, expanded data-flow diagrams, module-internals
discussion).

## What egm-studio is

A desktop GUI for **signal exploration, ML diagnostics, and paper-
figure prep** over intracardiac EGM data. Consumes banks produced by
the upstream pipelines (synthetic-egm-pipeline, iafdb-pipeline,
egm-classifier), surfaces them through a filter-driven analysis UI,
and writes observations + paper-figure specs back into the phase-
organized meta repo (intracardiac-platform).

It ships **two console scripts** from one Python package
(`myocard-egm-studio`):

- **`egm-studio`** — the interactive Qt shell.
- **`egm-studio-render <spec.json>`** — the headless figure renderer.

Both wrap the same framework-agnostic `figures` module; the GUI
shell adds the interactive frontend. [ADR-004, ADR-005, ADR-015]

## Core invariants

The eight decisions everything else hangs off. Change any of these
and the architecture changes.

1. **All data I/O goes through egm-data + egm-contracts.** egm-studio
   never opens an HDF5 / JSON / CSV directly. New file types require
   coordinated schema → reader → consumer PRs across the three
   repos. [ADR-001, [[feedback-use-contracts-at-boundaries]]]
2. **Filter-and-sort-first analysis, not browse-and-scroll.** Every
   view is "traces matching this query, ordered by this metric."
   Filters compose across trace-features, ML outcomes, bank
   metadata, similarity, and manual sets. [ADR-002, ADR-011]
3. **Two frontends sharing one core.** The headless figure path is a
   framework-agnostic Python module; the GUI is a thin Qt shell on
   top. Same `render()` function powers both. [ADR-004, ADR-005]
4. **PySide6 + pyqtgraph + matplotlib.** Desktop Qt for the shell;
   pyqtgraph for interactive trace plots; matplotlib for publication-
   quality figures (Agg backend for headless). [ADR-016]
5. **Resizable columns + collapsible side panels** for the layout
   shell. Not a fixed 4-quadrant grid, not free-form drag-anywhere
   dock. One-or-two main columns; optional left + right sidebars
   that collapse to icon strips. [ADR-025]
6. **Composable trace widget.** One `TraceWidget` per trace; N
   instances stack inside a `GraphicsLayoutWidget` container with a
   shared X-axis. Default N=1 at v0.1; scales to N=64+ for later
   phases without rewriting plumbing. [ADR-024]
7. **Observations + figure specs persist in the meta repo, not in
   egm-studio.** Unified Save schema writes observation YAMLs into
   `intracardiac-platform/project/phases/phase_X/observations/` (or
   scratch dir when no phase is loaded). [ADR-017, cross-artifact
   linkage design]
8. **egm-studio is the canonical curator of the per-phase manifest.**
   The right-rail Phase GUI updates `manifest.json` as the
   user saves observations, trace sets, and figure specs. Producers
   never touch the manifest — they just stamp stable IDs on their
   outputs. [ADR-021, ADR-022]

## Module map

```
myocard_egm_studio/
├── analysis/             # Pure data computation. NO rendering, NO Qt.
│   ├── distributions.py  #   CDFs, KS / Wasserstein distance, histogram, KDE
│   ├── aggregation.py    #   between-group feature distance + aggregate roll-up
│   ├── similarity.py     #   per-feature nearest-trace lookup        [ADR-020]
│   ├── metrics.py        #   ROC / AUROC + reliability / ECE + confusion (synth-val only)
│   └── ...               #   one module per analytical concern
├── charts/               # Chart-building primitives, dual backend.
│   ├── inputs.py         #   prepared recipe-input dataclasses (shared, framework-free)
│   ├── palette.py        #   shared Okabe-Ito group palette + color_for
│   ├── matplotlib/       #   static recipes + the recipe registry
│   │   ├── registry.py   #     RECIPES dict + @register decorator
│   │   ├── style.py      #     paper rcParams + paper_style (re-exports palette)
│   │   └── <recipe>.py   #     one self-registering recipe per module
│   └── pyqtgraph/        #   interactive, GUI-embedded chart recipes
│       ├── style.py      #     PgChartStyle (background / foreground)
│       ├── feature_distribution.py  # feature-distribution overlay (GUI twin)
│       ├── feature_scatter.py       # 2-D feature scatter (GUI-only; no mpl twin) [B7.9]
│       ├── output_distribution.py   # Flow B: P(positive) per source            [B8e]
│       ├── metrics.py               # Flow B: ROC / calibration / confusion      [B8f]
│       └── training.py              # Flow B: loss + metric curves               [B8f]
├── figures/              # Thin headless layer over charts/matplotlib/.
│   └── render.py         #   render(spec, *, data, overwrite) -> Path (pure rendering)
├── gui/                  # Qt shell — imports PySide6 + pyqtgraph.
│   ├── app.py            #   QApplication entry (`egm-studio` script)  [B4]
│   ├── shell.py          #   Layout shell + CollapsibleSidebar    [ADR-025, B4]
│   ├── preferences.py    #   QSettings-backed prefs (theme + view state)  [ADR-017 seed, B4]
│   ├── theme/            #   dark + light + vibrant QSS themes    [ADR-012, B4]
│   │   ├── palette.py    #     colour + typography tokens per theme
│   │   └── _qss.py       #     one shared QSS template + builder
│   ├── widgets/
│   │   ├── trace.py      #   TraceWidget + container        [ADR-024, B5]
│   │   ├── filter.py     #   Filter / query UI              [ADR-002]
│   │   ├── phase_tree.py #   Phase artifact tree: groups, status dots, menu  [B6]
│   │   ├── explore_detail.py  # shared per-trace detail + pluggable finds (both flows) [B8g]
│   │   └── ...           #   Other shared widgets (result_list, feature_grid, metrics_view, ...)
│   └── views/
│       ├── signal_exploration.py   # Flow A — Summary/Explore/Scatter tabs      [B7]
│       ├── ml_diagnostics.py       # Flow B — Output/Metrics/Training/Explore    [B8]
│       └── paper_figure_prep.py    # Flow C — wraps figures/        (Block 9, pending)
├── cli/
│   └── render.py         #   `egm-studio-render` entry point
│                         #   (`egm-studio` GUI script -> gui/app.py:main)
├── loaders/              # Data-loading: ids/paths -> in-memory inputs.   [B7]
│   ├── figure_inputs.py  #   spec + {id: path} -> recipe inputs + LOADERS
│   └── manifest.py       #   phase manifest -> {artifact_id: path} resolution
├── save/                 # Observation + manifest writers   [ADR-017, ADR-021]
└── view_model/           # Prepared, Qt-free view data       [ADR-002]
    ├── builder.py        #   unified per-trace table (features + metadata + ML outcomes)
    ├── ml_outcomes.py    #   predictions-bank -> ML columns; ML_COLUMNS         [B8a]
    ├── combine.py        #   pool N banks into one frame (global row_id)  [B7.8]
    ├── summary.py        #   bank stats for the Flow A summary landing    [B7.7]
    ├── trace_detail.py   #   per-trace feature + metadata + ML detail + deltas [B7.6, B8g]
    ├── similar.py        #   nearest-in-other-bank + correct-pair / in-class finds [B7.10, B8b]
    ├── phase_groups.py   #   manifest -> the ten role-based groups       [B6]
    ├── phase_status.py   #   per-artifact existence + schema validation  [B6]
    ├── phase_actions.py  #   right-click action policy per role          [B6]
    └── artifact_metadata.py  # file-level "Show metadata" summaries       [B6]
```

### The three-layer rendering split

The single most important structural decision after the 25 ADRs:
**no chart logic is duplicated between the GUI and the headless
renderer.** Three layers make this work:

1. **`analysis/`** — pure data computation. Statistical primitives
   (CDFs, KS-distance, distribution comparisons), feature aggregation
   queries, similarity computations, ROC / AUROC + calibration metrics. Pure functions
   over numpy /
   pandas / scipy / egm-features. No rendering, no Qt, fully unit-
   testable.
2. **`charts/`** — chart-building primitives with **two rendering
   backends**: `charts/matplotlib/` for static / publication, and
   `charts/pyqtgraph/` for interactive / GUI-embedded. Both
   backends consume `analysis/` for data prep, so the same
   computation feeds both presentations.
3. **`figures/`** — thin headless dispatch layer. `render(spec, *, data)`
   dispatches `spec.recipe` to the matching `charts/matplotlib/` recipe,
   passing the prepared `data` (built by `figures/loaders.py` from the
   spec's bank ids), and writes the output file — skipping an existing
   one unless `overwrite=True`. The spec is parsed + validated upstream
   by egm-data's `load_figure_spec`, not here.

GUI views (`gui/views/`) import `charts/pyqtgraph/` for live
display. Headless renderer (`figures/`) imports `charts/matplotlib/`
for static export. Both reuse `analysis/` for data prep. Adding a
new chart means: implement once in `analysis/`, implement twice in
`charts/` (one per backend), expose via `figures/` if it needs
headless export.

The two backends share their prepared inputs (`charts/inputs.py`) and
group palette (`charts/palette.py`) at the `charts/` root — both
framework-free, so `charts/pyqtgraph/` reuses them without importing
`charts/matplotlib/` (whose package import pulls in matplotlib).

### The registry pattern (recipes + loaders)

Two places in egm-studio use a **registry**: a module-level dict mapping a
string key to a function, populated by a decorator at import time and looked up
by a dispatcher at call time. It is what keeps `render()` tiny and ignorant of
individual figures, and what lets a new recipe (or loader) be added without
editing any dispatch code — you add a module, not a branch.

There are two registries, one per direction of a render:

- **Recipe registry** — `charts/matplotlib/registry.py` holds
  `RECIPES: dict[str, RecipeFn]` and the `@register("<recipe-name>")`
  decorator. Each recipe module (e.g. `charts/matplotlib/prediction_histogram.py`)
  decorates its drawing function, inserting it into `RECIPES` keyed by the
  `figure_spec.recipe` string. `figures/render.py` then does
  `RECIPES[spec.recipe]` — a dict lookup, not an `if/elif` chain.
- **Loader registry** — `figures/loaders.py` holds
  `LOADERS: dict[str, RecipeLoaderFn]` and `@register_loader("<recipe-name>")`.
  A loader turns a spec's bank ids into the prepared input its recipe draws;
  `resolve_recipe_data(spec, bank_paths)` dispatches on `spec.recipe` the same way.

Three mechanics make it work:

1. **Decorator = self-registration.** `@register("prediction-histogram")` runs
   at import and adds the function to the dict. The author writes one decorator
   line; nothing central changes. Adding the 8th recipe touches only its own
   new module. A duplicate name raises at import rather than silently shadowing.
2. **Import for side effect.** A registry is only populated once the modules
   carrying the decorators have been imported. `charts/matplotlib/__init__.py`
   imports each recipe module precisely so their decorators run; importing the
   package therefore fills `RECIPES`. (This is why those recipe imports look
   "unused" in `__init__` — they exist for the registration side effect, and
   `F401` is per-file-ignored there.)
3. **Registry in its own module.** `RECIPES` / `register` live in `registry.py`,
   *not* the package `__init__`, so a recipe can `from .registry import register`
   without importing the `__init__` that imports the recipe — which would be a
   circular import. The `__init__` is the only place that imports the recipe
   modules; the recipe modules import only the registry.

The trade-off is the import-for-side-effect indirection (mechanic 2), which is
contained to the `__init__` + `registry.py` modules. In exchange the recipe and
loader vocabularies stay open (the contract treats `recipe` as a free-form
string owned by egm-studio), and recipes remain independent and individually
snapshot-tested.

> **`figures/loaders.py` vs the top-level `loaders/`:** the figure-data adapters
> (bank → recipe input) live in `figures/loaders.py`, next to the renderer that
> consumes them. The planned top-level `loaders/` (Blocks 6–7) is for the
> GUI's bank-reading wrappers + the phase-manifest reader. Whether the
> figure-data adapters fold into that package once it exists is an open question
> tracked in `project/roadmap.md` (Block 7).

### Import boundaries (hard rules)

- `analysis/` MUST NOT import matplotlib, pyqtgraph, or PySide6.
- `figures/` and `charts/matplotlib/` MUST NOT import PySide6 or
  pyqtgraph.
- `charts/pyqtgraph/` MUST NOT import matplotlib.
- `gui/` imports `charts/pyqtgraph/` and `figures/`; never the
  reverse.

This keeps the headless path working — `figures/` and everything
underneath it runs in notebooks, CI, and `egm-studio-render` without
a display. [ADR-005, ADR-013]

## Cross-repo dependencies

| Repo | What egm-studio uses | Trigger |
|---|---|---|
| `myocard-egm-contracts` (v0.5.2+) | Schemas: `classifier_bank`, `iafdb_bank`, `noise_bank`, `epoch_record`, `model_metadata`, `predictions`, `observation`, `phase_manifest`, `figure_spec`; the generated `Role` / `role_of` artifact-role vocabulary (v0.5.2) | Runtime dep; all schemas land in v0.5.0 [ADR-014, ADR-017, ADR-021] |
| `myocard-egm-data` (v0.4.2+) | Bank readers/writers; record + phase-artifact I/O (`phases.load_figure_spec`, `phases.load_phase_dir` added v0.4.2); `ClassifierBank.uniform_fs_hz()` (added v0.4.1) | Runtime dep [ADR-001] |
| `myocard-egm-features` (v0.1.1+) | `bundle.extract_all` for the unified view-model (v0.1.1 added the py.typed marker) | Runtime dep [ADR-002] |
| `myocard-egm-signal` (v0.2.0+) | Filter primitives; activation-peak helpers (likely Block 3+) | Runtime dep |
| `intracardiac-platform` (workspace, not a Python dep) | Reads + writes the phase manifest, observations, and figure specs (JSON) when egm-studio saves | File-system contract via cross-artifact linkage design |
| `intracardiac-papers` (workspace) | Receives the rendered figure image (gitignored) at `papers/<paper-slug>/figures/`; the figure spec itself lives in the meta repo | File-system contract via figure_spec schema |

egm-studio depends on **all five myocard-labs library repos**. It
does NOT depend on producers (egm-classifier, synthetic-egm-pipeline,
iafdb-pipeline) at the Python level — only at the data level, via
the banks they write.

**The egm-features boundary** is extract-vs-analyze: egm-features owns
per-trace *extraction* (one trace → scalar features); egm-studio's
`analysis/` owns *analysis over* those features (distribution distances,
KDEs, similarity). The KS / Wasserstein / KDE primitives operate on arrays
of already-extracted feature values, never on raw traces, so they live in
egm-studio — per the Refactor Step 6 decision that egm-features stays a
library-only extractor (no analysis workflows).

## Layout and interaction patterns

### Layout shell [ADR-025]

```
┌──────────────────────────────────────────────────────────────┐
│ Menu bar                                                       │
├──┬───────────────────────────────────┬──┬──────────────────┬─┤
│L │                                   │  │                    │R│
│e │   Main work area                  │  │  Phase artifact    │S│
│f │   ─ One full-width column OR      │  │  tree              │i│
│t │   ─ Two side-by-side columns      │  │                    │d│
│  │                                   │  │  (right sidebar)   │e│
│S │   Within each column, vertical    │  │                    │b│
│i │   stacking is allowed (e.g.       │  │  Collapses to      │a│
│d │   traces on top + table below).   │  │  icon strip.       │r│
│e │                                   │  │                    │ │
│b │                                   │  │                    │ │
│a │                                   │  │                    │ │
│r │                                   │  │                    │ │
└──┴───────────────────────────────────┴──┴──────────────────┴─┘
```

- Sidebars collapse to a thin Activity-Bar-style icon column
  (JupyterLab convention from `reference_apps.md`).
- All column / sidebar separators are draggable.
- Traces always have full window width available (collapse both
  sidebars + use one main column).
- Pair-comparison views use the two-column main area [ADR-002].

**As built (Block 4):** `MainWindow` + `CollapsibleSidebar` (in `gui/shell.py`)
implement this shell — draggable `QSplitter` columns, each sidebar folding to a
~40px Activity-Bar strip and back (the splitter drives the width, since a
`QSplitter` ignores a child's max-width; a collapsed strip is non-resizable), a
header-hosted 3-mode segmented control, and the `View > Theme` toggle.
`View > Toggle sidebar` and the in-panel buttons share one handler so the menu
checkmarks stay in sync. Region content stays placeholder until Blocks 5+.

### Interaction patterns

- **Filter-and-sort-first** as the universal entry: every view
  opens with the query / filter bar [ADR-002].
- **Pair-comparison** is a first-class UI pattern — Δfeature pairs
  and similarity-driven pairs both supported [ADR-002, ADR-020]. Both
  flows share one pane: Flow A's detail was extracted into a reusable
  `ExploreDetail` (waveforms + value table + pluggable finds) [B8g].
- **One Open-bank path, mode auto-detected** [B8]: the single Open-bank
  action builds the view-model, and `gui/sources.frame_eval_mode` reads
  whether it carries predictions (+ labels) to populate Flow B — no
  separate "load evaluated bank" entry. One filter panel narrows both
  flows.
- **Live-preview** via `@interact`-equivalent: Qt sliders bound to
  PyQtGraph redraw callbacks with debouncing; manual-trigger button
  for expensive operations [ADR-019].
- **Multi-monitor**: views can tear out into separate windows
  (Qt's `QMdiArea` / detached windows).
- **Time-axis navigation** on traces: pan + zoom via PyQtGraph mouse
  defaults; time-scale slider as a discoverability aid.
- **Theme**: dark default + light + vibrant themes via QSS, the choice
  persisted across launches (`gui/preferences.py`) [ADR-012].

## Data flow

The architectural keystone is the **unified per-trace view-model**.
For any loaded combination of banks + predictions, egm-studio
constructs one composite table:

```
Per-trace view-model columns
├── Identity:   bank_id, trace_idx, stable_artifact_id
├── Metadata:   label, patient_id, sim_id, electrode_pair_id, source, ...
├── Features:   peak_to_peak, zero_crossings, activation_position,
│               sec_peak_count, spectral_centroid, spectral_entropy,
│               dominant_frequency, sample_entropy, shannon_entropy,
│               lempel_ziv_complexity, higuchi_fractal_dimension
│               (from egm-features.bundle.extract_all)
├── ML outcomes (when a predictions bank is loaded):
│               predicted_prob, predicted_class, correctness_bucket,
│               per_trace_loss, calibration_residual
├── Similarity (computed on demand, per ADR-020):
│               similarity_to_<target_id>_along_<feature>
└── Set membership (manual / saved trace sets):
                in_set_<set_name>: bool
```

All filter / sort / pair-comparison operations run against this
composite. Storage backend is in-memory pandas; performance scales
with result-set size, not bank size, because nothing renders all
rows [ADR-011].

## Save / persistence model

egm-studio v0.1 has **no generic session persistence** [ADR-003].
But **partial persistence of meaningful work** is supported via the
unified save schema [ADR-017]:

- **Observations** — prose `description` (required) + optional trace list +
  optional `view_state` for reload. Saved as JSON in
  `intracardiac-platform/project/phases/phase_X/observations/<obs-id>.json`.
- **Trace sets** — embedded inside observations; a pure trace list
  without prose is not a thing (the discovery IS the observation).
- **Figure specs** — JSON in the meta repo at
  `intracardiac-platform/project/phases/phase_X/figure_specs/<fig-id>.json`,
  reproducible via `egm-studio-render`. Only the rendered image is written to
  the paper repo (gitignored there).
- **Phase manifest** — egm-studio appends to / updates
  `intracardiac-platform/project/phases/phase_X/manifest.json` (banks split
  into `egm_banks` + `noise_banks`) as observations and figure specs are
  saved [ADR-021].
- **Stable IDs** — every saved artifact gets a role-prefixed +
  date-stamped ID: `obs_my_observation_2026-06-25`,
  `fig_F-1-5-2_2026-06-25`, etc. [ADR-022]
- **Scratch mode** — when no phase is loaded, saves go to
  `intracardiac-platform/project/scratch/`. "Promote to Phase"
  action moves + indexes into the proper phase.

## Test strategy [ADR-013]

Three-layer pyramid:

1. **Unit tests (pytest)** — data-prep, figure recipes, query/filter
   logic, save-state serialization. Pure functions; no GUI; runs
   without a display. The bulk of the surface area lives here.
2. **Integration tests (pytest-qt)** — "data flows through the views
   correctly." `xvfb-run` in CI. Small, contract-shaped.
3. **Snapshot tests (pytest-mpl)** — rendered-figure regressions.
   Snapshots live in `tests/snapshots/`; regenerate explicitly with
   `--mpl-generate-path`.

**Avoid:** pixel-coordinate assertions, click-here-see-that tests,
font-availability assumptions beyond what pytest-mpl handles.

## Distribution [ADR-007]

- `pip install myocard-egm-studio`
- Two console scripts declared in `pyproject.toml`: `egm-studio` and
  `egm-studio-render`.
- No PyInstaller bundle, no Docker image, no web deploy for v0.1.
- Future web frontend (if ever needed) reuses `figures/` and
  `loaders/`; only `gui/` would be a from-scratch rewrite.

## Documentation [ADR-008, ADR-009]

- No in-app help / tour in v0.1; documentation is external.
- `docs/usage.md` is the user manual.
- Markdown in repo for v0.1; MkDocs Material is the upgrade path
  when content density justifies it.

## Forward-looking items

Concrete open follow-ups with trigger conditions (full text in the
"Open questions" section of `design.md`):

- **Joint similarity metric** — ADR-020 follow-up; trigger: v0.1
  usage clarifies the trade-offs.
- **ADR-019 live-preview perf tuning** — trigger: real-bank perf
  forces a strategy change at implementation time.
- **Bottom panel** (JupyterLab "down area") — trigger: a use case
  emerges that the resizable-column layout doesn't accommodate.
- **Phase 8+ live playback mode** (task #311) — animated time
  cursor sweep; rides on ADR-024's composable trace widget substrate.
- **Plugin architecture** [ADR-006] — trigger: external contributors
  want to extend egm-studio with new views / chart types.
