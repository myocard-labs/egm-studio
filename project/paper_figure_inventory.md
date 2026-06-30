# egm-studio — paper figure inventory

Enumeration of every figure expected across every paper we anticipate
writing in the [intracardiac-platform](https://github.com/myocard-labs/intracardiac-platform)
project. Drives ADR-014 (figure spec format) — the union of distinct
**recipes** below is what the egm-studio figure module has to support.

This is a **living document.** Add entries as new figures get
identified; mark implementation status as recipes ship. The goal is
"better to have an inventoried figure and not need it than to scramble
to retrofit a recipe at paper-writing time."

## Status / scope

- **Papers covered (per Daniel, 2026-06-24):** Phase 1.5, 2, 3, 4, 5,
  7, 8. Phase 6 (TensorRT deployment) is engineering, not a paper.
  Phase 1 results are not their own paper — the lessons-learned story
  rolls into Phase 1.5.
- **Audience:** medical-device industry portfolio / job-search
  audience, not a strict-conventions peer-reviewed journal
  submission. Figures should *look* like medical-device-industry
  paper figures (color-blind safe, clean labels, vector when sensible)
  without being rigidly bound to a specific journal's house style.
- **Implementation priority:** Phase 1.5 (P0) gets full
  implementation in egm-studio v0.1; Phase 2 (P1) in v0.2; Phase
  3-5 (P2) inventoried only; Phase 7-8 (P3) inventoried, deferred.

## Hard constraint: IAFDB is unlabeled

Per [[feedback-iafdb-unlabeled-no-ml-validation]]: IAFDB has no
fibrosis ground truth. **No ML validation metrics — ROC, AUROC,
confusion matrix, calibration, precision, recall, F1, "misclassified
trace" identification — can be computed against IAFDB.** This is a
hard constraint that shapes every paper's figure inventory below.

What IAFDB **can** contribute to a figure:

1. **Feature-distribution comparison data** — egm-features bundle
   values on IAFDB segments. Label-free; works for sim-realism
   measurement.
2. **Qualitative model-output distribution** — observing that the
   model's P(class) histogram on IAFDB is degenerate (Phase 1
   saturation diagnostic) or progressively less degenerate (Phase
   1.5+ intervention checks). Label-free observation; informative
   without ground truth because "the output collapsed to a
   constant" is observable regardless of what the right answer is.
3. **Pretraining data** — Phase 5 CLOCS uses unlabeled IAFDB for
   self-supervised pretraining; no labels needed by definition.

Every "validation metric" figure across every paper below is
computed on the **synthetic held-out validation set**, where the
labels exist by construction. The synthetic side carries the full
ROC / calibration / confusion-matrix burden for the entire project.

## Phase kickoff review policy

This inventory is a living forecast. The early-phase figures (1.5, 2)
are well-anchored because we know the data and math; the later-phase
figures (3, 4, 5, 7, 8) are speculative because the analyses they'd
support don't fully exist yet.

**Before each project phase begins**, we revisit this inventory for
that phase:

1. Daniel spins up on any unfamiliar math / domain concepts for that
   phase's figures (called out per-figure where known — see Phase
   4-5-7 notes below).
2. Daniel gives final go / no-go on each figure for that phase.
3. The figure list is updated based on what we've learned from
   prior phases — figures may be added, removed, retitled, or
   merged.
4. Figures approved at kickoff get pulled into the implementation
   roadmap as concrete tasks.

This protocol is mirrored as a checklist item in
[egm-studio/project/design.md](design.md) under the step plan, and
should be added to each project phase's kickoff prompt in
intracardiac-platform.

## Sim-real comparability prerequisite (cross-phase)

A bunch of figures across multiple phases compare model output or
feature distributions between synthetic and IAFDB data
(F-1.5.2 / F-1.5.6 / F-2.8 / F-3.6 / F-4.6 / F-5.4 / F-7.2 / F-7.4 /
F-8.5 / F-8.6). For those comparisons to be **methodologically
fair** rather than confounded, the synthetic data generation needs
to approximate the IAFDB recording conditions on at least:

- **Electrode spacing and geometry** — Phase 1's flat 5×5 grid does
  not match any catheter actually used in IAFDB. Bipolar voltage is
  sensitive to electrode spacing, so mismatched geometries can
  produce trivially different feature distributions for reasons
  unrelated to substrate.
- **Fibrosis density baseline** — even healthy hearts contain some
  fibrotic tissue. The synthetic "healthy" class should target a
  density distribution consistent with what histology / imaging
  literature reports for healthy adult atria, rather than 0%.
- **Whatever else recording-physics literature recommends.**

**Research item (Phase 1.5 planning):** survey the catheter +
healthy-baseline literature to pick defensible target values. This
research isn't a Block 0 task; it's a Phase 1.5 kickoff item. Flag
when starting Phase 1.5 design.

## Terminology note

Two related but distinct concepts that get conflated and need to be
kept straight in paper text — see
[[terminology-activation-peak-vs-rwave-anchoring]]:

- **R-wave anchoring** — surface-ECG-based amplitude calibration.
  Lives in egm-signal / iafdb-pipeline. **NOT a Phase 1.5
  intervention.**
- **Activation-peak anchoring** — dV/dt-max positioning on the
  bipolar EGM trace itself. Lives in egm-features. **IS a Phase
  1.5 intervention** (task #293).

## Entry format

Each figure entry looks like this:

```markdown
### F-X.Y: Short figure name

- **Description:** one sentence on what it shows.
- **Recipe:** which entry in the cross-paper recipe catalog below.
- **Data sources:** which bank / run record / features it consumes.
- **Priority:** P0 / P1 / P2 / P3.
- **Notes:** any paper-specific framing or quirks.
```

Numbering: **F-{phase}.{idx}** — `F-1.5.3` = third figure in Phase 1.5
paper. Cross-paper references use the same F-X.Y identifier.

## Recipe naming

Recipes are named in `kebab-case`. The same recipe type covers
multiple figures with different data inputs — `confusion-matrix` is
one recipe, instantiated as Phase 1 binary, Phase 2 multiclass,
Phase 3 pattern-type, etc.

---

## Phase 1.5 paper — "Improving synthetic data realism for intracardiac fibrosis classification"

**Story arc — REVISED 2026-06-24 to honor
[[feedback-iafdb-unlabeled-no-ml-validation]]:**

The Phase 1 model achieves excellent in-distribution AUROC (0.999) on
synthetic data but, when applied to real IAFDB data, **collapses to
returning P(fibrotic) ≈ 0.999 on essentially every segment regardless
of input** — the decision function is saturated. This is a
qualitative observation we can make without labels (the model is
constant, so "right" or "wrong" doesn't enter the picture).

Phase 1.5 tests synthetic-side interventions intended to push the
synthetic data distribution closer to the real IAFDB distribution,
on the hypothesis that a model trained on more-realistic synthetic
data will (a) not saturate on real data, and (b) generalize better
in any eventual labeled-real-world evaluation. We can demonstrate
(a) qualitatively on IAFDB; we **cannot** demonstrate the
generalization-to-real claim quantitatively because IAFDB has no
labels.

Hence the paper's evaluation arc is **two-pronged**:

1. **Sim-realism check (the primary deliverable):** Did each
   intervention bring the synthetic feature distribution closer to
   the IAFDB feature distribution? Measured via per-feature
   Wasserstein / KS distance. **Quantitative, label-free.**
2. **Synthetic in-distribution check (the sanity-check
   deliverable):** Did each intervention preserve in-distribution
   classifier performance on the synthetic held-out set? Measured
   via standard ROC / calibration / confusion on synthetic val.
   **Quantitative, on labeled synthetic data only.**
3. **Qualitative IAFDB output check (the supporting deliverable):**
   Did each intervention de-saturate the model's output distribution
   on real IAFDB data? Measured by visualizing the P(fibrotic)
   distribution on IAFDB before / after. **Qualitative — no labels,
   no metric — but informative because "the histogram became less
   pointy at 1.0" is observable without ground truth.**

The Phase 1.5 interventions under test (per project_plan.md "Seeded
tasks from the roadmap audit"): label-threshold tuning,
**activation-peak anchoring** (NOT R-wave anchoring — see
[[terminology-activation-peak-vs-rwave-anchoring]]), additive-noise
augmentation, Courtemanche cell model, additional activation sources
(PointStimulus / S1S2Protocol).

**Implementation priority:** P0. This is the closest paper in time;
its figures get full implementation in egm-studio v0.1.

### F-1.5.1: Phase 1 saturation diagnostic (REFRAMED)

- **Description:** Two-panel histogram of model output P(fibrotic).
  Left panel: synthetic validation set (shows healthy and fibrotic
  classes well-separated — model works in-distribution). Right
  panel: IAFDB segments (shows essentially all output collapsed
  near 1.0 — the saturation observation). **No labels involved on
  the IAFDB side; the observation is "model is constant on real
  data," not "model is wrong on real data."**
- **Recipe:** `prediction-histogram`
- **Data sources:** Phase 1 predictions bank for synthetic val
  + Phase 1 predictions bank for IAFDB.
- **Priority:** P0
- **Status:** Shipped — egm-studio `prediction-histogram` recipe
  (Block 3): panels (per-class synthetic + single-distribution IAFDB)
  + overlay modes, snapshot test, `examples/prediction_histogram_spec.json`.
- **Notes:** The "problem statement" figure. The framing in the
  paper text matters: this is a *decision-function-collapse*
  observation, not a *misclassification rate*. We don't know how
  often the model is wrong on IAFDB because we have no ground
  truth; we know its outputs are degenerate.

### F-1.5.2: Synthetic vs IAFDB feature distributions

- **Description:** 11-panel small-multiples figure — one subplot per
  egm-features bundle feature — overlaying KDEs of the synthetic
  hybrid bank vs IAFDB healthy segments. Visually quantifies where
  the synthetic distribution misaligns with real.
- **Recipe:** `feature-distribution-overlay`
- **Data sources:** synthetic hybrid bank features
  (via `bundle.extract_all`) + IAFDB bank features.
- **Priority:** P0
- **Status:** Shipped — egm-studio `feature-distribution-overlay`
  recipe (Block 3): per-feature shared-x KDE / histogram density
  overlay, per-panel KS / Wasserstein annotation, per-feature axis
  units, `layout.features` curation, framed panels, snapshot test,
  `examples/feature_distribution_overlay_spec.json` (+ `_curated`).
- **Notes:** Critical figure. **Label-free** — uses only signal-
  level egm-features. The per-subplot KS / Wasserstein annotation is
  implemented (KS default). This is the primary sim-realism
  diagnostic across the whole project.

### F-1.5.3: Sim-realism distance reduction per intervention

- **Description:** Bar chart per intervention (label-threshold tune,
  activation-peak anchoring, additive-noise augmentation,
  Courtemanche cell model, additional activation sources, …)
  showing the change in aggregate feature-distribution distance
  (synthetic vs IAFDB) before/after the intervention.
- **Recipe:** `bar-chart-with-deltas`
- **Data sources:** Per-intervention synthetic bank features + IAFDB
  bank features. Distance metric is per-feature Wasserstein
  averaged with weights TBD (open question — see bottom of doc).
- **Priority:** P0
- **Status:** Shipped — egm-studio `bar-chart-with-deltas` recipe (generic)
  + F-1.5.3 distance loader (Block 3): per-group aggregate distance to a named
  IAFDB reference, optional baseline-relative deltas, and `layout.features` to
  restrict which columns define the distance. The aggregate metric defaults to
  KS (unitless — sound to average across the heterogeneous features; raw
  Wasserstein-across-units is not); `styling.metric` overrides. The per-feature
  *weighting* remains the open question below. Validated end to end on
  synthetic-pipeline variant banks (IAFDB-noise on/off, density) ahead of the
  real Phase-1.5 intervention banks.
- **Notes:** **Label-free.** Headline result figure. Want a clear
  win/no-win read at a glance.

### F-1.5.4: Per-intervention synthetic in-distribution ROC (REPLACES old F-1.5.4)

- **Description:** Multi-line ROC curves overlaid, one per
  intervention, on the **synthetic held-out validation set**.
  AUROC annotated.
- **Recipe:** `roc-curve-multi-line`
- **Data sources:** Per-intervention model + synthetic val
  predictions bank.
- **Priority:** P0
- **Status:** Shipped — egm-studio `roc-curve-multi-line` recipe (Block 3):
  overlaid ROC curves (one per labeled synthetic-val predictions bank) with
  per-curve AUROC + a chance diagonal. The ROC/AUROC math is a new
  pure-numpy/scipy `analysis/metrics` module (rank-based AUROC, no sklearn); the
  recipe reuses `PredictionGroup` + the `prediction-histogram` loader (stacked
  registration), adding only an all-groups-labeled guard. `inputs.positive_label`
  selects the positive class. Snapshot test + examples/roc_curve_multi_line_spec.json.
- **Notes:** **Synthetic-only evaluation** (where labels exist by
  construction). The companion-question to F-1.5.3: did the
  interventions hurt in-distribution performance? If F-1.5.3 shows
  realism improved but this shows AUROC dropped, that's an
  interesting trade-off worth discussing.
- **Historical note:** Previously framed as "per-intervention IAFDB
  AUROC." That was wrong — IAFDB has no labels — see
  [[feedback-iafdb-unlabeled-no-ml-validation]].

### F-1.5.5: Per-intervention synthetic in-distribution calibration (REPLACES old F-1.5.5)

- **Description:** Reliability diagrams (predicted-probability bins
  vs observed positive rate) per intervention on **the synthetic
  held-out validation set**. Shows whether each intervention kept
  the model well-calibrated.
- **Recipe:** `calibration-reliability-diagram`
- **Data sources:** Per-intervention model + synthetic val
  predictions bank.
- **Priority:** P0
- **Notes:** **Synthetic-only.** Same reframing as F-1.5.4. The
  Phase 1 result already established that temperature scaling fixed
  in-distribution calibration but didn't help the IAFDB saturation
  — so this figure documents that synthetic calibration stays good
  across interventions, not that anything about the IAFDB problem
  changed.

### F-1.5.6: IAFDB output-distribution de-saturation per intervention (NEW)

- **Description:** Per-intervention overlay of P(fibrotic) histograms
  on IAFDB segments. Each intervention's curve shown as a single
  line; the Phase 1 saturated baseline is the reference. Did any
  intervention spread the IAFDB output distribution away from 1.0?
- **Recipe:** `prediction-histogram` (multi-line / faceted variant)
- **Data sources:** Per-intervention model + IAFDB predictions bank.
- **Priority:** P0
- **Notes:** **Qualitative — no labels involved.** The observation
  "model output is less pointy at 1.0" is meaningful without ground
  truth. Pairs with F-1.5.1 (problem statement) to show whether
  interventions made progress on the *observable* symptom.

### F-1.5.7: Synthetic vs IAFDB matched-trace gallery

- **Description:** N × 2 grid of paired traces — for each row, a
  synthetic trace and its most-similar IAFDB trace (along a TBD
  similarity metric — see egm-studio ADR-002 Open question). Lets
  the reader eyeball realism qualitatively.
- **Recipe:** `trace-pair-gallery`
- **Data sources:** Synthetic bank + IAFDB bank + similarity-index
  computed on egm-features bundle.
- **Priority:** P0 (qualitative; conditional)
- **Notes:** Realism qualitative check. **Label-free** — similarity
  is computed over signal-level features. Probably 8-12 pairs in
  the paper body, more in supplementary.
- **Pairing opportunity:** This figure becomes much more useful
  paired with the attention-overlay figure (F-4.5 / pulled-forward
  variant) on the same matched pairs — "the model sees these as
  similar in feature-space, but which parts of each trace is the
  model actually attending to?" If the attention maps diverge
  between sim and real on otherwise-similar traces, that's a
  pointed diagnostic for what synthetic realism is missing. **If
  the attention recipe lands by Phase 1.5 paper time, treat F-1.5.7
  as a feeder for that combined figure rather than standalone.**
- **Conditional inclusion:** Include in the paper only if the
  by-eye comparison surfaces a hypothesis worth following up. If
  the matched pairs look uninformatively similar OR
  uninformatively different across the board, drop to supplementary
  or skip.

### F-1.5.8: Phase 1 methods schematic (referenced)

- **Description:** Pipeline diagram — Finitewave simulator →
  pseudo-EGM forward calc → 5×5 electrode grid → label policy →
  ClassifierBank.
- **Recipe:** `methods-schematic` (out of egm-studio's scope —
  hand-drawn / Inkscape, possibly TikZ in LaTeX)
- **Data sources:** N/A (hand-drawn).
- **Priority:** N/A — not implemented by egm-studio.
- **Notes:** Could live in a separate "methods" paper-figure pool
  shared across Phase 1.5 / 2 / 3 / 4 / 5 papers.
- **Pre-Phase-1.5 deep-dive (TODO):** Phase 1.5 is the next phase
  after the egm-studio refactor finishes, so methods-diagram
  tooling becomes a near-term need. Before Phase 1.5 design opens,
  do a short survey + recommendation: Inkscape vs TikZ-in-LaTeX vs
  draw.io vs Excalidraw vs matplotlib-based hand-rolled. Trade-offs
  include version-controllability (text-based wins), styling
  precision, ease-of-edit, and whether the diagram language can
  share state with the actual code (e.g. auto-updating electrode-
  position diagrams when the placement strategy changes). **Track
  as Phase 1.5 kickoff prereq.**

### F-1.5.9: Phase 1 model architecture diagram (referenced)

- **Description:** 1D MobileViT architecture block diagram.
- **Recipe:** `methods-schematic` (out of egm-studio's scope)
- **Data sources:** N/A.
- **Priority:** N/A — not implemented by egm-studio.
- **Pre-Phase-1.5 deep-dive (TODO):** Same as F-1.5.8 — architecture
  diagrams have their own conventions (NN architecture diagrams have
  a different visual grammar than pipeline schematics). Worth
  surveying tools specifically used for NN architecture diagrams
  (PlotNeuralNet, Net2Vis, hand-drawn, etc.) before Phase 1.5 design.
  **Track as Phase 1.5 kickoff prereq.**

### F-1.5.10: IAFDB curation summary table

- **Description:** Table — records, patients, segments, channels,
  threshold cutoff, post-curation segment count per record.
- **Recipe:** `summary-table` (LaTeX table; possibly auto-generated
  from a noise_bank_run_record or iafdb_bank_run_record)
- **Data sources:** IAFDB bank run record.
- **Priority:** P0 (low effort — small CSV-to-LaTeX exporter)
- **Notes:** Could be reused across all phase papers that use IAFDB.

### F-1.5.11: Training-curve panel

- **Description:** Loss + selection-metric (AUROC) vs epoch for one
  representative training run from Phase 1.5. Train + val on shared
  axes.
- **Recipe:** `training-curve`
- **Data sources:** `metrics.csv` + `run.json` from a training run.
- **Priority:** P0
- **Notes:** Standard ML-paper figure. Usually goes in supplementary
  but worth including in the main body if the training story is
  interesting (early stopping, instability, etc.).

---

## Phase 2 paper — "Multi-class severity grading"

**Story arc:** Extend Phase 1.5's binary classifier to a multi-class
ordinal severity scale (e.g., healthy / mild / moderate / severe
fibrosis). Per [[project-publishing-timing]], leaning toward this as
the first-publish milestone.

**Evaluation constraint:** Same as Phase 1.5 —
[[feedback-iafdb-unlabeled-no-ml-validation]]. All metric figures
(confusion / ROC / calibration / Sankey) compute against the
**synthetic held-out validation set** where the K-class labels exist
by construction. IAFDB contributes one qualitative figure showing
the model output distribution across K classes (does the multi-class
model split IAFDB output more meaningfully than Phase 1's saturated
binary did?).

**Implementation priority:** P1. Most Phase 1.5 recipes carry over
with K-way instead of 2-way data. New recipes flagged.

### F-2.1: Multi-class confusion matrix (synthetic val)

- **Description:** K × K heatmap of true vs predicted class counts
  on the **synthetic held-out validation set**. K likely = 3 or 4.
- **Recipe:** `confusion-matrix` (generalizes the binary case)
- **Data sources:** Phase 2 model + synthetic val predictions bank.
- **Priority:** P1

### F-2.2: Per-class ROC / PR curves (synthetic val)

- **Description:** K one-vs-rest ROC + PR curves overlaid; per-class
  AUC annotated. Computed on **synthetic val**.
- **Recipe:** `roc-curve-multi-line`
- **Data sources:** Phase 2 model + synthetic val predictions bank.
- **Priority:** P1

### F-2.3: Per-class calibration (synthetic val)

- **Description:** K reliability diagrams, one per class. Computed
  on **synthetic val**.
- **Recipe:** `calibration-reliability-diagram` (instantiated K times)
- **Data sources:** Phase 2 model + synthetic val predictions bank.
- **Priority:** P1

### F-2.4: Per-class prediction histograms (synthetic val)

- **Description:** Predicted-probability distributions per *true*
  class, side by side, on **synthetic val**. Shows whether the
  model is confidently splitting classes or hedging.
- **Recipe:** `prediction-histogram` (faceted by true class)
- **Data sources:** Phase 2 model + synthetic val predictions bank.
- **Priority:** P1

### F-2.5: Class-confusion Sankey diagram (synthetic val)

- **Description:** Sankey diagrams (also called alluvial diagrams)
  visualize FLOW between categories. For K-class confusion, the
  diagram has two vertical bars:
  - **Left bar:** K stacked segments, one per **true** class,
    height proportional to that class's count in the test set.
  - **Right bar:** K stacked segments, one per **predicted**
    class, same height encoding.
  - **Curved bands** connect each left-segment to each
    right-segment, with band thickness proportional to the count
    of test samples with that (true, predicted) pair.

  Textual sketch for K=4:
  ```
   true             predicted
   ─────             ─────
   [healthy ]══════[healthy ]    ← big band: correct
       │\___              │
       │   \___           │
       │       \═══[mild ]│      ← small band: healthy→mild
   [mild    ]══════[mild    ]    ← correct
       │\______       │
       │       ═══[moderate]    ← off-by-one
   [moderate]══════[moderate]
       │
   [severe  ]══════[severe  ]
  ```

- **What it adds over a confusion matrix:** Confusion matrices
  encode the same data but are read as a grid of numbers — fine
  for an ML audience but harder for a clinical reader. Sankey makes
  three things visually pop that the matrix de-emphasizes:
  1. **Class imbalance** is visible at a glance (band heights
     reflect raw counts, not normalized rates).
  2. **Ordinal error structure** — off-by-one errors form short
     bands between adjacent classes, while wildly-wrong errors form
     long bands crossing the diagram. The matrix shows the same
     thing but the visual encoding is "off-diagonal cell darkness,"
     which is less intuitive.
  3. **Where each predicted class came from** — for the predicted
     "mild" column, you immediately see what mix of true classes
     produced it.

  Sankey is *strictly redundant* with the confusion matrix in
  information content; the value is purely in legibility. For an
  audience used to reading confusion matrices, it's a "nice-to-
  have." For a mixed clinical / ML audience, it can be the
  primary view with the confusion matrix in supplementary.

- **Recipe:** `sankey-class-flow`
- **Data sources:** Phase 2 model + synthetic val predictions bank.
- **Priority:** P1
- **Tooling note:** matplotlib doesn't have native Sankey; common
  options are `plotly.graph_objects.Sankey` (interactive HTML,
  exports static via Orca), `pySankey` (matplotlib-based, less
  pretty), or hand-rolled via `matplotlib.patches.Path` (full
  control, more code). Decide at implementation time.
- **Reference:** Sankey diagrams have been used in cardiac ML
  literature for visualizing inter-rater agreement on arrhythmia
  classification — searching "Sankey diagram cardiac classification"
  surfaces examples; we can cite one when paper-writing.

### F-2.6: Per-class example trace galleries (synthetic)

- **Description:** K × N grid — N traces per *true* class, sampled
  from the synthetic ClassifierBank (where class labels exist by
  construction). Shows the morphological character of each
  severity grade.
- **Recipe:** `trace-gallery-grouped`
- **Data sources:** Phase 2 synthetic ClassifierBank + true-label
  column.
- **Priority:** P1

### F-2.7: Feature-space scatter colored by *predicted* class

- **Description:** Take each trace's 11-element egm-features bundle
  vector. Reduce to 2D via a dimensionality-reduction algorithm
  (t-SNE or UMAP — both produce a 2D scatter where points that are
  *similar in the 11-D feature space* land close together in the
  2D plot). Color each point by the model's predicted class.

  Textual sketch:
  ```
  UMAP-y ↑
         │     ●●●●     ▲▲▲▲           ● healthy (pred)
         │   ●●●●●●   ▲▲▲▲▲▲           ▲ mild (pred)
         │  ●●● ● ▲▲▲▲ ▲ ▲▲            ■ moderate (pred)
         │      ●● ▲▲▲                 ★ severe (pred)
         │   ■■■  ★★
         │  ■■■■■   ★★★
         │   ■■■   ★★★★
         └──────────────────→ UMAP-x
  ```

  The story the figure tells: "if the feature space cleanly
  separates the classes the model is asked to distinguish, then the
  feature bundle is informative; if the colors are all jumbled
  together, then either the features aren't discriminative or the
  model is making decisions on something other than these
  features." It's a diagnostic for feature-set adequacy, not a
  performance metric.

  **Three useful instantiations of the same figure:**
  1. Synthetic val with **predicted-class coloring + true-class
     shape** (circles / triangles / squares / stars per true
     class). Lets you see where predictions diverge from truth in
     feature space.
  2. IAFDB with **predicted-class coloring only** (no true labels
     to encode as shape). Lets you see how the model "sees" real
     data in feature space.
  3. Combined synthetic + IAFDB with **data-source as shape and
     predicted class as color**. Shows whether real and synthetic
     populations live in the same feature-space regions or are
     spatially segregated.

- **Recipe:** `embedding-scatter`
- **Data sources:** Phase 2 predictions bank features + precomputed
  2D embedding (UMAP or t-SNE over egm-features bundle vector).
- **Priority:** P1
- **Notes:** One of the few figures that can usefully include
  IAFDB data, because predicted-class coloring is label-free.
- **References / further reading:**
  - **t-SNE:** van der Maaten & Hinton, "Visualizing Data using
    t-SNE," Journal of Machine Learning Research 2008.
  - **UMAP:** McInnes, Healy, & Melville, "UMAP: Uniform Manifold
    Approximation and Projection for Dimension Reduction,"
    arXiv:1802.03426, 2018. UMAP is generally preferred over t-SNE
    in current biomedical-ML practice — faster, preserves more
    global structure.
  - **Example in cardiac signal-processing literature:** ECG
    embedding visualizations are common in deep-learning ECG
    papers; Hannun et al. 2019 (Nature Medicine) used t-SNE on
    learned ECG embeddings to visualize rhythm classes — same
    general pattern as what we'd do here, just with our
    hand-engineered features instead of learned embeddings.
- **Tooling note:** `umap-learn` or `sklearn.manifold.TSNE` for the
  2D reduction (computed once, cached), then standard scatter plot
  for rendering.

### F-2.8: IAFDB K-class output distribution (qualitative)

- **Description:** K stacked or grouped histograms showing the
  fraction of IAFDB segments assigned to each predicted class.
  Qualitative observation: does the K-class model spread IAFDB
  segments across the severity scale, or does it collapse to one
  class (the K-way analogue of Phase 1's binary saturation)?
- **Recipe:** `prediction-histogram` (faceted by predicted class)
- **Data sources:** Phase 2 model + IAFDB predictions bank.
- **Priority:** P1
- **Notes:** **Label-free.** No metric — just "what does the model
  do on real data?" Complements F-1.5.6 (binary version).

### F-2.9: Binary-vs-multiclass comparison table (synthetic val)

- **Description:** Side-by-side table comparing Phase 1.5 binary
  results vs Phase 2 binarized-multiclass results (collapse
  multiclass predictions back to fibrotic-vs-healthy) — does the
  multi-class model retain binary performance? Both columns
  computed on **synthetic val**.
- **Recipe:** `summary-table` (same recipe as F-1.5.10)
- **Data sources:** Phase 1.5 + Phase 2 predictions banks on
  synthetic val.
- **Priority:** P1

### F-2.11: Attention / activation visualization (PROMOTED from Phase 4)

- **Description:** Overlay of attention weights or saliency from the
  Phase 2 multi-class classifier onto a single trace, showing
  which parts of the input the model attended to when assigning
  its class. Works on any trace (synthetic or IAFDB) since
  attention extraction is label-free.

  Per-paper instantiations for the Phase 2 paper:
  1. **Per-class attention exemplars** — for each true class
     (synthetic val), pick the highest-confidence correct
     prediction and show its attention overlay. Builds intuition
     for "what does the model think 'mild fibrosis' looks like in
     a trace?"
  2. **Confusion diagnostic** — pick a misclassified synthetic
     trace (true class A, predicted class B) and show its
     attention overlay. If the attention is on a non-diagnostic
     region, that's a story.
  3. **IAFDB attention sampling** — overlay on a handful of IAFDB
     traces. Where is the model attending on real data? Companion
     observation to F-2.8 (IAFDB K-class output distribution).

- **Recipe:** `trace-with-heatmap-overlay` (new in Phase 2 per this
  promotion)
- **Data sources:** Phase 2 model intermediate activations + one
  trace at a time (selected per the three instantiations above).
- **Priority:** P1
- **Notes:** Promoted to Phase 2 from its original Phase 4 home
  (old F-4.5) because the recipe doesn't require multi-beat input
  — it works on any classifier — and the diagnostic value is
  highest early. See the implementation-effort estimate under
  F-4.5 below (~2-4 days end-to-end).
- **Cross-link:** F-4.5 retains the multi-beat-specific instance of
  the same recipe; that's just a different trace input fed into
  this recipe, no new code.

#### Phase 1.5 escalation clause (conditional)

If the Phase 1.5 paper's primary deliverables — the feature-
distribution comparison F-1.5.2 and the per-intervention distance
reduction F-1.5.3 — don't surface an interesting story, **pull
F-2.11 (attention overlay) further forward to Phase 1.5**. The
narrative "we improved sim realism on N features but the model is
still saturating on real data, and attention overlays show it's
fixating on Y" is a stronger paper than "we improved sim realism
on N features, here's the new histogram."

Trigger condition: at Phase 1.5 paper-writing time, if F-1.5.2 +
F-1.5.3 read as "incremental, hard to draw a strong conclusion
from," reach into the F-2.11 implementation early. This is the
*only* circumstance for the pull-forward; if F-1.5.2 + F-1.5.3
do tell a clear story, F-2.11 stays as a Phase 2 figure.

**Implementation impact of the conditional:** if pulled forward,
egm-studio v0.1 grows from 8 recipes to 9 (the
`trace-with-heatmap-overlay` recipe + the model-introspection
hooks). This is a meaningful but not crazy v0.1 scope addition —
~2-4 extra days of implementation work per the F-4.5 effort
estimate.

### F-2.10: Multi-class label-generation schematic (referenced)

- **Description:** Methods diagram showing how each synthetic
  simulation's **continuous fibrosis-density value** (a real number,
  e.g. 0.27, representing the fraction of myocyte cells replaced
  with fibrotic cells in the substrate) gets mapped to a
  **discrete K-class severity label** for the multi-class
  classifier.

  Textual sketch of what the schematic would show:
  ```
   continuous density           class boundaries           discrete label
   ──────────────────           ───────────────────         ──────────────
   0.0  ←─── healthy
         │
         ├── 0.05  ← class 0 / 1 boundary
   0.20  ← mild
         │
         ├── 0.30  ← class 1 / 2 boundary
   0.45  ← moderate
         │
         ├── 0.60  ← class 2 / 3 boundary
   0.85  ← severe
         │
   1.0   ←─── (all fibrotic)
  ```

  The schematic visually communicates:
  - The continuous nature of the underlying ground truth (we
    *could* train a regression model; instead we discretize).
  - Where the class boundaries are placed (often justified by
    clinical / literature thresholds, often somewhat arbitrary
    binning of a continuum).
  - How edge cases — e.g. density = 0.295, right at a boundary —
    get assigned. Worth showing the policy explicitly because
    boundary choices materially affect the confusion matrix.

  Could also include a histogram of synthetic-set density values
  with bin-boundary vertical lines overlaid, showing the class-size
  imbalance the binning produces.

- **Recipe:** `methods-schematic` (out of egm-studio scope —
  hand-drawn / TikZ / Inkscape)
- **Data sources:** **N/A** in the sense that the *schematic itself*
  is hand-drawn — the diagram is conceptual, not data-driven. The
  *bin boundaries* it visualizes come from Phase 2's
  config / label-policy decisions (which DO need to be made before
  this figure can be drawn).
- **Priority:** N/A — not implemented by egm-studio.
- **Why data sources are N/A:** This is a recurring pattern across
  all `methods-schematic` figures (F-1.5.8, F-1.5.9, F-2.10,
  F-3.7, F-4.7, F-5.7, F-7.7, F-8.7). The figure is *about* the
  pipeline / architecture / labeling scheme, not *generated from*
  any data; it's drawn by hand once and committed alongside the
  paper LaTeX. The "data source" field is N/A because there's no
  data flow for egm-studio to plug into.

---

## Phase 3 paper — "Pattern-type classification of atrial fibrosis"

**Story arc:** Beyond severity, classify *type* of fibrosis pattern
(interstitial / patchy / compact / mixed). Multi-output head over the
Phase 2 backbone.

**Evaluation constraint:** Same as Phase 1.5 / Phase 2 —
[[feedback-iafdb-unlabeled-no-ml-validation]]. All metric figures on
**synthetic val**. IAFDB contributes only a qualitative output-
distribution figure since real data has neither severity nor
pattern-type labels.

**Implementation priority:** P2 — inventoried, implementation deferred
until Phase 3 begins.

**Code reuse from Phase 2 (no new recipes for Phase 3):** Every
figure in this phase reuses a recipe already implemented for Phase 2,
just with different data inputs:

- F-3.1 confusion matrix → `confusion-matrix` (from F-2.1)
- F-3.2 pattern-type substrate viz → `substrate-render-2d` (this
  recipe is new in Phase 3 but it's the only Phase 3 newcomer)
- F-3.3 per-pattern feature distributions →
  `feature-distribution-overlay` (from F-1.5.2)
- F-3.4 joint multi-output accuracy → `bar-chart-with-deltas`
  (from F-1.5.3)
- F-3.5 per-pattern trace galleries → `trace-gallery-grouped`
  (from F-2.6)
- F-3.6 IAFDB output distribution → `prediction-histogram` (from
  F-1.5.1)

**The only net-new implementation for Phase 3 is the
`substrate-render-2d` recipe.** Everything else is "register the
Phase 3 model's outputs as a new data source against the existing
recipes."

### F-3.1: Per-pattern-type confusion matrix (synthetic val)

- **Description:** K × K confusion matrix per pattern type, on
  **synthetic val** (where pattern labels exist by construction).
  Multi-head architecture means one confusion matrix per output
  head.
- **Recipe:** `confusion-matrix`
- **Data sources:** Phase 3 model + synthetic val predictions bank.
- **Priority:** P2

### F-3.2: Pattern-type substrate visualization (synthetic)

- **Description:** For each pattern type, a small synthetic-substrate
  rendering showing what that pattern looks like spatially on the
  2D patch. **Synthetic-only by necessity** — real data has no
  pattern label *and* no spatial substrate map to render.
- **Recipe:** `substrate-render-2d` (new recipe)
- **Data sources:** Phase 3 synthetic dataset config + fibrosis
  array from the synthetic-egm-pipeline result.
- **Priority:** P2

### F-3.3: Per-pattern feature distributions (synthetic)

- **Description:** Same shape as F-1.5.2 but split by pattern type
  rather than by data source. Shows which features discriminate
  patterns. Synthetic-only (where pattern labels exist).
- **Recipe:** `feature-distribution-overlay`
- **Data sources:** Phase 3 synthetic ClassifierBank + pattern-type
  label.
- **Priority:** P2

### F-3.4: Joint multi-output accuracy (synthetic val)

- **Description:** Bar chart per output head (severity, pattern-type,
  …) showing per-head accuracy + joint correctness on **synthetic
  val**.
- **Recipe:** `bar-chart-with-deltas`
- **Data sources:** Phase 3 synthetic val predictions bank.
- **Priority:** P2

### F-3.5: Per-pattern example trace galleries (synthetic)

- **Description:** Pattern-type × N grid sampled from the synthetic
  ClassifierBank.
- **Recipe:** `trace-gallery-grouped`
- **Data sources:** Phase 3 synthetic ClassifierBank.
- **Priority:** P2

### F-3.6: IAFDB output distribution per predicted pattern type (qualitative)

- **Description:** Stacked or grouped histograms showing the
  fraction of IAFDB segments the multi-output model assigned to
  each predicted pattern type. Qualitative — no labels.
- **Recipe:** `prediction-histogram`
- **Data sources:** Phase 3 model + IAFDB predictions bank.
- **Priority:** P2
- **Notes:** **Label-free.** Companion to F-2.8 (severity).

### F-3.7: Multi-output architecture diagram (referenced)

- **Recipe:** `methods-schematic` (out of egm-studio scope)
- **Priority:** N/A.

---

## Phase 4 paper — "Multi-beat sequence classification for atrial fibrosis"

**Story arc:** Move from single-activation classification to multi-beat
sequences. PacingTrain protocol on the synthetic side; longer-T
inputs to the classifier.

**Evaluation constraint:** Same as prior phases —
[[feedback-iafdb-unlabeled-no-ml-validation]]. Metrics on **synthetic
val**. IAFDB has no labels AND no PacingTrain protocol available, so
the only IAFDB role is qualitative output-distribution observation
on whatever multi-beat IAFDB segments can be extracted via the
`extraction.multi_beat` primitive from egm-signal.

**Implementation priority:** P2.

### F-4.1: Multi-beat trace example

- **Description:** Single trace showing N consecutive beats (the
  input format Phase 4 consumes), with beat boundaries marked.
- **Recipe:** `trace-with-annotations` (new recipe — extends the
  single-trace render with overlay markers)
- **Data sources:** Phase 4 synthetic ClassifierBank, one trace.
- **Priority:** P2

### F-4.2: Per-N accuracy curve (synthetic val)

- **Description:** Line plot of accuracy vs number-of-beats-in-input
  on **synthetic val**. How much does the model benefit from more
  beats?
- **Recipe:** `parameter-sweep-curve` (new recipe — generic
  metric-vs-parameter curve)
- **Data sources:** Multiple Phase 4 runs with varying N + synthetic
  val predictions.
- **Priority:** P2

### F-4.3: Sequence vs single-beat comparison (synthetic val)

- **Description:** Bar chart — sequence-model accuracy vs
  single-beat-model accuracy on the same **synthetic val** set.
- **Recipe:** `bar-chart-with-deltas`
- **Data sources:** Phase 4 sequence model + Phase 2 single-beat
  model predictions on synthetic val.
- **Priority:** P2

### F-4.4: Multi-beat confusion matrix (synthetic val)

- **Description:** The Phase 1.5 binary / Phase 2 multiclass-
  severity / Phase 3 pattern-type confusion matrices, **re-computed
  on multi-beat-trained models** evaluated on **synthetic val**.
  Same K-class structure as whichever classifier head Phase 4 is
  building. One confusion matrix per output head (could be all
  three: binary, severity, pattern-type).
- **Recipe:** `confusion-matrix` (no new code — same recipe as
  F-2.1, F-3.1; just a new model + new predictions bank as input)
- **Data sources:** Phase 4 multi-beat model + synthetic val
  predictions bank.
- **Priority:** P2
- **Notes:** Yes, this IS just the previous-phase confusion matrices
  with multi-beat models as the data source. Phase 4's novelty for
  this figure is purely in the model+data input, not the recipe.

### F-4.5: Multi-beat attention visualization (Phase 4 instance)

- **Description:** Same attention-overlay recipe as F-2.11, applied
  to **multi-beat input traces** specifically. Multi-beat input
  has the most structure for attention to fixate on (different
  beats, intra-beat phases), so the Phase 4 paper version is the
  highest-information instance of the recipe.

  Specific framing the Phase 4 paper would emphasize: "the
  multi-beat model attends to beat N rather than beat 1" or "the
  model attends to the transition between beats" — observations
  only possible with multi-beat input.

- **Recipe:** `trace-with-heatmap-overlay` — implemented in
  egm-studio v0.2 as part of F-2.11 (PROMOTED to Phase 2).
  **No new code for Phase 4.**
- **Data sources:** Phase 4 multi-beat model intermediate
  activations + one multi-beat trace.
- **Priority:** P1 (recipe lands with Phase 2; this is just the
  Phase 4 instance / new data input)
- **Notes:** Phase 4 inherits a working recipe from Phase 2. The
  only Phase-4-specific concern is making sure the
  patch-to-sample projection (the "annoying part" of the
  implementation estimate) handles multi-beat-length inputs
  cleanly, which it should as long as MobileViT's patch
  tokenization is length-aware.

#### Implementation effort estimate (lifted from F-2.11 promotion, ~2-4 days)

- *Easy part:* The `trace-with-heatmap-overlay` rendering recipe
  is a single matplotlib chart with a colormapped row/band over
  the trace. ~half a day.
- *Medium part:* PyTorch hooks to extract attention weights from
  MobileViT's transformer blocks during eval. There are multiple
  transformer blocks in the architecture; deciding which layer's
  attention to visualize (and how to combine if showing all) is a
  design decision but not hard. ~1 day.
- *Annoying part:* MobileViT operates on **tokenized patches** of
  the input, not raw samples. The attention weights are per-token,
  not per-sample. Projecting attention back to sample-level
  positions requires bookkeeping on the patch-tokenization
  mapping. Doable; ~1 day.
- *Optional polish:* Compare attention maps for the same input
  trace across different model variants (Phase 1 vs Phase 1.5
  interventions vs Phase 5 CLOCS-pretrained). This is where the
  diagnostic really pays off but needs to be designed deliberately.

### F-4.6: IAFDB multi-beat output distribution (qualitative)

- **Description:** Histogram of model output on multi-beat segments
  extracted from IAFDB via `extraction.multi_beat`. The narrative
  framing: "we know these IAFDB patients aren't all severely
  diseased, so if the model labels a large fraction of their
  segments as fibrotic that's a sanity-check failure for the
  model." It **can't validate** the model (no labels), but an
  obviously-wrong histogram **can invalidate** the model — or, more
  productively, point the next phase's research at a specific
  failure mode.
- **Recipe:** `prediction-histogram`
- **Data sources:** Phase 4 model + IAFDB multi-beat extraction
  results.
- **Priority:** P2
- **Notes:** **Label-free.** Only meaningful if the multi-beat
  extraction successfully produces enough N-consecutive-beat
  segments from IAFDB.
- **Cross-paper prerequisite:** See the global "Sim-real
  comparability prerequisite" section above. For this figure to be
  diagnostic rather than confounded, the synthetic training data's
  electrode spacing needs to approximate what was used in IAFDB —
  otherwise the model's IAFDB output distribution can look weird
  for reasons unrelated to substrate (bipolar voltage is
  spacing-sensitive). This prereq applies to all qualitative
  IAFDB-output figures (F-1.5.6, F-2.8, F-3.6, F-4.6, F-5.4,
  F-7.4, F-8.5) but is most acute for the multi-beat version
  because catheter geometry constraints get amplified across
  multi-beat windows.

### F-4.7: PacingTrain protocol diagram (referenced)

- **Description:** Methods schematic of the `PacingTrain` activation
  protocol used in Phase 4 synthetic-data generation. PacingTrain
  is a Phase-4-specific concept on synthetic-egm-pipeline's
  roadmap; it generates trains of N consecutive pacing pulses with
  fixed intervals, producing the N-consecutive-beat synthetic
  inputs that the Phase 4 multi-beat classifier consumes.
- **Recipe:** `methods-schematic` (out of egm-studio scope)
- **Priority:** N/A.
- **Pre-Phase-4 spin-up (TODO):** Daniel hasn't dug into PacingTrain
  yet — it's Phase 4 territory, three project phases out from now.
  When Phase 4 design opens, schedule a session to (a) spin up on
  what PacingTrain does + how it differs from Phase 1's
  single-stimulation `Edge` protocol, (b) verify this figure is
  the right way to communicate it. **Track as Phase 4 kickoff
  prereq.**

---

## Phase 5 paper — "Self-supervised pretraining on unlabeled IAFDB for synthetic EGM classification"

**Story arc:** CLOCS-style adjacent-segment self-supervised
pretraining on **unlabeled IAFDB** (labels not needed for
self-supervised loss), then fine-tuning on **labeled synthetic**.
The hypothesis: a backbone exposed to real-data signal statistics
during pretraining will produce better-calibrated, less-saturated
outputs when subsequently asked to score real data — even though
all *evaluation* still happens on synthetic val (where labels
exist).

**Evaluation constraint:** Same as prior phases —
[[feedback-iafdb-unlabeled-no-ml-validation]]. Metrics on **synthetic
val**. IAFDB role: (a) unlabeled pretraining data,
(b) qualitative output-distribution comparison
pre-pretrained-vs-from-scratch.

**Phase 5 is the closest the project comes to "validating sim-to-
real performance"** — but even here, the actual claim has to be
narrower than "pretrained model performs better on real data,"
because we cannot measure performance on real data. The claim is
"pretrained model produces a *less degenerate* output distribution
on real data while preserving synthetic in-distribution performance,"
which is observationally meaningful but not a labeled-eval metric.

**Implementation priority:** P2.

### F-5.1: CLOCS pretraining loss curve

- **Recipe:** `training-curve` (same as F-1.5.11)
- **Data sources:** Pretraining run metrics on unlabeled IAFDB.
- **Priority:** P2
- **Notes:** **Label-free.** Self-supervised loss; no labels needed.

### F-5.2: Fine-tuning accuracy with vs without pretraining (synthetic val)

- **Description:** Multi-line learning curves — fine-tuning accuracy
  on **synthetic val** vs epoch, one line for pretrained-init, one
  for from-scratch-init.
- **Recipe:** `training-curve` (multi-series variant)
- **Data sources:** Two fine-tuning runs + synthetic val metrics.
- **Priority:** P2

### F-5.3: Synthetic val ROC + calibration — pretrained vs from-scratch (REFRAMED)

- **Description:** ROC + reliability diagrams on **synthetic val**,
  comparing pretrained-backbone fine-tuned model vs from-scratch
  fine-tuned model. Does the pretrained backbone preserve or hurt
  in-distribution performance?
- **Recipe:** `roc-curve-multi-line` + `calibration-reliability-diagram`
- **Data sources:** Both models + synthetic val predictions banks.
- **Priority:** P2
- **Historical note:** Previously framed as "IAFDB sim-to-real
  eval." Wrong — IAFDB has no labels — see
  [[feedback-iafdb-unlabeled-no-ml-validation]].

### F-5.4: IAFDB output distribution — pretrained vs from-scratch (NEW, qualitative)

- **Description:** Overlaid P(fibrotic) histograms on IAFDB,
  showing the from-scratch baseline (likely saturated, like Phase
  1) vs the pretrained-backbone model. Did pretraining de-saturate
  the decision function on real data? **Qualitative — no labels.**
- **Recipe:** `prediction-histogram`
- **Data sources:** Both models + IAFDB predictions bank.
- **Priority:** P2
- **Notes:** **The headline-observation figure of the Phase 5
  paper.** This is the closest we can get to "did pretraining help
  on real data" without labels.

### F-5.5: Feature-space comparison — pretrained vs from-scratch backbone

- **Description:** Side-by-side t-SNE/UMAP scatters of the
  intermediate-layer embedding, one per backbone init. Coloring
  by predicted class (label-free, works on IAFDB) or by true class
  (synthetic only).
- **Recipe:** `embedding-scatter` (multi-panel variant)
- **Data sources:** Two models + same input data; embeddings
  extracted by hook.
- **Priority:** P2

### F-5.6: Per-patient adjacent-segment data volume

- **Description:** Bar chart per IAFDB patient — how many adjacent-
  segment pairs (the data unit CLOCS pretraining consumes) we got
  out of each patient's recordings. Shows the per-patient data
  volume going into pretraining; long tail or near-empty patients
  affect what CLOCS can learn.
- **Recipe:** `bar-chart-with-deltas` (group-by variant)
- **Data sources:** Pretraining bank record.
- **Priority:** P2
- **Pre-Phase-5 spin-up (TODO):** Daniel hasn't dug into CLOCS
  details yet. "Adjacent segment" is CLOCS-specific jargon —
  contrastive pairs of consecutive heartbeat segments that the
  self-supervised loss treats as positive examples (same patient,
  same approximate cardiac state) vs distant segments as negative
  examples. The actual data unit and how "adjacent" is defined
  needs domain spin-up at Phase 5 kickoff. **Track as Phase 5
  kickoff prereq.**

### F-5.7: CLOCS adjacent-segment loss diagram (referenced)

- **Description:** Methods schematic of the CLOCS contrastive loss
  — adjacent-segment pairs from the same patient are pulled
  together in embedding space; non-adjacent / different-patient
  pairs are pushed apart. The diagram would show the
  encoder → embedding-space geometry, the positive/negative pair
  structure, and the InfoNCE / contrastive loss formulation.
- **Recipe:** `methods-schematic` (out of egm-studio scope)
- **Priority:** N/A.
- **Pre-Phase-5 spin-up (TODO):** Same as F-5.6 — and additionally,
  the contrastive-loss math (InfoNCE, NT-Xent, or whichever variant
  CLOCS uses specifically) needs Daniel's spin-up before this
  figure can be go/no-go'd. **Track as Phase 5 kickoff prereq.**

## Phase 5 — Daniel-go/no-go-required figures

Per the Phase kickoff review policy at the top of this doc:
**Phase 5 has the most unfamiliar math in the project so far.**
Before Phase 5 design opens, Daniel needs to spin up on:

- CLOCS itself (Kiyasseh et al. 2021, ICML) — the self-supervised
  pretraining method this whole phase is built on.
- Contrastive-loss formulations (InfoNCE, NT-Xent) — the math the
  pretraining objective uses.
- "Adjacent segment" semantics — how the data is paired for the
  loss.

After spin-up, revisit F-5.1 through F-5.7 and give explicit
go/no-go on each. Figures may be added (e.g. embedding-space
visualizations of the contrastive structure) or removed (if
something turns out to be misframed).

---

## Phase 7 paper — "3D atrial substrate geometry for synthetic EGM generation"

**Story arc:** Move synthetic side from 2D patch to 3D anatomical
atrial mesh; TorchCor backend replaces Finitewave. Reframed claim
(per [[feedback-iafdb-unlabeled-no-ml-validation]]): rather than
"3D substrate closes the sim-to-real performance gap," the claim
becomes "3D substrate produces synthetic data that is (a) closer
to IAFDB on label-free distributional measures and (b) yields a
classifier that produces a less-degenerate output distribution on
IAFDB while preserving synthetic in-distribution performance."

**Evaluation constraint:** Same as prior phases. All metric figures
on **synthetic val**. IAFDB role: feature-distribution comparison
target (label-free) + qualitative output-distribution observation.

**Implementation priority:** P3 — inventoried, not implemented yet.
The mesh-rendering recipes are the biggest implementation lift and
land last.

### F-7.1: 3D atrial mesh rendering

- **Description:** Rendered 3D view of the atrial mesh substrate
  with fibrosis distribution color-mapped onto the endocardial
  surface.
- **Recipe:** `substrate-render-3d` (new recipe — major
  implementation work)
- **Data sources:** Phase 7 synthetic dataset 3D fibrosis array +
  mesh geometry.
- **Priority:** P3

### F-7.2: 2D vs 3D vs IAFDB feature distribution comparison

- **Description:** 11-panel small-multiples, three lines per panel
  (2D synthetic, 3D synthetic, IAFDB) — does 3D synthetic move
  closer to IAFDB than 2D synthetic was?
- **Recipe:** `feature-distribution-overlay`
- **Data sources:** Phase 1.5 (2D) synthetic bank features + Phase
  7 (3D) synthetic bank features + IAFDB bank features.
- **Priority:** P3
- **Notes:** **Label-free.** Extends F-1.5.2 to three sources.

### F-7.3: 2D-trained vs 3D-trained synthetic in-distribution ROC + calibration (REFRAMED)

- **Description:** ROC + reliability diagrams on **synthetic val**,
  comparing 2D-trained vs 3D-trained models. Did the 3D-trained
  model preserve in-distribution performance?
- **Recipe:** `roc-curve-multi-line` + `calibration-reliability-diagram`
- **Priority:** P3
- **Historical note:** Previously "2D-trained vs 3D-trained sim-to-
  real eval." Wrong — IAFDB has no labels — see
  [[feedback-iafdb-unlabeled-no-ml-validation]].

### F-7.4: IAFDB output distribution — 2D-trained vs 3D-trained (NEW, qualitative)

- **Description:** Overlaid P(fibrotic) histograms on IAFDB, 2D-
  trained vs 3D-trained baselines. Did 3D synthetic data training
  de-saturate the model's output on real data? **Qualitative — no
  labels.**
- **Recipe:** `prediction-histogram`
- **Data sources:** Both models + IAFDB predictions bank.
- **Priority:** P3

### F-7.5: 3D fibrosis-pattern examples

- **Description:** Multiple mesh renderings showing different
  fibrosis-density configurations on the 3D substrate.
- **Recipe:** `substrate-render-3d` (multi-panel variant)
- **Priority:** P3

### F-7.6: Endocardial-surface electrode placement diagram

- **Description:** 3D mesh + overlaid electrode positions from the
  `EndocardialSurface3D` placement strategy.
- **Recipe:** `substrate-render-3d-with-electrodes` (new recipe —
  builds on substrate-render-3d)
- **Priority:** P3

### F-7.7: 2D-to-3D backend swap diagram (referenced)

- **Description:** Methods schematic of the synthetic-egm-pipeline
  architecture change Phase 7 makes. The synthetic-egm-pipeline
  was designed (per its `project/architecture.md`) so that swapping
  simulators is a **contained refactor** — three guardrails were
  put in place specifically to make this possible:
  1. The `Backend` protocol with a single `simulate(spec) -> result`
     method.
  2. The `SimulationSpec` / `SimulationResult` typed objects as the
     interface between any backend and the pipeline.
  3. The strategy Protocols (LabelPolicy, ElectrodePlacement, etc.)
     staying backend-agnostic.

  The diagram visualizes what changes (the AP solver — Finitewave
  2D → TorchCor 3D) and what stays the same (everything that
  consumes a `SimulationResult` and everything that produces a
  `SimulationSpec`).

  Textual sketch:
  ```
   PHASE 1 (2D):                       PHASE 7 (3D):
   ────────────                        ─────────────

   SimulationSpec                      SimulationSpec
       │                                   │
       ▼                                   ▼
   ┌──────────────────┐                ┌──────────────────┐
   │ FinitewaveBackend│                │  TorchCorBackend │     ◄── CHANGED
   │   (2D, FD)       │                │  (3D, FEM/GPU)   │
   └─────────┬────────┘                └─────────┬────────┘
             │                                   │
             ▼                                   ▼
   SimulationResult                    SimulationResult
       │                                   │
       ▼                                   ▼
   pseudo_egm + label_policy           pseudo_egm + label_policy   ◄── UNCHANGED
       │                                   │
       ▼                                   ▼
   ClassifierBank                      ClassifierBank
  ```

  The story the figure tells: "we anticipated this swap during
  Phase 1 design and the architecture absorbs it cleanly." Useful
  for justifying the Phase 1 design choices to a reviewer who
  asks "why didn't you just start with 3D?"

- **Recipe:** `methods-schematic` (out of egm-studio scope —
  hand-drawn / TikZ / Inkscape)
- **Priority:** N/A.

### F-7.8: Compute-cost comparison

- **Description:** Bar chart — Finitewave 2D vs TorchCor 3D
  wall-clock time per simulation, per-trace memory, etc.
- **Recipe:** `bar-chart-with-deltas`
- **Data sources:** Benchmark run records.
- **Priority:** P3

---

## Phase 8 paper — "Realistic catheter geometry in 3D synthetic intracardiac EGM generation"

**Story arc:** With 3D substrate established in Phase 7, model the
catheter geometry explicitly (decapolar / spline / basket) — the
electrodes sit on the catheter, the catheter sits in the substrate,
and the spatial sampling pattern reflects the catheter shape rather
than a flat grid.

**Evaluation constraint:** Same as prior phases. All metric figures
on **synthetic val**. IAFDB role: feature-distribution comparison
target + qualitative output-distribution observation.

**Implementation priority:** P3.

### F-8.1: Catheter geometry rendering

- **Description:** Standalone 3D rendering of one or more catheter
  shapes (decapolar 2-5-2 mm, basket, spline) with electrode
  positions marked.
- **Recipe:** `catheter-geometry-render` (new recipe)
- **Data sources:** Catheter geometry spec from Phase 8 config.
- **Priority:** P3

### F-8.2: Catheter-in-substrate rendering

- **Description:** Combined render — catheter geometry inside the
  3D atrial mesh, showing electrodes contacting the endocardial
  surface.
- **Recipe:** `substrate-render-3d-with-catheter` (new recipe)
- **Data sources:** Phase 8 mesh + catheter geometry.
- **Priority:** P3

### F-8.3: Per-catheter-type synthetic val accuracy

- **Description:** Bar chart of model accuracy per catheter type
  used in synthetic training data, evaluated on **synthetic val**.
- **Recipe:** `bar-chart-with-deltas`
- **Priority:** P3

### F-8.4: Phase 7 vs Phase 8 synthetic val ROC (REFRAMED)

- **Description:** ROC on **synthetic val**, Phase 7 (3D substrate
  only) vs Phase 8 (3D substrate + realistic catheter). Does the
  added catheter realism preserve in-distribution performance?
- **Recipe:** `roc-curve-multi-line`
- **Priority:** P3
- **Historical note:** Previously framed as "sim-to-real
  comparison." Wrong — IAFDB has no labels — see
  [[feedback-iafdb-unlabeled-no-ml-validation]].

### F-8.5: IAFDB output distribution — Phase 7 vs Phase 8 (NEW, qualitative)

- **Description:** Overlaid P(fibrotic) histograms on IAFDB,
  Phase 7 vs Phase 8 baselines. Did catheter realism further
  de-saturate the output on real data? **Qualitative — no labels.**
- **Recipe:** `prediction-histogram`
- **Priority:** P3

### F-8.6: IAFDB vs Phase 7 vs Phase 8 feature distribution comparison

- **Description:** Extension of F-7.2 with a fourth line (Phase 8
  synthetic).
- **Recipe:** `feature-distribution-overlay`
- **Priority:** P3
- **Notes:** **Label-free.**

### F-8.7: Catheter spatial sampling pattern diagram (referenced)

- **Recipe:** `methods-schematic` (out of egm-studio scope)
- **Priority:** N/A.

---

## Cross-paper recipe catalog

The union of distinct recipes across the inventory above. Each row is
a unique recipe; instantiated by multiple figures with different
data inputs. **This is the input to ADR-014 (figure spec format)** —
the figure-spec schema needs to cover the union of metadata fields
across all of these recipes.

| Recipe | Used by | Priority | Implementation notes |
|---|---|---|---|
| `prediction-histogram` | F-1.5.1, F-1.5.6, F-2.4, F-2.8, F-3.6, F-4.6, F-5.4, F-7.4, F-8.5 | P0 | Histogram(s) of predicted probability; supports faceting by class and grouping by data source. **The single most-used recipe across the project** — both labeled (synthetic val per-class histograms) and label-free (qualitative IAFDB output distributions) instantiations live here. |
| `feature-distribution-overlay` | F-1.5.2, F-3.3, F-7.2, F-8.6 | P0 | N-panel small-multiples; per-panel a KDE or histogram with one line per group; KS/Wasserstein annotation optional. **Label-free** — primary sim-realism diagnostic. |
| `bar-chart-with-deltas` | F-1.5.3, F-3.4, F-5.6, F-7.8, F-8.3 | P0 | Grouped bar chart; error bars; baseline-relative deltas optional. |
| `roc-curve-multi-line` | F-1.5.4, F-2.2, F-5.3, F-7.3, F-8.4 | P0 | Multi-line ROC + AUC annotation; PR-curve sibling. **All instances on synthetic val** (IAFDB has no labels). |
| `calibration-reliability-diagram` | F-1.5.5, F-2.3, F-5.3, F-7.3 | P0 | Bin-wise predicted vs observed; per-class faceting. **All instances on synthetic val.** |
| `trace-pair-gallery` | F-1.5.7 | P0 | N × 2 grid of paired traces; per-row metadata annotation. Label-free (uses similarity). |
| `summary-table` | F-1.5.10, F-2.9 | P0 | Tabular data → LaTeX / markdown / PNG export. |
| `training-curve` | F-1.5.11, F-5.1, F-5.2 | P0 | Loss + metric vs epoch; train/val multi-series; multi-run overlay variant. |
| `confusion-matrix` | F-2.1, F-3.1, F-4.4 | P1 | K × K heatmap; K configurable; row / column normalization variants. **All instances on synthetic val.** |
| `sankey-class-flow` | F-2.5 | P1 | Sankey / alluvial; class flow from true → predicted. **Synthetic val only** (requires true labels). |
| `trace-gallery-grouped` | F-2.6, F-3.5 | P1 | Group × N grid of traces; group labels per row. Synthetic data only (needs class labels). |
| `embedding-scatter` | F-2.7, F-5.5 | P1 | 2D scatter of high-dim embedding; coloring by *predicted* class is label-free (works on IAFDB); coloring by true class requires synthetic. UMAP / t-SNE computed externally. |
| `parameter-sweep-curve` | F-4.2 | P2 | Generic metric-vs-parameter line plot; error bars over seeds. |
| `trace-with-annotations` | F-4.1 | P2 | Single trace with overlay markers (beat boundaries, activation times). |
| `trace-with-heatmap-overlay` | F-2.11, F-4.5 | P1 | Single trace with intensity overlay (attention / saliency). Label-free. Promoted from P2 to P1 (2026-06-24) per F-2.11 — Phase 2 paper consumes the diagnostic; Phase 4 reuses with multi-beat input. Conditional P0 escalation to Phase 1.5 if F-1.5.2 + F-1.5.3 underwhelm. |
| `substrate-render-2d` | F-3.2 | P2 | 2D imshow of fibrosis array; color-mapped. Synthetic-only (real data has no spatial substrate map). |
| `substrate-render-3d` | F-7.1, F-7.5 | P3 | 3D mesh rendering; surface color-mapped. **Major implementation lift** — needs a 3D rendering library decision (vtk? pyvista? plotly 3D? trimesh?). |
| `substrate-render-3d-with-electrodes` | F-7.6 | P3 | Extends `substrate-render-3d` with electrode position overlays. |
| `substrate-render-3d-with-catheter` | F-8.2 | P3 | Extends further to embed catheter geometry. |
| `catheter-geometry-render` | F-8.1 | P3 | Standalone catheter render; smaller lift than substrate-render-3d but new code. |
| `methods-schematic` | F-*.{schematic figures} | N/A | **Explicitly OUT of egm-studio scope.** Hand-drawn in Inkscape / TikZ / draw.io. The figure module does not generate these. |

### Recipe-count summary

- **8 recipes at P0** — Phase 1.5 paper's full needs.
- **5 additional recipes at P1** — adds confusion-matrix, sankey,
  trace-gallery-grouped, embedding-scatter, **trace-with-heatmap-overlay**
  (last one promoted from P2 → P1 on 2026-06-24 for the Phase 2 paper).
- **3 additional recipes at P2** — Phase 3-5 expansions
  (substrate-render-2d, parameter-sweep-curve, trace-with-annotations).
- **4 additional recipes at P3** — Phase 7-8 3D rendering work.

**Total: 20 distinct recipes** across the project (plus the
out-of-scope `methods-schematic` bucket).

### Observation: `prediction-histogram` is the single highest-leverage recipe

After the 2026-06-24 IAFDB-unlabeled cascade, `prediction-histogram`
is instantiated by **9 figures across all 7 papers** — the most of
any recipe. The reason is that this single recipe covers both
labeled-eval cases (per-class histograms on synthetic val) and
qualitative IAFDB observations (P(class) distribution on
unlabeled real data). Getting this recipe right early pays off
across every paper.

---

## Per-phase implementation novelty

A view from the implementation perspective: for each phase, what
recipes are **new** vs **reused-from-an-earlier-phase**. Answers
"how much net implementation work does Phase X actually require?"
and "where might we be tempted to duplicate work?"

| Phase | New recipes | Reused recipes | Net new implementation |
|---|---|---|---|
| **1.5** | `prediction-histogram`, `feature-distribution-overlay`, `bar-chart-with-deltas`, `roc-curve-multi-line`, `calibration-reliability-diagram`, `trace-pair-gallery`, `summary-table`, `training-curve` | (none — Phase 1.5 is the first paper) | **8 recipes** |
| **2** | `confusion-matrix`, `sankey-class-flow`, `trace-gallery-grouped`, `embedding-scatter`, `trace-with-heatmap-overlay` | Everything else from 1.5 | **5 recipes** (heatmap-overlay promoted from Phase 4 per F-2.11) |
| **3** | `substrate-render-2d` | Everything else from 1.5 + 2 | **1 recipe** |
| **4** | `trace-with-annotations`, `parameter-sweep-curve` | Everything else from 1.5 + 2 (incl. heatmap-overlay) | **2 recipes** (heatmap-overlay moved to Phase 2) |
| **5** | (none — all CLOCS figures reuse existing recipes with new data sources) | All of 1.5 + 2 | **0 recipes** |
| **7** | `substrate-render-3d`, `substrate-render-3d-with-electrodes` | All earlier | **2 recipes (substantial 3D-rendering lift)** |
| **8** | `substrate-render-3d-with-catheter`, `catheter-geometry-render` | All earlier | **2 recipes (extends Phase 7 3D stack)** |

**Total: 20 distinct recipes across the project.**

**Observations:**

- **Phase 3 and Phase 5 are mostly "wire up the new model's outputs
  as a data source against existing recipes" work.** Phase 3 adds
  one recipe (`substrate-render-2d`); Phase 5 adds zero. The risk of
  duplicate implementation is real if these phases are designed
  in isolation from the recipe catalog — call this out at Phase 3
  and Phase 5 kickoff.
- **Phase 7 + Phase 8 share a 3D-rendering substack.** Together
  they add 4 recipes all built on top of `substrate-render-3d`.
  Picking the 3D library (vtk / pyvista / plotly-3D / trimesh) is
  a single decision that affects all four. Worth a dedicated ADR at
  Phase 7 kickoff.
- **Phase 4 is the implementation-heaviest middle phase** — 3 new
  recipes (annotations, heatmap overlay, parameter sweep). The
  attention-overlay recipe (`trace-with-heatmap-overlay`) is the
  one with the most diagnostic value across all phases; per F-4.5
  notes above, recommend pulling it forward to P1 (egm-studio v0.2
  alongside Phase 2) so Phase 1.5 / 2 / 3 figures can use it too.
- **Phase 1.5 carries the 8-recipe foundation.** Half the project's
  total recipe surface gets implemented for the first paper. This
  is intentional — Phase 1.5 has the most figure-design risk
  because we're proving out what works at all.

## Implementation priority summary

| egm-studio release | Recipes added | Papers unblocked |
|---|---|---|
| **v0.1** | 8 P0 recipes | Phase 1.5 |
| **v0.2** | +5 P1 recipes (cumulative 13) | + Phase 2 (+ multi-beat instance of attention overlay for Phase 4) |
| **v0.3+** | +3 P2 recipes (cumulative 16) | + Phase 3, 4, 5 |
| **v0.4+** | +4 P3 recipes (cumulative 20) | + Phase 7, 8 |

**Conditional escalation:** If F-1.5.2 + F-1.5.3 underwhelm by
Phase 1.5 paper-writing time, the `trace-with-heatmap-overlay`
recipe escalates from v0.2 (P1) to v0.1 (P0), making v0.1 ship 9
recipes instead of 8. See F-2.11 "Phase 1.5 escalation clause"
above.

The figure-spec schema (ADR-014) should be designed to **support all
20 recipes from day one** even though only 8 are implemented in v0.1.
The schema is the long-lived interface; adding a recipe later
shouldn't require a schema migration if we anticipate the field surface
upfront.

---

## Open figure-inventory questions

- **Methods-schematic policy.** Are paper methods diagrams genuinely
  out of egm-studio's scope (hand-drawn, version-controlled in
  `intracardiac-papers/papers/<slug>/figures/`), or do we want some
  egm-studio support for the data-driven half (e.g. an electrode-
  position diagram that auto-updates if the placement strategy
  changes)? Current default: out of scope.
- **Supplementary figures.** Most papers have ~10x more figures in
  supplementary than in the main body. Do we inventory those too?
  Current default: no — supplementary uses the same recipes as the
  main body, just with more instantiations. As long as the recipe
  surface is complete, supplementary needs nothing new.
- **Per-paper visual style.** All papers use the same color palette /
  typography, or do we leave room for paper-specific styling?
  Current default: shared style with optional per-paper overrides
  through the figure spec.
- **F-1.5.3 distance metric weighting.** "Aggregate feature-
  distribution distance" needs a weighting per feature. Equal weights
  is a starting point; learned-importance weights would be more
  defensible but require Phase 1.5 model introspection work.
- **Per-feature significance testing for `feature-distribution-overlay`.**
  When the figure shows synthetic vs IAFDB across 11 feature
  subplots, we want a per-subplot indicator of whether the
  distributions differ "significantly." KS test? Wasserstein
  distance? Two-sample CDF bootstrap? Decide before Phase 1.5 paper
  writing.
- **What constitutes "less degenerate" output distribution.** The
  qualitative IAFDB output-distribution figures
  (F-1.5.6 / F-2.8 / F-3.6 / F-4.6 / F-5.4 / F-7.4 / F-8.5) rely
  on the observation "less pointy at 1.0." A more rigorous summary
  statistic (entropy of the histogram? variance? mode distance from
  endpoint?) would let us put numbers on the trend. Worth defining a
  single quantitative summary per paper that pairs with the
  qualitative histogram.
- **F-1.5.7 / F-3.5 / F-5.6 cross-paper trace-gallery sample
  selection.** When a paper has multiple trace galleries, the same
  underlying trace set could plausibly appear in more than one (e.g.
  the worst-saturated IAFDB segments from F-1.5.1 might be the
  natural sample for a matched-pair gallery in F-1.5.7). Do we
  cross-link trace IDs to keep the narrative consistent, or treat
  each gallery as independently sampled?
