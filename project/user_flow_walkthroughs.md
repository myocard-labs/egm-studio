# egm-studio — user-flow walkthroughs

Prose-at-click-level walkthroughs of the three user workflows
egm-studio is being designed to support. Each flow starts from a
concrete anchor scenario (a real situation Daniel might be in) and
follows him step-by-step through what he'd do.

> **As-shipped note (egm-contracts v0.5.0):** the linkage formats are **JSON,
> not YAML**; the observation prose field is `description` (not `body`); the
> manifest stores banks as `egm_banks` + `noise_banks`. Read the YAML / `body`
> references below accordingly — see the reconciliation note in
> `project/architecture.md`.

**Why this exists:** writing user flows in prose shakes out UI shape
better than top-down design. As we walk each flow we accumulate a
list of UI requirements + data-model needs + open design questions,
collected in the "Design questions surfaced" section at the bottom.
That accumulated list is the primary input to **ADR-015**
(one-vs-many GUI) and **ADR-016** (framework).

## Conventions

- **Granularity:** Coarse — actions like "load bank," "filter by X,"
  "view trace." Not every button or pixel.
- **Mode framing:** Where a flow implies the GUI has distinct *modes*
  or *workspaces*, that's called out (and feeds ADR-015).
- **Cross-flow patterns:** Some operations show up in multiple flows.
  Worth pulling out into the global summary at the bottom rather
  than re-listing per flow.
- **Hard-constraint reminder:** No ML metrics on IAFDB per
  [[feedback-iafdb-unlabeled-no-ml-validation]]. Where IAFDB shows
  up in these flows, the action is qualitative inspection, not
  metric computation.

---

## Flow A: Signal exploration

**Anchor scenario:** Daniel just ran synthetic-egm-pipeline overnight
with the Courtemanche cell-model swap (a Phase 1.5 intervention).
The bank wrote out to `~/data/banks/synthegm_v1_5_courtemanche.cbank.h5`.
Before kicking off training, he wants to *eyeball* the produced
traces — do they look qualitatively different from the prior
Aliev-Panfilov synthetic data, and do they look any closer to
IAFDB?

### Walkthrough

1. **Launch egm-studio.** Default landing view: a "recent banks"
   list + a load button.
2. **Load the new synthetic bank.** File picker → pick the
   Courtemanche `.cbank.h5`. Studio reads it via
   `myocard_egm_data.banks.load_synthetic_bank_as_classifier`
   (per ADR-001), then shows a **bank-summary view**:
   - Total trace count, class balance, source provenance from the
     bank's run record.
   - Thumbnail-grid: 11 small histograms, one per egm-features
     bundle feature, computed over all traces in the bank. Gives
     immediate "what does this bank look like" intuition.
   - **Responsive sizing:** the 11-panel grid needs to behave well
     across screen sizes (laptop 13" → external 27"). Naive
     "fit-to-window" scaling either crowds the panels at small
     sizes or wastes space at large ones. **Strategy: per-panel
     min/max size clamps with a user-selectable global scale
     factor.** When the window is too narrow to fit all 11 at the
     min size, the grid wraps to more rows; when too wide for max
     size, panels stay at max with extra whitespace. The global
     scale factor lives in user preferences and survives across
     sessions. *Tracked as ADR-018 — responsive UI sizing strategy
     — in the proposed-new-ADRs list at the bottom.*
3. **Load IAFDB bank in parallel** (for the comparison Daniel is
   after). Studio supports having **multiple banks loaded
   simultaneously** — the bank-summary view becomes side-by-side
   with the synthetic on the left, IAFDB on the right, same 11
   histograms overlaid.

   *(Implication: multi-bank loading is a first-class capability.
   Not "open one bank, close it, open another.")*
4. **Apply a filter.** Daniel notices the synthetic
   `sample_entropy` distribution has a long tail on the high side
   that IAFDB doesn't have. He wants to see those high-entropy
   synthetic traces. Filter UI: `data_source == synthetic` AND
   `sample_entropy > 1.5`. Result list: ~200 matching traces.
5. **Sort the result list.** Orders by `sample_entropy` descending
   so he sees the most-extreme cases first.
6. **Pick a trace.** Clicks the first row. **Per-trace detail view**
   opens:
   - EGM waveform plot (full trace, scrollable / zoomable).
   - 11 feature values displayed as a table or radial plot.
   - Metadata: `sim_id`, `electrode_pair_id`, fibrosis-density
     value, label.
7. **Open up to two comparison traces** (cap at 3 total —
   beyond 3 the comparison gets cluttered and bank-level
   histograms become the more informative view). Wants to know
   "what does an IAFDB trace with similar `sample_entropy` look
   like, and how do the Aliev-Panfilov and Courtemanche synthetic
   traces differ from it?" Clicks "find similar in other bank" →
   per-feature similarity dropdown (pick `sample_entropy`) → pulls
   up the nearest IAFDB trace along that one feature axis. Then
   loads a third trace: the matched Aliev-Panfilov synthetic from
   the prior bank. Detail view becomes a **3-pane side-by-side:
   Aliev-Panfilov | Courtemanche | IAFDB**, with feature deltas
   annotated between adjacent pairs.

   **Similarity metric note:** v0.1 ships **per-feature
   similarity** only ("nearest along `sample_entropy`," "nearest
   along `peak_to_peak`", etc.). A joint multi-feature similarity
   metric (Euclidean over normalized features? learned embedding?
   per-feature weighted average?) is interesting but needs more
   design thought before locking — deferred to a future ADR. The
   per-feature variant is enough to support the diagnostic
   workflows in flows A and B without forcing the joint-metric
   decision now.
8. **Switch to feature-distribution scatter.** From the per-trace
   detail view, navigates to a 2D scatter of `(sample_entropy,
   peak_to_peak)` for the current filter result, colored by data
   source. Sees the synthetic high-entropy traces cluster in a
   region IAFDB doesn't reach. **Observation: the Courtemanche
   intervention is *adding* a synthetic-only feature-space
   region, not removing one. That's possibly bad.**
9. **Save the observation.** Wants to remember this so it makes it
   into the Phase 1.5 paper notes. Saves a short annotation
   (free-text) along with the current view state (which banks were
   loaded, the filter, the 3 traces being compared) to a file.

   **The save target is in the meta repo, NOT in egm-studio.**
   The observation is a project-level artifact — it relates back
   to high-level Phase 1.5 goals, not to anything egm-studio
   itself owns. Storage path is something like
   `intracardiac-platform/project/phases/phase_1_5/observations/`
   (specifics TBD per the per-phase manifest discussion below).
   egm-studio just writes the file; the meta repo keeps the
   history. The only downstream consumer of these observations is
   eventually `intracardiac-papers` when the paper gets written.

   *(Implication: requires a small persistence mechanism. The
   v0.1 form is a single unified Save schema covering both
   observations AND saved trace sets, since both are "I just
   noticed something cool, save it for later." This is a meaningful
   amendment / partial-supersede of ADR-003 "no session
   persistence" — flagged for a focused deeper-discussion session
   below.)*
10. **End session.** Closes the app. Tomorrow he'll either re-open
    the named view to dig deeper, or hand the observation list to a
    follow-up training run.

### What this flow needs from the UI

- **Multi-bank loading + parallel display.** Not "one bank at a time."
- **Bank-summary view** as the default post-load landing, with
  **responsive thumbnail-grid sizing** (per-panel min/max clamps +
  user-selectable global scale factor; new ADR-018).
- **Composable filter UI** — numeric thresholds + categorical
  equality + boolean composition (`data_source == X AND
  sample_entropy > Y`).
- **Sortable result list** with arbitrary feature columns as the
  sort key.
- **Per-trace detail view** with waveform + features + metadata.
- **N-pane (up to 3) comparison view** that can hold traces from
  the same or different banks. Above 3 forces the user back to
  bank-level histograms.
- **Per-feature similarity-driven trace lookup** in v0.1. Joint
  similarity metric deferred (ADR-020 reframed).
- **Feature-distribution scatter view** with interactive
  panning / zooming + per-point coloring.
- **Observation / trace-set save mechanism, writing to the
  meta repo** (NOT to egm-studio's own state). Shared schema
  across observations + saved trace sets — see ADR-017 below.

---

## Flow B: ML diagnostics (v1 vs v1.5 IAFDB output comparison)

**Anchor scenario:** Daniel just finished training v1.5 with the
activation-peak-anchoring intervention. The v1 baseline is still on
disk from a few weeks ago. He wants to (a) confirm v1.5 didn't
regress on synthetic in-distribution performance, (b) see whether
v1.5's IAFDB output distribution is less saturated than v1's, and
(c) drill into specific IAFDB traces where v1 and v1.5 disagree
most — looking for a *why*.

### Walkthrough

1. **Launch egm-studio.** Same shell as Flow A. Probably implies a
   mode-switch widget — "I'm here to do ML diagnostics, not signal
   exploration" — though under the hood much of the data layer is
   shared.

   *(Implication: probably a **mode** concept in the shell. Could be
   tabs at the top, a left-rail mode picker, or a Cmd+K command
   palette. Decision for ADR-015 / ADR-016.)*
2. **Load training run.** File picker on the v1.5 `run.json`. Studio
   loads the run.json + sibling `metrics.csv` + the `best.pt`
   reference (just the path — actual checkpoint loading is lazy).
   Default landing: **training curves view** — loss + AUROC vs
   epoch, train + val on shared axes. Sanity check: did training
   complete cleanly?

   *(No separate "Load Evaluated Bank" entry — **amended 2026-07-04**.*
   The training-run entry point above is one way in. The bank way in
   is just the ordinary **Open bank** action — the same one Flow A
   uses; there is no second "load evaluated bank" button. Studio
   builds one view-model per loaded bank, and when the traces carry
   predictions `build_view_model` joins the ML-outcome columns (B8a);
   the shell reads the result with `frame_eval_mode` and populates
   Flow B automatically. Three cases:
   - *No predictions at all* → Flow B stays in its landing state
     (nothing to diagnose). No warning, no refusal — the bank still
     opens normally in Flow A for raw-trace inspection.
   - *Predictions but no truth labels* (the IAFDB shape) → Flow B
     shows the qualitative-only analysis (output histogram, per-trace
     inspection, attention overlay). No metrics.
   - *Predictions AND truth labels* (synthetic eval bank, or anything
     with ground truth) → Flow B shows the full metric suite (ROC +
     confusion + calibration + per-class histograms + drill-down on
     misclassifications).

   This means a Phase 1.5 evaluation can target either real IAFDB
   data OR a held-out synthetic eval bank built with deliberately
   different sim parameters than train/val — the GUI's analysis
   surface adjusts automatically based on what the loaded set
   contains. The branching lives in the bank-load handler, not in a
   mode menu the user picks from. **Why the change:** a bank either
   has predictions or it doesn't; a separate "evaluated" entry that
   refuses raw banks just duplicates Open-bank with a worse error
   path.)*
3. **Add v1 baseline as a second run.** Load button picks the v1
   `run.json`. Now two runs loaded; the training-curves view
   becomes a multi-line overlay (one color per run). At a glance:
   training was healthy for both.
4. **Switch to synthetic val metrics.** ROC + confusion matrix +
   calibration diagram, **per run, on synthetic val**. v1.5 retains
   v1's AUROC (~0.999), maybe slightly better calibrated. Good —
   no regression.
5. **Load IAFDB predictions banks for both runs.** File picker
   takes two paths (or a multi-select). The two sibling
   `<run>_iafdb_pred.cbank.h5` banks get loaded.
6. **Open IAFDB output histogram view.** P(fibrotic) histograms for
   both runs, overlaid. **The headline observation:** v1 is
   pegged at 0.999 (peaked at the right edge); v1.5 is also high
   but has a visible left tail down to ~0.85. Some de-saturation.
   Modest but real.
7. **Query for "where do v1 and v1.5 disagree most."** Composable
   filter: `|v1_prob - v1_5_prob| > 0.10`. Result list: ~50 IAFDB
   traces where the two models disagree by at least 10pp.
8. **Sort by v1_prob descending.** Want to see the cases where v1
   was most-confident-fibrotic but v1.5 backed off.
9. **Pick a trace.** **Per-trace detail view, multi-model**:
   - EGM waveform once.
   - Two prediction badges: "v1: 0.998 fibrotic", "v1.5: 0.86
     fibrotic".
   - 11 features computed once (same trace).
   - **(If F-2.11 attention-overlay is implemented)** Side-by-side
     attention overlays: v1's attention is spread across the whole
     trace; v1.5's attention is concentrated on the activation
     peak. **Observation: the activation-peak anchoring is
     visibly working** — v1.5 is paying attention to the *right
     part* of the trace, even though its output is still high.
10. **Mark traces of interest.** Adds the current trace + 4 others
    he just inspected to a "v1.5 attention-success exemplars" trace
    set. Saves the set to disk for later loading.
11. **Bridge to figure prep.** Wants to use these 5 traces as the
    exemplars for F-1.5.7 (matched-trace gallery) or for F-2.11
    (attention overlay) in the Phase 1.5 paper. Notes the trace-set
    file path. Will reload it in figure-prep mode tomorrow.
12. **End session.** Closes the app.

### What this flow needs from the UI

- **Mode switcher** (or distinct workspace) between signal
  exploration / ML diagnostics / figure prep.
- **Run-record loader** (run.json + sibling files).
- **Multi-run loading + parallel display** (analogous to multi-bank
  in Flow A — same shape).
- **Training-curves view** with multi-run overlay.
- **Synthetic-val-metrics view** (ROC, confusion, calibration) with
  per-run faceting.
- **Predictions-bank loading** alongside the underlying source bank
  (predictions reference the original bank's traces; both need to
  be live to assemble the per-trace view).
- **IAFDB output-histogram view** with multi-run overlay.
- **Filter UI that operates over the joined view-model** — both
  feature columns (from egm-features) AND prediction columns (from
  the predictions bank) AND per-model derived columns (like
  `|v1_prob - v1_5_prob|`). This is the ADR-002 unified per-trace
  view-model in action.
- **Per-trace detail view that handles multi-model display.**
- **Attention-overlay rendering** (F-2.11 recipe; only available if
  v0.2 / conditional v0.1 escalation).
- **Trace-set save / load mechanism** — important bridge to Flow C.

---

## Flow C: Paper-figure prep (iterate in GUI, then export)

**Anchor scenario:** Daniel is writing the Phase 1.5 paper. The
analysis is done; results are in. He needs to produce F-1.5.2
(synthetic vs IAFDB feature distributions, 11-panel small-multiples)
as a publication-quality figure file to drop into the LaTeX paper
source.

### Walkthrough

1. **Launch egm-studio + switch to figure-prep mode.**
   The left rail changes from "loaded banks/runs" to "figure
   templates." The center pane becomes a split: **spec editor on
   the left, live preview on the right.**
2. **Pick a figure template.** The template list mirrors the
   recipe catalog from `paper_figure_inventory.md`:
   `feature-distribution-overlay`, `roc-curve-multi-line`,
   `confusion-matrix`, etc. Daniel picks
   `feature-distribution-overlay` for F-1.5.2.
3. **Empty spec editor opens.** The editor shows all the fields the
   recipe expects:
   - Data source(s) — list, one entry per group/line.
   - Feature subset — which columns of the egm-features bundle to
     show (default: all 11).
   - Panel layout — grid shape, panel size.
   - Styling — palette, font, DPI, output size, distance-annotation
     toggle (KS / Wasserstein).
   - Output — file path + format (PDF, PNG, SVG).
4. **Configure data sources.** Adds up to three entries (same
   3-pane cap as the Flow A comparison view — figures with 4+
   overlaid groups become illegible). For F-1.5.2 he uses two:
   - Group A: name "Synthetic v1.5 (Courtemanche)", path
     `~/data/banks/synthegm_v1_5_courtemanche.cbank.h5`.
   - Group B: name "IAFDB", path `~/data/banks/iafdb_v1.cbank.h5`.

   For a related figure later (sim-comparison across cell models),
   he'd add a third group: "Synthetic v1 (Aliev-Panfilov)".
5. **Configure layout.** Defaults to 4x3 grid (since 11 features
   doesn't divide cleanly, one cell will be blank). Daniel keeps
   the default. Per-panel size: 1.5" x 1.2" — at the journal's
   double-column width of 7.2", that gives 4 panels per row at
   1.5" each = 6" with margins, fits.
6. **Live preview renders.** Right pane shows the actual figure as
   it'll export. 11 panels of overlaid KDEs. Daniel sees the
   `sample_entropy` panel has the most-divergent distributions —
   wants to emphasize that.
7. **Iterate on styling:**
   - Picks the project standard palette (color-blind safe; defined
     once project-wide).
   - Bumps font size from 7pt to 9pt — Daniel realizes 7pt is too
     small for the 1.5" panels.
   - Turns on the KS-distance annotation per panel.
   - Adjusts the global title and axis label conventions.
   - Each change triggers a fast preview re-render (<1 sec ideally).
8. **Export.** Click "Export" → file picker, names output
   `F-1-5-2_feature_distributions.pdf`. Format default is
   **vector PDF** (matplotlib `pdf.fonttype = 42`); when LaTeX
   `\includegraphics` includes this PDF, text in the figure
   remains searchable + selectable + scalable in the final
   compiled paper PDF. Fall back to PNG only for raster-domain
   figures (heatmaps with millions of cells, embedded photos).

   Two files produced:
   - The PDF (image goes to `intracardiac-papers/papers/phase_1_5/figures/`).
   - A sibling YAML spec `F-1-5-2_feature_distributions.spec.yaml`
     capturing every configuration field. The YAML goes to the
     **meta repo** (`intracardiac-platform/project/phases/phase_1_5/figure_specs/`
     or equivalent — exact path TBD per the per-phase manifest
     discussion), since the spec is the project-level source of
     truth for the figure. **Saved automatically as a side-effect
     of export.**

   *(Storage strategy:* the image file is regenerable from the
   spec, so it shouldn't be tracked in git (would pollute history
   with binary diffs). Options for the image side:
   - `.gitignore` the image path; treat the YAML as canonical;
     regenerate the PDF on-demand during paper build.
   - Track via Git LFS in the paper repo.
   - Store images in a separate non-git artifact location.

   Decision deferred — flagged in ADR-023 below.*)
9. **Inspect the spec YAML.** Opens the YAML in a text editor to
   verify it captures everything. Could be re-loaded into the
   editor or run headlessly via `egm-studio figure render
   F-1-5-2_feature_distributions.spec.yaml` from the terminal.
10. **Commit the YAML to the meta repo; not the image.** `git add`
    the YAML in `intracardiac-platform/`. The image either stays
    untracked (regenerable from the YAML at paper-build time) or
    goes through whatever storage strategy ADR-023 settles on. The
    YAML is the source of truth; the PDF is build output.
11. **End session.** Closes the app.

### What this flow needs from the UI

- **Mode switcher** (figure-prep is distinct from
  diagnostics / exploration).
- **Figure-template picker** — lists the recipes from the recipe
  catalog (data-driven, not hardcoded).
- **Spec editor** — form-based with optional raw-YAML view for
  power-users. Per-field documentation visible inline (so Daniel
  doesn't have to re-read the recipe spec to remember what a field
  does).
- **Live preview pane** with sub-1-sec re-render on field change.
  For expensive recipes (anything calling egm-features on a large
  bank), might need a "preview with a sample" mode.
- **Styling controls** that respect a project-wide default theme
  but allow per-figure override.
- **Export flow** that produces figure-file + sibling spec YAML in
  lockstep. The YAML *is* the figure's source of truth; the PDF/PNG
  is regenerable from it.
- **Headless CLI companion** (per ADR-005) that takes a spec YAML
  and produces the file. Same plotting code as the GUI; just no
  shell around it.
- **Trace-set load** (bridge from Flow B) — for figures that
  consume a specific list of traces (e.g. F-1.5.7 matched-trace
  gallery), the spec references a trace-set file written in Flow B.

---

## Design questions surfaced

Aggregated across all three flows. These feed ADR-015 (one-GUI-vs-
many), ADR-016 (framework choice), and a few new ADRs we need.

### Strongly suggests one unified GUI with mode-switching

All three flows share the same underlying data layer (banks, runs,
predictions banks via egm-data). Flow A and Flow B share most of the
UI surface (loaders, filter UI, per-trace detail view) with only
mode-specific differences (training curves only in B; bank-summary
default only in A). Flow C is the most different but still
benefits from "the data is already loaded" continuity. **Lean
strongly toward ADR-015 = single GUI with three modes**, not three
separate apps.

### Mode-switcher needs to be cheap

If switching from diagnostics to figure-prep mid-session means
re-loading banks, the mode-switch is too expensive. Loaded data
should be shared across modes; the mode change just swaps the
center-pane workspace.

### Multi-bank / multi-run loading is foundational

Both Flow A (synthetic + IAFDB) and Flow B (v1 + v1.5 runs +
their predictions banks) require multiple data sources loaded
simultaneously. The "current bank" mental model from naive
file-viewer designs doesn't survive contact with these flows. The
data layer needs to be a **registry of loaded data sources**, not
a singleton "currently open bank."

### The unified per-trace view-model (ADR-002) is doing heavy lifting

Flow B step 7 (`|v1_prob - v1_5_prob| > 0.10` filter) requires the
filter UI to compose conditions across features, predictions, AND
derived per-model deltas. This is exactly the ADR-002 unified
view-model in action. Worth re-reading ADR-002 to make sure the
view-model design contemplates multi-model joins.

### Trace-set save/load is the explicit Flow B → Flow C bridge

Flow B step 10-11 saves a trace-set; Flow C step 11 (implied — not
spelled out in F-1.5.2 walkthrough but applies to F-1.5.7 matched-
trace gallery) loads it as a figure-spec input. This is the
"manual trace-set selection" filter source from ADR-002's filter
taxonomy. Format and storage location need an ADR.

### Observation / named-view persistence conflicts with ADR-003

Flow A step 9 wants to save short observations + named filter
views. ADR-003 said "no session persistence in v0.1." But
*partial* persistence — observations and named filter+sort states,
not full workspace — is much cheaper than full session save and
arguably load-bearing for the diagnostic workflows. **Worth a new
ADR** ("partial persistence: observations + named views, NOT full
workspace state") OR an amendment to ADR-003.

### Live preview performance is the hardest perf requirement

Flow C step 7 implies "sub-1-sec preview re-render on each field
change." For figures over large banks, this isn't free —
`extract_all` on 10k traces is ~10s per call. Means we need either:
- Cached / incremental feature DataFrames (compute once, query many
  times)
- A "preview with sample" mode that uses a subsample of the bank
  for live preview, then runs the full data for the export
- Both

This intersects with ADR-016 (framework choice — interactive perf
matters here) and possibly warrants a new ADR on "preview
strategy."

### Figure-template <-> recipe mapping is direct

Flow C step 2 establishes that the figure-template picker UI is
data-driven from the recipe catalog. This is the strongest
signal yet that the figure-spec format (ADR-014) needs to be one
schema per recipe, with the recipe ID as the discriminator. The
editor renders the right form fields based on which recipe is
picked.

### CLI companion is non-negotiable

Flow C step 9-10 makes the CLI companion (ADR-005) load-bearing:
the YAML spec needs to be runnable from the command line to support
the "regenerate the figure six months later" reproducibility claim.
Not optional; not a v0.x add-on. Plan for it from v0.1.

### New ADRs surfaced from the walkthroughs

Reframed and expanded after Daniel's 2026-06-24 review feedback.
Several of these are interconnected and benefit from a focused
deep-dive session before being individually scaffolded as ADRs in
`design.md`. See **"Bundled deep-dive items"** below.

| Proposed ADR | Triggered by | Topic |
|---|---|---|
| ADR-017 | Flow A step 9 + Flow B step 10 | **Unified Save schema** — single file format covering both observations + saved trace sets. Stored in meta repo (`intracardiac-platform/`), not in egm-studio. Save files only reference trace IDs from a saved/versioned bank — they don't embed the trace data themselves. Amends/supersedes ADR-003 "no session persistence." *Needs deep-dive — interlocked with ADR-021, ADR-022.* |
| ADR-018 | Flow A step 2 | **Responsive UI sizing strategy** — per-panel min/max clamps + user-selectable global scale factor + grid-wrap on overflow. Drives shell-level layout decisions across all views. |
| ADR-019 | Flow C step 7 | **Live-preview strategy** (caching / sampling / both). Drives perf design for figure-prep mode + intersects with ADR-016 framework choice. |
| ADR-020 | Flow A step 7 (REFRAMED) | **Per-feature similarity metric for trace pairing.** v0.1 ships per-feature similarity only (nearest by `sample_entropy`, by `peak_to_peak`, etc.). Joint multi-feature similarity (Euclidean? learned embedding? weighted?) is interesting but needs more design thought — deferred to a future ADR after v0.1 usage informs what joint metric (if any) would be useful. |
| ADR-021 (NEW) | Flow A step 9, Flow C step 10, high-level comment #2 | **Per-phase manifest file in meta repo.** A file per project phase (1.5, 2, 3, …) that indexes everything associated with that phase: datasets used, models trained, observations made (refs to trace sets), generated figures (refs to spec YAMLs + output paths), associated papers. Lives at `intracardiac-platform/project/phases/phase_X/manifest.{md,yaml}`. Source of truth for "what produced this paper?" *Needs deep-dive — interlocked with ADR-017, ADR-022.* |
| ADR-022 (NEW) | Flow B + high-level comment #1 | **Model unique-ID + cross-artifact linkage.** Likely requires an egm-contracts schema change to give every trained model a stable identifier that observations, predictions banks, figure specs, and per-phase manifests can reference. *Needs deep-dive — has cross-component coordination cost (contracts → data → classifier → studio).* |
| ADR-023 (NEW) | Flow C step 8 | **Figure image storage strategy.** Image files are regenerable from spec YAMLs — should they be (a) `.gitignore`d and regenerated at paper-build time, (b) tracked via Git LFS in the paper repo, or (c) stored in a non-git artifact location? Affects paper repo size + paper-build CI complexity. |

### Bundled deep-dive items

ADR-017 (Save schema), ADR-021 (per-phase manifest), and ADR-022
(model linkage) are **deeply interconnected** — they share the
same underlying concern of "how do we systematically track what
produced what, across phases and across artifact types." Resolving
them in isolation will produce mismatched designs.

Recommendation: schedule a focused deep-dive session before step
0.5 (open-ADR resolution) that takes all three together. The
output of the session is one coherent design covering:

- What gets a stable ID (models, banks, observations, trace sets,
  figures)?
- Where do the canonical "manifest" files live (per-phase in the
  meta repo)?
- What egm-contracts schema changes are needed to support cross-
  repo references?
- How does egm-studio write into this system without becoming the
  source of truth itself?
- How do downstream consumers (intracardiac-papers, future plugins)
  read from it?

ADR-018 (UI sizing), ADR-019 (preview strategy), ADR-020
(similarity), ADR-023 (image storage) can be resolved
independently as standard ADRs at step 0.5.

### Things that DON'T need an ADR yet

- Specific keybindings, menu structure, command-palette design —
  too granular for Block 0; resolve at implementation time.
- Exact widget choice (table view vs grid vs custom) — depends on
  framework choice (ADR-016) and is implementation-time.
- Color palette specifics — depends on the reference-app study
  (step 0.4) and ADR-012 (theme).

---

## Status

Walkthroughs drafted 2026-06-24; Daniel-review-pass-1 feedback
incorporated same day. Major changes from pass-1 review:

- **3-way comparison** (was 2-way) across Flow A and Flow C.
- **Responsive UI sizing** for the thumbnail-grid (new ADR-018).
- **"Load Evaluated Bank"** unified entry point in Flow B with
  conditional branching (no predictions → warning; predictions
  only → qualitative; predictions + labels → full metrics).
  *(Superseded 2026-07-04 — folded into the single Open-bank path;
  no separate entry, no warning branch. See Flow B step 2.)*
- **Per-feature similarity** in v0.1; joint metric deferred
  (ADR-020 reframed).
- **Observations save to meta repo, not egm-studio** (Flow A step
  9 updated; ADR-017 reframed to "unified Save schema").
- **PDF export with vector text** as default for figures with text
  labels; PNG only for raster-domain figures.
- **Image storage strategy** flagged as new ADR-023 (gitignore
  vs LFS vs separate location).
- **New ADRs surfaced from high-level comments:** ADR-021
  (per-phase manifest), ADR-022 (model unique-ID + linkage).

Three of the surfaced ADRs (017, 021, 022) are interconnected and
flagged for a **bundled deep-dive session** before step 0.5
resolution. The other four (018, 019, 020, 023) can be resolved
independently.

Pending Daniel review-pass-2.

**As-built (2026-07-04):** Flow A shipped in Block 7 and **Flow B shipped in
Block 8** — the ML-diagnostics mode is **Output / Metrics / Training / Explore**
tabs over an evaluated bank (see roadmap Block 8). Deviations from this
walkthrough: the **"Load Evaluated Bank"** unified entry was folded into the
single **Open bank** path (predictions auto-detected; no warning branch — Flow B
step 2, already annotated above); the **3-way** output comparison generalized to
**N sources** (the Output tab); the **pair-comparison** shipped as the shared
`ExploreDetail`'s source-first 3-pane compare (same machinery as Flow A's B7.10),
not a distinct two-column layout; and the **filter-by-ML-outcome** became the
shell's *shared* filter panel driving both flows rather than a Flow-B-specific
control.

**Flow C shipped in Block 9** — a curated per-recipe spec form beside a live
**WYSIWYG** preview (a raster of the real matplotlib recipe, pixel-identical to the
export). Deviations from this walkthrough: **ADR-019 resolved to matplotlib WYSIWYG,
not the `@interact` pyqtgraph sliders** (a pyqtgraph twin would make preview ≠
export); the resolve runs on a **worker thread** so a large bank doesn't freeze the
window (edits debounce; expensive recipes gate behind Refresh); **Render-full writes
to the spec's own `output.path`** (no save dialog; confirms an overwrite); and the
**Phase tree drives it** (Edit / View / Generate / Regenerate figure, the menu
dynamic on whether the image exists). Live-preview perf on very large banks is a
Post-v0.1 follow-up. The Flow C → Flow B trace-set bridge waits on the Block 10 save
flow.

**Block 10 shipped the Save flow (2026-07-05)** — the write path
described in Flow A step 9 + Flow B step 10 + Flow C, as built:

- **Save an observation** (Flow A / Flow B) via **File ▸ Save
  observation**. The dialog captures required prose plus optional
  parent-observation links; egm-studio also snapshots the current **view
  state** — loaded banks, the filter (with its match type), and the
  selection — so **Open observation** later *reloads that view*, not just
  the text. **Edit observation** re-opens the dialog to revise it.
- **Save a figure** (Flow C) via **Save into…**; the figure entry
  records the banks / models / observations it consumes and any
  observations it illustrates.
- **Save target.** With a phase open, both offer **Add to scratch /
  Add to phase**. With no phase open, saves go to **scratch** — a
  per-user, Settings-editable app-data folder that is a full *mini-phase*
  (its own manifest, the same tree + status dots + viewers). **Promote
  to phase** moves authored files into the phase and re-indexes producer
  pointers. This corrects Flow A step 9's "fixed meta-repo path" and the
  earlier scratch location (ADR-017 → **ADR-026**).
- **Auto-add dependencies.** Promoting — or saving / loading — into a
  phase also pulls the artifact's scratch-resident dependencies along
  (e.g. a promoted figure brings its banks), unless the Settings toggle
  is off.
- **Dependency-aware verification.** A well-formed artifact whose
  referenced ids aren't resolvable shows **amber "unresolved"** with a
  tooltip naming the missing id; resolution is cross-scope (a scratch
  item sees scratch + the phase, a phase item sees the phase only).
- **Still open:** manual add / remove of producer entries directly in a
  *phase* tree (**B10g**), and the post-write scan-and-validate hook.
