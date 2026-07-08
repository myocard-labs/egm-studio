# egm-studio — roadmap

Future work only. Shipped history lives in [`CHANGELOG.md`](../CHANGELOG.md) at release
granularity and in the **git log** block-by-block (the v0.1.0 build ran as Blocks 1–14; that
detailed build log was retired from this file when the roadmap was trimmed to future-only).
Internal doc; public users read the README + `docs/getting-started.md` + `docs/usage.md`.

v0.1.0 shipped the whole app — the Qt shell + four modes (signal exploration, noise, ML
diagnostics, paper-figure prep), the eight Phase-1.5 paper recipes, the Save / Phase-tree
curation flow, the performance pass, and the headless `egm-studio-render` CLI. What remains is
later-phase paper recipes, the Phase-1.5 realism-**analysis** upgrades, a batch of small items
gated on coordinated egm-contracts bumps, and deferred performance work (each with a trigger).

Work lands here as it's identified, sits in the **Backlog** until a phase-planning session
promotes it into a **Phase** cluster, then moves to the CHANGELOG once shipped. Phase clusters
mirror the science Project Phases in `intracardiac-platform/project/project_plan.md`; items
scheduled into cross-cutting Phase work carry a `→ tracked at intracardiac-platform Phase X`
annotation. Architectural decisions are recorded as ADRs in [`design.md`](design.md); the
recipe inventory is [`paper_figure_inventory.md`](paper_figure_inventory.md).

## Phase 1.5 — sim-realism (analysis upgrades)

### Weighted multi-feature distance — joint similarity + realism aggregate (ADR-020)

The v0.1 similarity is per-feature (one axis at a time) and the realism aggregate is an
unweighted KS distance. Once the Phase-1.5 realism study says *which* features matter, upgrade
to a weighted joint distance: standardize each feature's distance by its pooled spread
(`docs/theory.md` §2.3 → dimensionless), add config-sourced importance weights, then apply as
(a) a joint nearest-neighbour metric for `trace-pair-gallery` (the ADR-020 resolution) and (b) a
weighted aggregate for `bar-chart-with-deltas` — unlocking weighted **Wasserstein** (whole-
distribution shift) over the max-CDF-gap KS. Weights are downstream of the realism investigation,
so this follows it. A rigor upgrade to the realism *analysis*, not a Phase-1.5 *figure* blocker
(the per-feature figures work today).

> → Tracked at `intracardiac-platform/project/project_plan.md` Phase 1.5. Cross-cutting plan
> lives there.

### Single-activation IAFDB windows for sim-vs-real comparison

Sim-vs-IAFDB feature / trace comparisons (F-1.5.2, F-1.5.7, …) are confounded: IAFDB segments
carry multiple activation waves while Phase-1 synthetic is single-beat. Segment IAFDB to
one-activation windows before feature extraction. Fix-location is TBD — a producer-side
segmentation step in iafdb-pipeline vs. an egm-studio comparison-loader hook — and it naturally
resolves once multi-beat synthetic lands (Phase 4).

> → Tracked at `intracardiac-platform/project/project_plan.md` Phase 1.5. Cross-repo.

## Phase 2+ — later-phase paper figures

### P1 / P2 / P3 figure recipes

v0.1 ships only the Phase-1.5 paper's eight P0 recipes. Each later paper (Phase 2 multiclass,
Phase 3 pattern, …) brings its own recipe set from `paper_figure_inventory.md`, added a
paper-worth at a time as that paper enters its writing phase — each a new recipe in
`charts/matplotlib/` (+ a pyqtgraph twin only if it needs live display) with a snapshot test +
example spec, extending `docs/theory.md` and the inventory as they land.

> → Tracked at `intracardiac-platform/project/project_plan.md` (per-phase paper milestones).

## Phase 4 — multi-beat

### Multi-trace `TraceContainer` (N > 1)

The `TraceContainer` already supports N stacked shared-X traces; wiring a multi-trace UI on top
becomes relevant when Phase-4 multi-beat windows arrive. Small — the substrate is in place.

> → Tracked at `intracardiac-platform/project/project_plan.md` Phase 4.

## Phase 8 — live playback

### Activation playback / animation

An animation loop + moving-cursor primitives over a trace (or a substrate map) for the Phase-8
work. Medium; no v0.1 substrate beyond the static `TraceWidget`.

> → Tracked at `intracardiac-platform/project/project_plan.md` Phase 8.

## Backlog (unscheduled — promoted into a phase at a planning session)

### egm-contracts-gated `view_state` / manifest items (refactor-cleanup batch)

Three small egm-studio changes, each blocked on a coordinated egm-contracts bump, batched to
land with the contracts refactor-cleanup pass (see egm-contracts roadmap → Backlog):

- **Structured filter / sort in observation `view_state`.** Reloading a saved observation's
  filter is best-effort today: `view_state.filter` / `sort` are free-text strings, so *Open
  observation* re-parses egm-studio's own `describe_filter` rendering and only re-applies when
  it round-trips exactly (else it surfaces the raw text for manual re-entry). Banks + pinned
  traces already reload exactly. Needs a **structured** filter field (conditions + combine) on
  the contracts `view_state`.
- **Active view / tab in observation `view_state`.** An observation can be made about a chart on
  any tab, but `view_state` records only banks + filter + traces, so *Open observation* always
  lands on Signal-exploration ▸ Explore. Needs an `active_view` (tab id) field.
- **Optional `produced_by` on manifest entries.** When egm-studio indexes a *loaded* producer
  artifact into scratch or a phase, the entry schema requires `produced_by_package` /
  `produced_by_version`, but the files record none — so curator-indexed entries stamp a sentinel
  (`"unknown"` / `"0"`, `save/producer.py`). Making the fields optional drops the sentinel. (The
  deeper fix — producers stamping provenance into their files — is a separate cross-repo add.)

### Per-condition filter bank scoping

The "Match all that exist" mode only *skips* a condition for banks that lack the field; filtering
a field that's *shared* across banks still applies to all of them. Add per-condition bank scoping
— a bank multiselect on each `FilterSpec` condition in `gui/widgets/filter.py`. Small.

### LaTeX / markdown text export for `summary-table`

`summary-table` renders a table image; the `figure_spec` `output.format` enum is pdf/png/svg only.
When a paper wants an *editable* table, add a `tex` / `md` format (a coordinated egm-contracts
`figure_spec` bump) + a text branch in `figures/render` (`pandas.to_latex` / `to_markdown` of the
`TableData` instead of `savefig`). Paper-driven.

### Rich "Show metadata" viewer

The metadata dialog is a plain read-only text pane. Upgrade to a browser-style JSON viewer
(collapsible nodes + per-type colouring) via a `QTreeView` + `QAbstractItemModel`. Needs
`view_model/artifact_metadata` to also expose a **structured** (nested) form — the run / figure /
observation records already have `model_dump()` dicts that map straight to a tree; the bank +
noise summaries would need restructuring from their hand-built strings. Keep the text form as a
copy-to-clipboard fallback. Low priority.

### Bottom panel ("down area", ADR-025 deferred)

The shell layout reserved the idea of a JupyterLab-style bottom panel. Build it if a use case
emerges that the resizable-column layout doesn't accommodate. Small.

### Deferred performance work (with triggers)

Standard techniques deliberately **not** built in the v0.1 perf pass — each revived only when its
trigger fires (full detail + the "one tiered store" rationale in
[`optimization_survey.md`](optimization_survey.md)):

- **Escalate to a true worker thread (generalized).** Move heavy compute off the UI thread
  entirely instead of the cooperative pump — applies to any prohibitive compute, not just the KDE
  grid. Requires separating compute from render (e.g. pulling the scipy KDE math out of the
  pyqtgraph draw), which also feeds the tiered store (cache computed curves) and fixes the
  theme-change KDE recompute (Known issues). **Trigger:** a compute cost grows past what a pumped
  dialog can hide, or full mid-rebuild interactivity becomes a requirement.
- **Memory-map the source (egm-data) + approximate stats (t-digest / reservoir).** **Trigger:**
  banks grow past what fits in RAM (IAFDB fits today).
- **Accelerate the O(T²) sample-entropy kernel (Numba / Cython, in egm-features).** **Trigger:**
  the feature math grows in complexity, or multiple IAFDB-sized banks become routine (one IAFDB
  bank's ~couple-minute extraction is acceptable).
- **Shrink the frame (dtype downcast + categorical) + copy-on-write.** **Trigger:** the memory
  ceiling is regularly overflowed and disk-tier thrash slows the loop.

## Known issues

- **Theme-change recomputes the KDE grid unpumped.** `set_style` re-runs the 11-panel KDE
  without the cooperative progress pump, so a theme switch briefly freezes on a large loaded bank.
  The natural fix is the tiered store caching *computed curves* (pairs with the generalized
  worker-thread escalation above).

## Won't-do (design rejections, documented to save the question)

- **Density / hexbin scatter for large N.** Rejected for the feature scatter (B11): it kills
  click-to-select and two overlaid density fields read muddy. Opt-in uniform point-decimation is
  the chosen path; the scatter's job is interactive selection, not density visualization.
- **`fetchMore`-streamed result table.** Rejected (B11): a streaming table sees only fetched rows,
  but filter / select / match must run over **all** rows. The virtualized `QAbstractTableModel`
  over the full in-memory frame is correct and fast.
- **pyqtgraph fast-preview for Flow C.** Rejected (ADR-019): only one of the eight recipes has a
  pyqtgraph twin, and a preview that differs from the export defeats a figure composer. The
  preview rasters the *real* matplotlib recipe, pixel-identical to the PDF by construction.

## Open architectural questions for later

- **Plugin architecture (ADR-006).** A large refactor to let external contributors extend the
  app; only worth it once there are external contributors wanting to.
- **Web frontend.** A `gui/` rewrite for the browser that reuses `figures/` + `loaders/` +
  `analysis/` + `charts/matplotlib/` unchanged. Only if desktop-only becomes limiting.
- **Per-trace stable IDs in banks.** Traces are keyed by integer index today; a real
  reproducibility break from that fragility would justify an egm-contracts revision + cascade to
  stamp per-trace ids.
- **HuggingFace Datasets for active bank sharing.** If the GitHub-Releases bank-sharing workflow
  gets painful for multiple collaborators; the changes are producer-side (egm-studio unchanged).
  Ties to [[project-publishing-timing]].
- **Live-preview perf revision (ADR-019).** If real-bank preview latency forces a strategy change,
  a successor ADR supersedes ADR-019 + its implementation.
