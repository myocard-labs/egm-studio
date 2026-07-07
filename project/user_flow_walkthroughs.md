# egm-studio — user-flow walkthroughs

Screen-by-screen, as-built walkthroughs of what egm-studio does. Each flow opens
on a concrete scenario, then follows it click by click through the app as it
ships today. Read these to learn what the app *does*; read
[`architecture.md`](architecture.md) for how it's built and
[`design.md`](design.md) for why.

The app is **one shell with four top-level modes**, switched from the header's
segmented control:

- **Signal exploration** (Flow A) — filter and inspect EGM traces from loaded banks.
- **ML diagnostics** (Flow B) — compare model runs over an evaluated predictions bank.
- **Paper-figure prep** (Flow C) — edit a figure spec beside a live preview, then render.
- **Noise** (Flow D) — browse the raw segments of an IAFDB noise bank.

All four share one data layer: every bank / run / predictions file is read
through `myocard-egm-data` against `myocard-egm-contracts` schemas [ADR-001], and
loaded data is shared across modes so switching modes never re-reads a file
[ADR-015]. Saved work (observations, figure specs) is written back into the
phase-organized meta repo as **JSON** — see [Saving work](#saving-work-cross-cutting).

> **Scope.** These are coarse, action-level walkthroughs ("open a bank," "filter
> by X," "compare traces"), not per-widget UI specs. Where a step maps to a module
> or an ADR, a pointer is given inline. IAFDB carries no fibrosis ground truth, so
> wherever it appears the action is *qualitative inspection*, not metric
> computation [[feedback-iafdb-unlabeled-no-ml-validation]].

---

## Flow A: Signal exploration

**Scenario.** A user just ran synthetic-egm-pipeline overnight with the
Courtemanche cell-model swap (a Phase 1.5 intervention), writing
`synthegm_v1_5_courtemanche.cbank.h5`. Before training, they want to eyeball the
traces: do they look qualitatively different from the prior Aliev-Panfilov
synthetic data, and any closer to IAFDB?

**Where it lives:** `gui/views/signal_exploration.py` — the **Summary / Explore /
Scatter** tabs over the unified per-trace view-model (`view_model/builder.py` +
`combine.py`).

1. **Open the bank.** *File ▸ Open bank* → the Courtemanche `.cbank.h5`.
   egm-studio reads it through egm-data, extracts the egm-features bundle, and
   lands on the **Summary** tab: trace count, class balance, and an 11-panel grid
   of per-feature distributions (one per bundle feature) over the whole bank. The
   grid uses per-panel min/max size clamps plus a user-scalable global factor,
   wrapping to more rows when the window is too narrow [ADR-018].
2. **Add the IAFDB bank.** *File ▸ Open bank* again → the IAFDB bank. A second
   open *adds* rather than replaces: both banks pool into one view-model
   (`combine_view_models`, global `row_id`), and the Summary grid overlays them as
   KDEs with a per-bank legend. Multiple banks loaded at once is the default, not
   one-at-a-time.
3. **Filter.** The user notices the synthetic `sample_entropy` has a high-side tail
   IAFDB lacks. In the **Explore** tab's filter panel (`gui/widgets/filter.py`) they
   compose `source == synthetic AND sample_entropy > 1.5`; the result table
   (`gui/widgets/result_list.py`) shows the ~200 matches. Filters compose across
   features, metadata, ML outcomes, similarity, and source [ADR-002].
4. **Sort and pick.** They sort the table by `sample_entropy` descending and click
   the top row. The shared **detail** pane (`gui/widgets/explore_detail.py`) opens:
   the EGM waveform, the 11 feature values, and metadata (`sim_id`,
   `electrode_pair_id`, fibrosis density, label).
5. **Compare across banks.** They want the nearest IAFDB trace along
   `sample_entropy`. *Find similar in other source* → pick the feature → the
   view-model returns the nearest trace in each other bank (`view_model/similar.py`)
   and the detail becomes a **source-first 3-pane compare**
   (Aliev-Panfilov | Courtemanche | IAFDB) with per-feature deltas annotated. v0.1
   ships **per-feature** similarity only; a joint multi-feature metric is deferred
   [ADR-020].
6. **Scatter.** The **Scatter** tab plots `(sample_entropy, peak_to_peak)` for the
   current result, colored by source. The synthetic high-entropy traces cluster in
   a region IAFDB never reaches — the Courtemanche swap is *adding* a
   synthetic-only feature-space region. Clicking a point opens it in the detail
   pane; very large scatters can be down-sampled from Settings [Block 11].
7. **Save the observation.** *File ▸ Save observation* records the finding — see
   [Saving work](#saving-work-cross-cutting). The snapshot includes the loaded
   banks, the filter, and the selection, so *Open observation* later reloads the
   view, not just the text.

---

## Flow B: ML diagnostics

**Scenario.** A user just finished training v1.5 with the activation-peak-anchoring
intervention; the v1 baseline is still on disk. They want to (a) confirm v1.5 didn't
regress on synthetic in-distribution performance, (b) see whether v1.5's IAFDB
output distribution is less saturated than v1's, and (c) drill into the IAFDB
traces where v1 and v1.5 disagree most.

**Where it lives:** `gui/views/ml_diagnostics.py` — the **Output / Metrics /
Training / Explore** tabs. The mode populates automatically from what a loaded bank
carries; there is no separate "load evaluated bank" entry.

1. **Open the bank.** Flow B uses the *same* *File ▸ Open bank* action as Flow A.
   `build_view_model` joins ML-outcome columns when the traces carry predictions
   (`view_model/ml_outcomes.py`), and the shell reads the result with
   `gui/sources.frame_eval_mode` to decide what Flow B shows [ADR-015]:
   - **No predictions** → Flow B stays idle (nothing to diagnose); the bank still
     opens normally in Flow A.
   - **Predictions, no truth labels** (the IAFDB shape) → qualitative only: the
     **Output** tab's P(positive) histogram and per-trace **Explore**. No metrics
     [[feedback-iafdb-unlabeled-no-ml-validation]].
   - **Predictions and truth labels** (a synthetic eval bank) → the full **Metrics**
     suite: ROC, confusion matrix, calibration.
2. **Open the training run** *(optional entry point).* *File ▸ Open training run* →
   the v1.5 `run.json` (+ sibling `metrics.csv`; the checkpoint is referenced by
   path, loaded lazily). The **Training** tab shows loss + AUROC vs epoch, train and
   val on shared axes — a quick "did training complete cleanly?" check.
3. **Add the v1 baseline.** Open v1's run and predictions bank too. Every view
   overlays per run (one color each): the Training curves, the **Output** tab's
   P(positive) histograms, and the **Metrics** tab. On synthetic val, v1.5 retains
   v1's AUROC (~0.999), maybe slightly better calibrated — no regression.
4. **Read the IAFDB output.** On the two IAFDB predictions banks, the **Output**
   histograms overlay across *N* sources: v1 is pegged at 0.999 (right edge); v1.5
   has a visible left tail to ~0.85. Modest but real de-saturation.
5. **Query the disagreement.** The shell's shared filter panel drives Flow B too,
   over the *joined* view-model — feature columns, prediction columns, and derived
   per-model deltas alike [ADR-002]. The user filters
   `|v1_prob − v1_5_prob| > 0.10` (~50 traces) and sorts by `v1_prob` descending to
   find where v1 was most-confident-fibrotic but v1.5 backed off.
6. **Drill in.** They click a trace; the shared **Explore** detail shows the waveform
   once, both prediction badges (v1: 0.998 · v1.5: 0.86), and the 11 features. The
   detail's pluggable finders locate each failure's nearest correctly-classified
   counterpart (`view_model/similar.py`). *(The per-model attention overlay is the
   F-2.11 recipe — a v0.2 item, not yet built.)*
7. **Save exemplars.** They save the interesting traces as an observation (Flow A's
   *Save observation*, shared here) — the bridge that later feeds a Flow C figure.

---

## Flow C: Paper-figure prep

**Scenario.** A user is writing the Phase 1.5 paper. They need F-1.5.2 (synthetic
vs IAFDB feature distributions, 11-panel small-multiples) as a
publication-quality file to drop into the LaTeX source.

**Where it lives:** `gui/views/paper_figure_prep.py` — a curated per-recipe spec
form (`gui/widgets/figure_form.py`) beside a live preview
(`gui/widgets/figure_preview.py`).

1. **Switch to figure-prep mode.** The center pane splits: **spec form on the
   left, live preview on the right.** The template list mirrors the recipe catalog
   in [`paper_figure_inventory.md`](paper_figure_inventory.md) — data-driven from
   the recipe registry, not hardcoded.
2. **Pick a template.** The user picks `feature-distribution-overlay` for F-1.5.2.
   The form renders exactly the fields that recipe expects: data source(s) (one
   per group), feature subset (default all 11), panel layout, styling (palette,
   font, DPI, size, KS/Wasserstein annotation toggle), and output path + format.
3. **Configure groups.** They add two groups (cap of three — 4+ overlaid groups go
   illegible): "Synthetic v1.5 (Courtemanche)" and "IAFDB". A later sim-comparison
   figure would add a third, "Synthetic v1 (Aliev-Panfilov)".
4. **The preview is the real thing.** The right pane is a **raster of the actual
   matplotlib recipe** (`figures.preview_png`, the same `draw_figure` + `paper_style`
   pipeline as export), so **preview == export** — not a pyqtgraph twin [ADR-019].
   Form edits debounce and the resolve runs on a worker thread so a large bank
   doesn't freeze the window; expensive recipes gate behind a **Refresh** button.
5. **Iterate on styling.** They pick the project palette (color-blind safe), bump
   the font to 9pt, turn on the KS-distance annotation, and adjust titles — each
   change re-renders the preview.
6. **Render.** *Render full* writes to the spec's own `output.path` (a vector PDF,
   `pdf.fonttype=42`, so figure text stays selectable in the compiled paper);
   an existing output prompts to overwrite. The rendered image lands in
   `intracardiac-papers/papers/<slug>/figures/` (gitignored there), while the
   **spec** is the source of truth and lives as JSON in the phase — see
   [Saving work](#saving-work-cross-cutting) [ADR-023].
7. **Reproduce headlessly.** The same spec runs from the terminal with
   `egm-studio-render <spec>.json --phase <phase-dir>` — same plotting code, no
   shell [ADR-005]. In the app, the **Phase tree** drives the figure lifecycle:
   *Edit / View / Generate / Regenerate*, the menu adapting to whether the image
   already exists (`view_model/figure_output.py`).

---

## Flow D: Noise

**Scenario.** A user wants to spot-check the raw IAFDB noise segments a curation
run selected — before they get mixed into a synthetic bank.

**Where it lives:** `gui/views/noise_exploration.py` over `view_model/noise.py`;
its own **fourth top-level mode** [ADR-027].

1. **Open a noise bank.** Right-click a noise bank in the Phase tree ▸ **View noise
   segments** (or open one directly). Because a noise bank is raw IAFDB segments —
   not the loaded-bank view-model Flow A operates on — it gets its own mode rather
   than a Flow A tab.
2. **Browse.** A **mode-driven left rail** replaces *Banks & filters* with the
   noise controls: an overview, record/channel filters, and the segment table.
3. **Inspect.** Selecting a segment plots it, aspect-capped so a single trace in a
   tall pane reads as a signal band rather than a stretched line.

---

## Saving work (cross-cutting)

Flows A/B save **observations**; Flow C saves **figure specs**. Both go through one
save layer (`save/`) and are curated by the right-rail Phase tree
(`gui/widgets/phase_tree.py`). egm-studio v0.1 has no generic session persistence,
but this *partial* persistence of meaningful work is first-class [ADR-003 → ADR-017].

- **Observations** (*File ▸ Save observation*) — required prose plus optional
  parent-observation links, plus a snapshot of the current **view state** (loaded
  banks, the filter with its match type, the selection) captured by `save/capture.py`.
  *Open observation* reloads that view; *Edit observation* revises it.
- **Figures** (Flow C *Save into…*) — the entry records the banks / models /
  observations the figure consumes and any observations it illustrates.
- **Save target.** With a phase open, both offer **Add to scratch / Add to phase**.
  With no phase open, saves go to **scratch** — a per-user, Settings-editable
  app-data folder that is a full *mini-phase* (its own `manifest.json`, the same
  tree + status dots + viewers). **Promote to phase** moves authored files into the
  phase folder and re-indexes producer pointers in place [ADR-017 → ADR-026].
- **Stable IDs.** Every authored artifact gets a role-prefixed, date-stamped id
  (`obs_…_2026-06-25`, `fig_…`), `save/ids.py` [ADR-022].
- **Auto-add dependencies.** Promoting — or saving/loading — into a phase also
  pulls the artifact's scratch-resident dependency closure along (transitive,
  cycle-safe; `view_model/dependencies.py`), unless a Settings toggle is off.
- **Dependency-aware verification.** A well-formed artifact whose referenced ids
  aren't resolvable reads **amber "unresolved"** with a tooltip naming the missing
  id; resolution is cross-scope (a scratch item sees scratch + the loaded phase, a
  phase item sees the phase only) [ADR-026].
- **Manual curation** (Block 10g). **Add to phase** indexes an existing artifact
  (producers as path-pointers *without opening them*; a figure/observation copied
  into the phase folder); **Remove from phase** unindexes (deleting authored files,
  leaving producer files in place).

The user-facing version of this flow is [`../docs/saving_work.md`](../docs/saving_work.md).

---

## How these flows shaped the design

These walkthroughs were the primary design input for the Block 0 ADRs: rather than
spec the UI top-down, each flow was written in prose to shake out what the shell
actually needed. The requirements that accumulated became the following ADRs, all
now resolved in [`design.md`](design.md):

| ADR | Surfaced by | Decision (as resolved) |
|---|---|---|
| ADR-015 | all three flows share a data layer | One GUI, four modes — not separate apps. |
| ADR-016 | interactive + headless needs | PySide6 + pyqtgraph (GUI) + matplotlib (export). |
| ADR-017 | Flow A save, Flow B exemplars | Unified Save schema, written to the meta repo (extended by ADR-026). |
| ADR-018 | Flow A summary grid | Responsive sizing — per-panel clamps + global scale + grid-wrap. |
| ADR-019 | Flow C live preview | Preview is the real matplotlib raster (preview == export). |
| ADR-020 | Flow A cross-bank compare | Per-feature similarity in v0.1; joint metric deferred. |
| ADR-021 | Flow A/C save targets | Per-phase manifest in `intracardiac-platform`. |
| ADR-022 | Flow B model linkage | Stable cross-artifact IDs (drove egm-contracts v0.5.0). |
| ADR-023 | Flow C export | Figure image is gitignored + regenerable from its spec. |
| ADR-026 | Save flow (Block 10) | Scratch mini-phase + dependency-aware curation. |
| ADR-027 | Noise (Block 10g) | Noise is a fourth top-level mode, not a Flow A tab. |

---

## Status

Flows A–C shipped in **Blocks 7–9**, the Save flow in **Block 10**, and manual
curation + the Noise mode (Flow D) in **Block 10g**. The prose above is as-built;
deviations from the original Block-0 drafts are folded into the steps rather than
tracked as a changelog (see git history for the design-time versions).

**Still open:** the per-model attention-overlay recipe (F-2.11, v0.2);
live-preview performance on very large banks (Post-v0.1); and the post-write
scan-and-validate hook into `intracardiac-platform`'s `validate_manifest.py`.
