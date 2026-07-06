# egm-studio — design log

Running log of design decisions made during **Block 0 (design phase)**.
Each entry is an **Architecture Decision Record (ADR)** capturing
context, options considered, decision, rationale, and consequences.
The reasoning trail matters as much as the conclusions — six months
from now, "why did we do it this way?" should be answerable from this
doc.

> **As-shipped reconciliation (egm-contracts v0.5.0, 2026-06-27).** The
> cross-artifact-linkage schemas shipped with surface changes from what some
> ADRs below describe. Read this doc with these deltas in mind (full list in
> `intracardiac-platform/project/cross_artifact_linkage_design.md` →
> Amendments). The high-level design — Phase GUI, Save-Observation flow,
> figure-render CLI, manifest curation — is **unaffected**; only surface
> details changed:
> - **On-disk format is JSON, not YAML** (`manifest.json`,
>   `observations/<id>.json`, `figure_specs/<id>.json`; the render CLI reads a
>   `.json` spec). Anywhere this doc says "YAML", read "JSON".
> - **Observation prose field is `description`** (not `body`); observations and
>   figure specs carry **no `phase` field** (the manifest records phase
>   membership).
> - **`figure_spec`** requires a `description` and dropped `inventory_ref`.
> - **Manifest banks are stored as `egm_banks` + `noise_banks`** (prediction
>   banks fold into `egm_banks`, distinguished by filling `model` +
>   `source_bank`). The right-rail "10 groups" tree is a *display* grouping the
>   GUI derives from the id prefix — unchanged by the storage shape.
> - **`FigureId` pattern is `^fig_[A-Za-z0-9_\-]+$`** — slug-based, date
>   optional, so both `fig_F-1-5-2` and `fig_F-1-5-2_2026-06-25` validate
>   (ADR-022 and the linkage design differ on whether to date figure ids; the
>   schema accepts either — pick one convention at implementation time).

Block 0 closed 2026-06-25; the as-is design synthesis lives at
`project/architecture.md` and the Block 1+ implementation plan at
`project/roadmap.md`. This file remains as the **historical
record** — the full reasoning trail for every decision. New ADRs
after Block 0 (covering later v0.2.0+ design changes) get appended
here, with `project/architecture.md` updated in lock-step per its
living-document commitment.

## Conventions

Each ADR follows the same shape:

```markdown
## ADR-NNN: Short decision name

**Date:** YYYY-MM-DD
**Status:** Accepted | Tentative | Deferred | Open | Superseded by ADR-X

### Context
What's the question? What constraints are at play?

### Options considered
1. Option A — pros / cons
2. Option B — pros / cons

### Decision
What we chose.

### Rationale
Why.

### Consequences
What this implies for the rest of the design.
```

Status definitions:

- **Accepted** — locked. Implementations proceed against it.
- **Tentative** — agreed for now; expect to revisit after first contact with code.
- **Deferred** — flagged as something we need to decide, not yet decided.
- **Open** — actively under discussion in Block 0.
- **Superseded** — replaced by a later ADR; left in place for history.

## Step plan (live source of truth)

The enumerated steps for the egm-studio build, kept in sync as work
progresses. **This is the canonical "where are we?" reference** —
supersedes any drift in a long chat. After each step closes:

1. Mark the step `[x]` complete with a date.
2. **Re-review the remaining plan** for changes — has anything we
   learned in the closing step invalidated a later step? Add /
   remove / re-order as needed.
3. Move on to the next pending step.

When a new Block is started, append its enumerated steps below the
prior block.

### Block 0 — design phase

- [x] **0.1 Scaffold egm-studio + start design log** (~½ day)
  - python-template scaffold personalized to `myocard-egm-studio`;
    `project/design.md` started with the initial 16 ADRs from the
    Q6-16 design discussion.
  - **Closed 2026-06-24.**
- [x] **0.2 Paper-figure inventory** (~1 day; reviewed and approved
  2026-06-24)
  - Enumerated every figure across every expected paper (Phase 1.5,
    2, 3, 4, 5, 7, 8 per Daniel — Phase 6 is engineering, no paper;
    Phase 1 lessons-learned roll into Phase 1.5). Grouped by recipe;
    derived the figure module's requirements + the figure-spec
    schema fields. **Drives ADR-014.**
  - **Output:** `project/paper_figure_inventory.md` — ~37 figures
    across 7 papers; 20 distinct recipes; implementation priority
    P0 (Phase 1.5) → P1 (Phase 2 + Phase 4 attention reuse) → P2
    (Phase 3-5) → P3 (Phase 7-8).
  - **Major mid-pass correction:** First draft included impossible
    figures (ROC / AUROC / confusion / calibration on IAFDB).
    Cascaded fixes across all 7 papers per
    [[feedback-iafdb-unlabeled-no-ml-validation]]: all eval metrics
    now on synthetic val; IAFDB role limited to feature
    distributions (label-free) + qualitative model-output
    distributions. Terminology fix: activation-peak anchoring (NOT
    R-wave anchoring) per
    [[terminology-activation-peak-vs-rwave-anchoring]]. Project-wide
    cleanup of stale "IAFDB ML eval" references queued as task
    #308.
  - **Late decision:** Pulled attention-overlay recipe forward from
    Phase 4 (P2) to Phase 2 (P1) as new F-2.11. Phase 1.5
    conditional-escalation clause built in (escalate to P0 / v0.1
    if F-1.5.2 + F-1.5.3 underwhelm).
  - **Cross-cutting research items surfaced:** Phase 1.5 kickoff
    prereqs include (a) electrode-spacing + healthy-heart fibrosis-
    baseline calibration research, (b) methods-diagram tooling
    survey (Inkscape / TikZ / draw.io / PlotNeuralNet for
    F-1.5.8 + F-1.5.9). Phase 4 + 5 prereqs include domain spin-up
    on PacingTrain (Phase 4) and CLOCS contrastive-loss math
    (Phase 5).
  - **Closed 2026-06-24.**
- [x] **0.3 User-flow walkthroughs** (~1 day; draft + Daniel
  review-pass-1 + cross-artifact deep-dive all incorporated by
  2026-06-25). **Closed 2026-06-25.**
  - Three workflows in prose at click level: signal-exploration
    (Flow A), ML-diagnostics (Flow B — anchored on "compare v1 vs
    v1.5 IAFDB output distributions" per Daniel's scoping; the
    original "debug v1.5 IAFDB FPs" anchor was reframed since
    IAFDB has no FPs), paper-figure-prep (Flow C — GUI-iterate-
    then-export primary mode). Shakes out the real UI shape better
    than top-down design. **Drives ADR-015 + ADR-016 + 7 surfaced
    ADRs (017-023).**
  - **Output:** `project/user_flow_walkthroughs.md` — ~600 lines
    covering the three flows + 7 proposed ADRs.
  - **Pass-1 review feedback incorporated:** 3-way comparison
    (not 2-way), responsive UI sizing, "Load Evaluated Bank"
    unified entry, per-feature similarity (joint deferred),
    observations save to meta repo (not egm-studio), PDF-with-
    vector-text as default export. ADR-017 reframed (unified Save
    schema, not partial session persistence). Two new ADRs
    surfaced: ADR-021 (per-phase manifest in meta repo) and
    ADR-022 (model unique-ID + cross-artifact linkage).
  - **Bundled deep-dive flagged:** ADR-017 + ADR-021 + ADR-022
    are interconnected and need a focused joint design session
    before step 0.5 resolution. ADR-018, 019, 020, 023 are
    independent.
- [x] **0.4 Reference-app study** (~1-2 hours; ran a bit longer with
  the deep-dive synthesis + vendor research) **Closed 2026-06-25.**
  - Three reference targets: RStudio (fixed pane grid), JupyterLab
    (free-form dock + `@interact` widget pattern), intracardiac
    mapping systems composite (CARTO 3 / EnSite X / Rhythmia HDx —
    multi-trace EGM panel pattern). DaVinci Resolve considered but
    dropped — the clinical-system convergence covers the multi-trace
    density question more directly without being out-of-domain.
  - **Output:** `project/reference_apps.md` covering all three targets,
    per-app what-we-borrow / what-we-don't matrices, the egm-studio
    synthesis, and the implications-for-ADRs table.
  - **Resolved ADRs:** ADR-012 (Deferred → Accepted: dark default +
    light toggle), ADR-019 (Deferred → Tentative: `@interact` pattern
    transfers; concrete v0.1 use cases listed).
  - **New ADRs:** ADR-024 (composable trace widget: TraceWidget +
    GraphicsLayoutWidget, default N=1, scales to N=8/20/64+ for later
    phases without rewrite); ADR-025 (layout model: resizable columns
    + collapsible side panels, neither RStudio-grid nor JupyterLab-
    dock).
  - **Deferred to later (tracked):** ADR-019 perf details to
    implementation time; Phase 8+ live playback (task #311).
- [x] **0.5 Tech-stack + open-ADR resolution** (batch-approved
  2026-06-25; ran shorter than the ~½ day estimate since the
  reference-app study + user-flow walkthroughs had pre-loaded the
  inputs). **Closed 2026-06-25.**
  - **Locked four ADRs:**
    - ADR-013 testing — Tentative → Accepted (3-layer: unit +
      pytest-qt + pytest-mpl; tooling now concrete given ADR-016).
    - ADR-014 figure spec — Open → Accepted (JSON Schema in
      egm-contracts + Pydantic codegen + YAML on disk; matches
      [[feedback-schemas-json-schema-first]]; stable IDs per ADR-022).
    - ADR-015 one-vs-many GUI — Open → Accepted (one unified
      `egm-studio` interactive shell + separate `egm-studio-render`
      headless CLI; shared figures module).
    - ADR-016 GUI framework — Open → Accepted (PySide6 + pyqtgraph
      + matplotlib; alignment with ADRs 007, 012, 019, 023, 024,
      025 documented).
  - **Similarity-metric follow-up — no new ADR needed.** 0.3 did NOT
    surface a clear joint-metric preference; ADR-020 (per-feature
    in v0.1, joint deferred) stands as captured.
- [x] **0.6 Synthesize `architecture.md` + `roadmap.md`** (~1 day;
  batch-approved 2026-06-25 after one revision pass on roadmap +
  module-map sync). **Closed 2026-06-25.**
  - `project/architecture.md` — ~330 lines synthesizing the 25
    ADRs: 8 core invariants, module map with the 3-layer
    rendering split (`analysis/` + `charts/` + `figures/`), cross-
    repo dependency table, layout/data-flow/persistence sections,
    test strategy, forward-looking items. Living-document
    commitment captured at the top.
  - `project/roadmap.md` — 13-block implementation plan (1
    retroactive + 12 to do). Velocity target: ~10-13 days focused,
    ~1-1.5 weeks elapsed. Critical-path: egm-contracts v0.5.0
    ships before Block 2 starts.
  - **Daniel's review-pass-1 feedback incorporated:** original
    Block 2 (figures) split into 2 (analysis + render-skeleton; then
    charts/matplotlib + recipes); original Block 3 (Qt shell + Flow
    A) split into 4 (shell; TraceWidget + charts/pyqtgraph; Phase
    tree read-only; Flow A); original Block 7 (ship) split into 3
    (design-phase doc updates; user docs; ship/tag). User docs given
    dedicated time per Daniel's "main way other people will be able
    to access my data" framing. Time estimates recalibrated downward
    to match actual project velocity.
  - **Architecture amendment surfaced + applied during synthesis:**
    the original module map showed a single `figures/` package; the
    Block 2 deep-dive surfaced that we need a 3-layer split
    (`analysis/` + `charts/` with dual backends + `figures/` as a
    thin dispatch) so no chart logic is duplicated between the
    headless renderer and the GUI's interactive displays. Applied to
    `architecture.md` to prevent day-1 drift.
- [x] **0.7 Block 0 close-out review** (~½ hour, **closed 2026-06-25**).
  - Walked `design.md` end-to-end; cross-checked the four sibling
    docs (`paper_figure_inventory.md`, `user_flow_walkthroughs.md`,
    `reference_apps.md`, `architecture.md`, `roadmap.md`) for ADR
    cross-reference consistency.
  - **No decision drift found.** All 25 ADRs have consistent
    statuses across all docs; cross-references to "Open" / "Deferred"
    ADRs in the sibling docs are all historical (describing the
    resolution path, not current state).
  - **Four wording fixes applied** — text written DURING Block 0
    that referred to "upcoming" Block 0 work (migration to
    architecture.md, Block 1+ enumeration in step 0.6, etc.) was
    past-tensed / updated to reference the now-existing
    `architecture.md` + `roadmap.md`. No decisions changed.
  - **Block 0 greenlit as complete.** Implementation start gated on
    `myocard-egm-contracts` v0.5.0 (the cross-artifact linkage
    shipping wave).

### Block 1+ — implementation

Enumerated in `project/roadmap.md` (14 blocks total: 1 retroactive
done + 13 to do; ~11-15 days focused effort / ~1.5-2 weeks elapsed).
Critical-path dependency: `myocard-egm-contracts` v0.5.0 ships
before Block 2 starts.

## Status summary (live)

| ADR | Title | Status |
|---|---|---|
| 1 | All data I/O via egm-data + egm-contracts | Accepted |
| 2 | Filter-by-feature-delta as the primary view pattern | Accepted |
| 3 | No session persistence in v0.1 | Accepted |
| 4 | Two modes: interactive exploration + headless figure generation | Accepted |
| 5 | Headless figure-generation reusable from notebooks / CI / scripts | Accepted |
| 6 | No plugin architecture in v0.1 | Accepted |
| 7 | Distribution: `pip install` + entry point | Accepted |
| 8 | No in-app help / onboarding in v0.1 | Accepted |
| 9 | Documentation: markdown in repo; MkDocs Material as upgrade path | Accepted |
| 10 | Design log lives at `project/design.md`, ADR-style | Accepted |
| 11 | Display: filter-and-sort-first, not paginated browsing | Accepted |
| 12 | Theme / styling system | Accepted (dark default, light toggle; via reference-app study) |
| 13 | Testing strategy | Accepted (locked at 0.5) |
| 14 | Figure spec format — JSON Schema in egm-contracts + YAML on disk | Accepted (at 0.5) |
| 15 | One unified GUI shell + separate headless CLI | Accepted (at 0.5) |
| 16 | GUI framework — PySide6 + pyqtgraph + matplotlib | Accepted (at 0.5) |
| 17 | Unified Save schema (observations + embedded trace sets) in meta repo | Accepted (via cross-artifact deep-dive) |
| 18 | Responsive UI sizing strategy | Tentative |
| 19 | Live-preview strategy | Tentative (via reference-app study; `@interact` pattern transfers) |
| 20 | Per-feature similarity in v0.1; joint metric deferred | Accepted |
| 21 | Per-phase manifest in meta repo | Accepted (via cross-artifact deep-dive) |
| 22 | Model unique-ID + cross-artifact linkage | Accepted (via cross-artifact deep-dive) |
| 23 | Image storage: gitignored + regenerated; banks via GitHub Releases | Accepted |
| 24 | Composable trace widget (one TraceWidget per trace, stacked) | Accepted (via reference-app study) |
| 25 | Layout model — resizable columns + collapsible side panels | Accepted (via reference-app study) |

---

## ADR-001: All data I/O via egm-data + egm-contracts

**Date:** 2026-06-24
**Status:** Accepted

### Context

egm-studio reads HDF5 banks, JSON training records, CSV metrics,
predictions banks, and model-metadata sidecars. Each of these has a
schema in egm-contracts and a reader in egm-data.

The question: does egm-studio reach into HDF5 / JSON directly, or
exclusively through egm-data?

### Options considered

1. **Direct I/O** — egm-studio reads its own files. Pros: zero
   coupling to egm-data; can ship without it. Cons: schemas
   re-implemented; egm-studio becomes a third place where the format
   knowledge lives, drifting against the other two.
2. **Exclusively via egm-data** — egm-studio never opens an HDF5 or
   JSON file directly. Pros: schemas and readers live in one place;
   any change to a format is a coordinated upgrade across the stack.
   Cons: egm-studio gets a runtime dep on egm-data (and transitively
   egm-contracts).

### Decision

**Exclusively via egm-data + egm-contracts.** If egm-studio needs to
read a file type that doesn't already have a schema / reader, we add
it to egm-contracts + egm-data first, then consume it from
egm-studio. Same convention as egm-classifier and the producer repos.

### Rationale

Keeps the data-interface boundary between projects clean. Prevents
egm-studio from accumulating dataset-specific I/O code that
duplicates the other two repos. Reinforces
[[feedback-use-contracts-at-boundaries]].

### Consequences

- egm-studio gets `myocard-egm-data` (and transitively
  `myocard-egm-contracts`) as runtime deps.
- New file types require coordinated PRs across contracts → data →
  studio. The cascade order is the same as for the other repos.
- The loader layer in egm-studio is thin and uniform — just typed
  models in, view-models out.

---

## ADR-002: Filter-by-feature-delta as the primary view pattern

**Date:** 2026-06-24
**Status:** Accepted

### Context

A loaded bank can have thousands of traces. The naive approach is a
scrollable list / grid. But scrolling through 10,000 traces looking
for "the interesting ones" is the wrong workflow — interesting cases
are interesting *with respect to some feature*, not in an absolute
sense.

### Options considered

1. **Paginated / scrollable browse** — show all traces, paginate.
   User scrolls to find what they want. Pros: simple. Cons: doesn't
   match the actual analysis workflow.
2. **Filter-and-sort-first** — the primary view is "traces matching
   this query, ordered by this metric." Including pair-comparison
   ("show me the 10 trace pairs with the largest Δsample_entropy
   between fibrotic and healthy labels"). Pros: matches how analysis
   actually happens; surfaces informative examples directly. Cons:
   requires a query / filter UI from day one.

### Decision

**Filter-and-sort-first.** egm-studio is an analysis-driven tool, not
a file browser. The primary view in every mode is "traces or
trace-pairs matching this query, ordered by this metric."

### Filter source taxonomy

The "query" axis is deliberately broad — not just egm-features
metrics. The shell must support filters from any of these source
categories, and let the user *compose* them (boolean conjunction over
multiple categories at once):

1. **Trace-level features** — every column of the egm-features bundle
   DataFrame (peak_to_peak, sample_entropy, dominant_frequency, etc.).
   Filter ("sample_entropy > 1.5") and sort ("descending by Δfeature
   across a pair axis").
2. **ML diagnostic outcomes** — when a predictions bank is loaded:
   predicted probability, predicted class, correctness bucket (TP /
   FP / TN / FN), per-trace loss, calibration residual. "Show me FNs
   sorted by predicted probability descending" is the canonical
   example.
3. **Bank / record metadata** — anything from the ClassifierBank or
   sibling bank record: label, patient_id, sim_id, channel position,
   electrode_pair_id, recording session, source (synthetic vs IAFDB
   vs hybrid). Categorical filters + group-by.
4. **Similarity-based selection** — "show me the trace most similar
   to *this* one" along a TBD similarity metric (see Open question
   below). Two specific patterns matter:
   - **Nearest-correct pair:** misclassified trace + most-similar
     correctly-classified counterpart of the *opposite* label.
     Diagnostic for "what made this one fail?"
   - **Within-class neighborhood:** an outlier trace + its k-nearest
     in-class peers. Diagnostic for "is this trace genuinely weird
     or just on the tail of the distribution?"
5. **Manual trace-set selection** — saved sets of trace IDs from a
   previous analysis ("these 12 traces from the v1.5 FN inspection
   that we want to revisit"). Reload + re-filter against the rest.
6. **Composition over the above** — booleans / set ops ("FN AND
   sample_entropy > 2.0 AND patient_id != excluded_list").

### Rationale

This is the most important architectural decision in the design. It
shapes the data model (a unified per-trace view-model with columns
from features + outcomes + metadata + similarity scores), the UI
model (query → list → comparison is the default workflow), and the
consumer flow (extends naturally to ML diagnostics, similarity
inspections, and paper-figure trace galleries).

The breadth matters: a filter UI that *only* understood feature
metrics would be a regression vs the analyses Daniel already runs
manually. Misclassification-driven and similarity-driven filters are
load-bearing for ML diagnostics.

### Consequences

- The "indexed view" of a bank isn't just the features DataFrame —
  it's a **unified per-trace view-model** that joins (a) features
  from egm-features, (b) ML outcomes from a loaded predictions bank
  (when present), (c) bank metadata, (d) any similarity columns
  computed on demand, (e) any user-defined trace-set memberships. The
  filter UI queries against this composite table.
- **Pair-comparison is a first-class UI pattern** — across both
  delta-driven pairing (Δfeature) and similarity-driven pairing
  (nearest neighbor of opposite label). The shell needs both.
- A query / filter UI needs to be designed early — expressive enough
  to compose categorical + numeric + similarity filters, simple
  enough to use without writing SQL.
- **Open question — similarity metric.** "Most similar" requires a
  distance function over traces. Options: Euclidean / cosine over
  features, DTW on raw traces, learned embedding from an
  intermediate model layer. To be decided in a future ADR; tracked in
  the Open questions section below.
- For the paper-figure mode, the same query syntax drives "select
  the trace gallery for this figure," giving figure-spec
  reproducibility (ADR-014 once locked).

---

## ADR-003: No session persistence in v0.1

**Date:** 2026-06-24
**Status:** Accepted

### Context

"I loaded these 3 banks, configured this comparison, opened these 2
traces — let me save the workspace and come back tomorrow" is a
common UX feature in mature scientific tools. But it's also expensive
to build: serialization format, restore semantics, schema migration,
versioning of saved sessions, etc.

### Options considered

1. **Full session persistence** — every workspace can be saved /
   restored. Pros: best UX for long-running analyses. Cons: large
   amount of code for v0.1; needs versioning + migration story.
2. **No session persistence** — every session starts cold. Pros:
   minimal code; no state-mgmt headaches. Cons: re-set-up cost when
   resuming work.
3. **Hybrid** — persist only "last-opened files" + window geometry,
   nothing else. Pros: cheap. Cons: still doesn't restore the
   in-flight analysis.

### Decision

**No session persistence in v0.1.** Single-session analyses only.
Revisit if it becomes a real pain.

### Rationale

The data + analyses we're working with aren't complex enough yet to
need cross-session continuity. Loading a bank + applying a filter
takes seconds; not worth the infrastructure cost upfront.

### Consequences

- The shell stays simpler; no state-serialization layer.
- If the figure-spec mode (ADR-004) needs persistence — and it does,
  since paper figures must be reproducible — that's a separate,
  scoped persistence mechanism (YAML files), not a generic session
  manager.

---

## ADR-004: Two modes — interactive exploration + headless figure generation

**Date:** 2026-06-24
**Status:** Accepted

### Context

The user modes break into two fundamentally different shapes:

- **Interactive** (signal exploration, ML diagnostics): user-driven,
  click-and-explore, immediate feedback.
- **Headless / batch** (paper figure generation): config-driven,
  reproducible, exportable without GUI interaction.

The temptation is to do interactive-only with an "export" button. But
paper figures need to be regenerable from a config six months later,
which means the production path must be scriptable.

### Options considered

1. **Interactive-only with export button** — single mode; pros:
   simpler. Cons: no reproducibility story for figures.
2. **Separate apps** — GUI for interactive, CLI for figures. Pros:
   clean separation. Cons: duplicated data-loading layer.
3. **Shared core, two frontends** — same data + plotting code;
   GUI mode wraps it interactively, CLI mode runs it headlessly from a
   config file. Pros: reproducibility built in; figures the user
   tweaks in the GUI export as YAML configs that the CLI can re-run.
   Cons: more code upfront.

### Decision

**Shared core, two frontends.** The interactive GUI is an editor for
figure configs; the CLI / Python entry point is the headless executor.
Same plotting code in both paths.

### Rationale

Paper-figure reproducibility is non-negotiable: when reviewer #2 asks
for a tweak six months later, we need to apply it without remembering
which knob we turned. "Save the YAML, re-run the CLI" is the only
sustainable answer. Daniel explicitly accepted the additional upfront
code cost for this.

### Consequences

- Architecture is bottom-up: the plotting / data-prep code is the
  shared substrate; the GUI and CLI are thin frontends on top.
- The figure-spec format (ADR-014) needs to be locked early since it's
  the interface between the GUI editor and the headless executor.
- Tests are easier — the headless path is pure-function and unit-testable
  without GUI machinery.

---

## ADR-005: Headless figure-generation reusable from notebooks / CI / scripts

**Date:** 2026-06-24
**Status:** Accepted

### Context

Even with a GUI editor, the figure-generation code should be
importable from a Jupyter notebook or a CI job — same way matplotlib
works.

### Decision

**Yes — headless API is first-class.** The figure-generation entry
point is a Python function callable from anywhere: GUI button
handlers, CLI, notebooks, CI jobs.

### Rationale

This is implied by ADR-004 but worth recording separately because it
constrains module structure: the figure code can't depend on Qt at
import time, only at GUI-shell wiring time. Lets us swap GUI
frameworks later without rewriting the figure code (Daniel called
this out as a benefit).

### Consequences

- Module boundary: `myocard_egm_studio.figures` (or similar) has zero
  Qt imports. `myocard_egm_studio.gui.figures_view` is the Qt shell
  on top.
- CI for the figures module is straightforward unit tests + snapshot
  tests on rendered output.
- Notebook ergonomics: `from myocard_egm_studio.figures import
  render_figure; render_figure(spec)` should just work.

---

## ADR-006: No plugin architecture in v0.1

**Date:** 2026-06-24
**Status:** Accepted

### Context

"Plugin systems" — letting external code register new view types,
new feature extractors, new chart kinds without touching core — are
heavy infrastructure (entry-point discovery, isolation, versioning).

### Decision

**No plugin system in v0.1.** Structure the code so plugin extension
*could* be added later without major rewrites — but only if doing so
is free.

### Rationale

The only consumer of egm-studio is Daniel for the foreseeable future.
Adding a new view means editing core code; that's fine. Plugin
systems are worth building only when external contributors actually
want to extend.

### Consequences

- View / chart types are registered in core via plain Python imports,
  not entry-point discovery.
- If we ever want plugin support, the natural shape is to make the
  view registry consume `importlib.metadata.entry_points` — but
  that's a v0.x+ refactor, not v0.1 work.

---

## ADR-007: Distribution — pip install + entry point

**Date:** 2026-06-24
**Status:** Accepted

### Context

How do users (Daniel, eventually collaborators) install and run
egm-studio?

### Options considered

1. **pip install + console-script entry point** — `pip install
   myocard-egm-studio && egm-studio`. Standard.
2. **PyInstaller bundle** — ship a standalone binary. Heavy CI; not
   needed yet.
3. **Web-deployed** — Streamlit / Dash style. Bigger architectural
   commitment; out of scope.
4. **Docker container** — heavy for desktop usage.

### Decision

**pip install + console-script entry point.** Web-deploy and binary
bundling out of scope for v0.1.

### Rationale

Lightest distribution that matches the desktop-app shape. Structure
the code so a future move to web (if needed) doesn't require a
ground-up rewrite (ADR-005 helps here — the figure code being
GUI-framework-independent makes a future swap easier).

### Consequences

- `pyproject.toml` declares an `egm-studio` console script.
- No bundler / installer CI work.
- Future web frontend (if ever) reuses the figures module and the
  data-access layer; only the shell would be new.

---

## ADR-008: No in-app help / onboarding in v0.1

**Date:** 2026-06-24
**Status:** Accepted

### Context

Polished apps often have embedded help (tooltips, tours, an in-app
manual). It's nice but expensive.

### Decision

**No in-app help in v0.1.** Documentation lives in `docs/usage.md`
and the README. If egm-studio ever becomes a long-term professionally
deployed application, revisit then.

### Rationale

Daniel is the only user for the foreseeable future. He doesn't need a
tour. External documentation is sufficient.

### Consequences

- No tooltip-management code, no in-app help system.
- `docs/usage.md` does double duty as the user manual.

---

## ADR-009: Documentation — markdown in repo; MkDocs Material as upgrade path

**Date:** 2026-06-24
**Status:** Accepted

### Context

GUI documentation tends to be image-heavy (screenshots), which strains
plain-markdown rendering. The question is whether to commit to
something fancier upfront (LaTeX / PDF, Sphinx, MkDocs).

### Options considered

1. **Plain markdown** — pros: zero toolchain, GitHub renders it.
   Cons: image-heavy docs feel cramped.
2. **MkDocs Material** — pros: looks great; consumes plain markdown
   unchanged; web-deployable. Cons: extra toolchain + CI step.
3. **PDF (LaTeX or pandoc)** — pros: pixel-perfect, printable.
   Cons: not searchable on the web; painful to update; no good story
   for inline code samples.

### Decision

**Markdown in repo for now. MkDocs Material is the upgrade path when
content justifies it.** PDF reserved for paper-submission figures
(which is a separate workflow — egm-studio *exports* PDFs, the docs
themselves don't need to be PDFs).

### Rationale

The upgrade from plain markdown to MkDocs is trivial — just add a
`mkdocs.yml` and a theme; the markdown files are unchanged. So
markdown-first is the no-regret choice. LaTeX / PDF for user manuals
is the wrong format (not searchable, hard to update).

### Consequences

- v0.1 docs live in `docs/*.md`.
- When content grows: add MkDocs build + GitHub Pages deploy in CI.
  Same markdown files, just a new frontend.

---

## ADR-010: Design log lives at `project/design.md`, ADR-style

**Date:** 2026-06-24
**Status:** Accepted

### Context

We need a place to record design decisions made during Block 0 + any
later architectural changes.

### Decision

**`egm-studio/project/design.md`**, ADR-style entries. Existing
project/ convention (`architecture.md` = as-is design,
`roadmap.md` = future work). `design.md` is the running decision log
and the post-Block-0 historical record; `architecture.md` is the
synthesized as-is reference. Both stay live: new architectural
decisions append here as new ADRs, with `architecture.md` updated in
lock-step per its living-document commitment.

### Rationale

ADR format (context → options → decision → rationale → consequences)
captures the reasoning trail, not just the outcome. Six months from
now, "why did we pick PySide6 over Streamlit?" needs to be answerable
without an archeology dig.

### Consequences

- All Block 0 decisions land here.
- `architecture.md` becomes the post-Block-0 synthesis (cleaner,
  shorter, "current state" doc).
- Later v0.2.0+ architectural changes get new ADRs appended here.

---

## ADR-011: Display — filter-and-sort-first, not paginated browsing

**Date:** 2026-06-24
**Status:** Accepted

### Context

Closely related to ADR-002, but distinct: ADR-002 is about the
*conceptual model* of "analysis-driven not browse-driven." This is
about the *concrete UI rendering* — what happens when you load a
1000-trace bank.

### Decision

**Show only the result of the current query / filter, not the raw
bank.** Default queries should be sensible (e.g. "all traces" with
a default sort) so the user isn't staring at an empty pane, but the
mental model is "you express what you want to see; the GUI shows
that subset."

### Rationale

Same as ADR-002. Reinforces it at the rendering layer.

### Consequences

- No "infinite scroll" widget rendering 10,000 trace cards.
- The result-set view is bounded (e.g. top-N matching, configurable).
- Performance scales with result-set size, not bank size.
- Sorts and filter operations are O(N) over the features DataFrame —
  fast even for large banks since we're not rendering everything.

---

## ADR-012: Theme / styling system

**Date:** 2026-06-24 (initial); **Updated:** 2026-06-25 (reference-app study)
**Status:** Accepted (dark default, light toggle)

### Context

Light vs dark mode, color palette, typography scale, custom widget
styling. The reference-app study (`project/reference_apps.md`)
confirmed that both RStudio and JupyterLab treat dark/light as
first-class, with toggle UI as a normal expectation. Clinical mapping
systems lean dark (cath-lab lighting); egm-studio's context is
researcher-in-an-office, where the dark/light choice is more personal
than functional.

### Decision

- **Default theme:** dark.
- **Light theme:** ships as a user-toggleable alternative; not a
  second-class citizen, but not the default.
- **Stylesheet implementation:** Qt's QSS, given the PySide6 lean in
  ADR-016. Final implementation locked when ADR-016 lands.

### Rationale

Daniel's stated preference is dark; the reference apps treat
dark-as-default as a perfectly normal choice. Shipping a light toggle
keeps the option open for any future user or context (presentations,
high-ambient-light rooms) without forcing the default.

### Open follow-ups (not blocking v0.1)

- **Paper-figure color palette** — separate from the GUI theme. Paper
  figures should match a journal-friendly color-blind-safe palette
  (Nature / Science / PLOS conventions); the GUI theme governs the
  shell, not the rendered figures. Decide as part of the figure-spec
  ADR (ADR-014) and the per-figure recipes.
- **Typography scale** — pick a small set of font sizes (e.g. 11/13/16
  px). Resolve at implementation time.

### Consequences

- v0.1 ships with three themes wired to a `View > Theme` menu — dark
  (default), light, and vibrant (see the Block 4 amendment below).
- User-preference system needs a `theme` key; realised in Block 4 via
  `gui/preferences.py` (Qt `QSettings`), which persists the selection.
- Per-trace plot styling (colors, line weights) lives separately from
  the GUI theme and is selected per-figure for the headless figure
  path.

### Amendment (2026-07-01, Block 4)

Shipped **three** themes, not two: dark (default) + light + **vibrant** — a
programmer-editor palette (Tokyo-Night-ish: bright green headings, purple
selection, cyan accents) Daniel requested as a personal preference. Adding a
theme is cheap under the implementation: each theme is a `Palette` of colour +
typography tokens fed to one shared QSS template (`gui/theme/`), so the three
can't drift structurally.

The "user-preference theme key" consequence is now realised — `gui/preferences.py`
persists the selection via Qt `QSettings`, so the shell reopens in the last-chosen
theme (first launch still defaults to dark). This is the seed of ADR-017's broader
save-state.

---

## ADR-013: Testing strategy

**Date:** 2026-06-24 (initial); **Locked:** 2026-06-25 (Block 0.5)
**Status:** Accepted

### Context

GUI tests are notoriously brittle. We need a strategy that gives
confidence without an order-of-magnitude maintenance cost. With the
framework choice locked at ADR-016 (PySide6 + pyqtgraph + matplotlib),
the concrete tooling for each layer is now known.

### Decision

Three-layer test strategy:

1. **Heavy unit tests** on data-prep, figure recipes, query / filter
   logic, save-state serialization. Pure functions, no GUI machinery
   needed. Default `pytest` + plain `assert`. Covers the bulk of the
   surface area.
2. **Light integration tests** with **`pytest-qt`** for the GUI
   shell. Tests cover "data flows through the views correctly" — e.g.
   loading a bank populates the trace list, applying a filter narrows
   the result set, saving an observation writes to the phase
   manifest. Tests do NOT cover "this button is at pixel (x, y)";
   that's brittle by design.
3. **Snapshot tests** for exported figures via **`pytest-mpl`**.
   Catches regressions in the rendered output. Snapshots regenerate
   on intentional changes; CI fails on unintentional ones.

**Avoid:** brittle click-here-see-that tests; pixel-coordinate
assertions; tests that depend on display resolution or font
availability beyond what pytest-mpl handles.

### Rationale

The layered approach localizes brittleness: most of the code is in
the unit-testable layer; the integration layer is small and
contract-y; the snapshot layer catches a specific class of
regression that's otherwise easy to miss.

The headless figure path (ADR-005) makes the snapshot layer
straightforward because figure code doesn't depend on Qt at import
time.

### Consequences

- CI runs unit + snapshot tests with no display dependency.
- Integration tests need a virtual display (`xvfb-run` in CI), which
  is standard infrastructure on Linux runners.
- Test fixtures for synthetic banks live in `tests/conftest.py`,
  shared across all three layers.
- Snapshot baselines are committed to the repo under
  `tests/snapshots/`; regeneration is an explicit pytest flag
  (`--mpl-generate-path=tests/snapshots`).

---

## ADR-014: Figure spec format / per-figure metadata

**Date:** 2026-06-24 (initial); **Locked:** 2026-06-25 (Block 0.5)
**Status:** Accepted

### Context

ADR-004 + ADR-005 commit to figures being driven by reusable specs.
The paper-figure inventory (Block 0.2) enumerated ~37 figures across
20 distinct recipes. Cross-artifact linkage (ADR-022) requires every
figure spec to have a stable ID. The format and schema home are the
remaining questions.

### Options considered

1. **Pure YAML, schema in egm-studio** — declarative, human-
   readable, version-controllable. Schema definition lives in
   egm-studio. Cons: drifts from the egm-contracts convention used
   for all other cross-component schemas (observation,
   phase_manifest, etc.).
2. **JSON Schema in egm-contracts + Pydantic codegen + YAML on disk**
   — schema lives in egm-contracts (Draft 2020-12 JSON Schema,
   single source of truth), Pydantic models codegen'd from it,
   serialized as YAML on disk. Matches
   [[feedback-schemas-json-schema-first]] and the pattern already
   used for `observation`, `phase_manifest`, `epoch_record`, etc.
3. **Python module + function call** — most flexible, but loses
   declarative reproducibility and breaks the
   "regenerable from spec six months later" requirement.

### Decision

**Option 2 — JSON Schema in egm-contracts + Pydantic codegen.**

> **As shipped (egm-contracts v0.5.0), this decision was refined:** serialize
> as **JSON** (not YAML); the **spec file lives in the meta repo** at
> `intracardiac-platform/project/phases/phase_X/figure_specs/<fig-id>.json`
> (decision 2026-06-27 — only the rendered image goes to the paper repo); and
> `recipe` is a **free-form string**, not an enum — the recipe vocabulary is
> owned + validated by egm-studio, not hardcoded into the contract (per
> [[feedback-library-defaults]]).

- Schema lives at `egm-contracts/schemas/figure_spec.schema.json`
  (Draft 2020-12).
- Pydantic model codegen'd to `myocard_egm_contracts.figure_spec`.
- Spec files (JSON) live in the meta repo at
  `intracardiac-platform/project/phases/phase_X/figure_specs/<fig-id>.json`;
  the rendered image is gitignored build output written to the paper repo.
- Stable ID per ADR-022 / the linkage design — the `FigureId` pattern is
  `^fig_[A-Za-z0-9_\-]+$` (slug-based; date optional).
- `recipe` is a free-form string; egm-studio owns the recipe vocabulary
  (the 20 recipes from the paper-figure inventory live in egm-studio, not in
  the contract schema).

### Rationale

- **Convention consistency.** Every other cross-component schema in
  myocard-labs goes through egm-contracts; figure_spec follows the
  same path. Per [[feedback-schemas-json-schema-first]]: never edit
  generated code, never re-define a schema in multiple places.
- **Reproducibility built in.** YAML on disk + spec-with-stable-ID
  means "reviewer #2's tweak six months later" is "edit the YAML,
  re-run `egm-studio-render`."
- **Validation for free.** Pydantic validation at load time catches
  malformed specs before they reach the renderer.
- **Cross-artifact linkage works.** Phase manifest entries can
  reference figure spec IDs; the validate_manifest script can check
  spec presence + schema validity as part of Check A
  (orphan detection).

### Consequences

- egm-contracts v0.5.0 (already planned for the cross-artifact
  linkage shipping wave) gains `figure_spec.schema.json` +
  generated Pydantic model.
- egm-studio depends on egm-contracts (already true via ADR-001).
- Headless renderer (ADR-005) is `render(spec: FigureSpec) -> Path`,
  callable from CLI, notebook, or GUI button handler.
- Recipe enum becomes the authoritative list of "figures egm-studio
  knows how to draw"; the paper-figure inventory + recipe enum stay
  in lock-step (additive evolution).
- Implementation order: schema lands in egm-contracts first; then
  the recipe-router lookup table + per-recipe functions land in
  egm-studio.

---

## ADR-015: One unified GUI shell + separate headless CLI

**Date:** 2026-06-24 (initial); **Locked:** 2026-06-25 (Block 0.5)
**Status:** Accepted

### Context

Should the three user modes (signal exploration / ML diagnostics /
paper figures) live in one app or many? The user-flow walkthroughs
(Block 0.3) made the answer clearer than the initial framing
suggested.

### Options considered

1. **Three separate apps** (one per mode) — pros: each app stays
   focused. Cons: forces re-loading the same banks across apps;
   breaks cross-flow rhythms ("notice anomaly in signal exploration
   → check ML predictions on it → save as observation → flag for
   paper figure" is one rhythm, not three); triplicates the data-
   layer, query-UI, and trace-display machinery.
2. **One unified interactive GUI** (with mode/view switching) **+
   one headless figure CLI** — pros: shared data layer, shared
   query UI, shared trace widgets, shared Phase artifact tree;
   cross-flow workflows work natively; the headless path stays as a
   separate console script for batch/CI/reproducibility use. Cons:
   slightly larger single binary; mode-switching UX needs design.

### Decision

**Option 2 — one unified GUI shell + separate headless CLI.**

Concretely:

- **`egm-studio`** (interactive GUI, console script) — single
  process. Three top-level "modes" cover the user-flow
  walkthroughs: signal-exploration, ML-diagnostics, paper-figure-
  prep. Modes share the data layer, query/filter UI, trace widgets,
  Save-Observation flow, and Phase artifact tree (right sidebar
  per ADR-025).
- **`egm-studio-render <spec.yaml>`** (headless CLI, separate
  console script) — reads a figure_spec YAML (ADR-014), executes
  the recipe, writes PNG/PDF/SVG. Also importable as
  `from myocard_egm_studio.figures import render` for notebook /
  CI use (per ADR-005).

Both ship from the same `myocard-egm-studio` package; both are
declared as console scripts in `pyproject.toml`.

### Rationale

The user-flow walkthroughs (Block 0.3) demonstrated that the three
flows share substantially more than they differ:

- All three load the same bank types via egm-data.
- All three use the same query/filter UI (ADR-002).
- All three render traces with the same TraceWidget (ADR-024).
- All three live inside the same layout shell (ADR-025).
- Two of three (signal-exploration, ML-diagnostics) save observations
  to the phase manifest (ADR-017).

The differences are mostly **which views are active** in each
mode, not which app the user is in. Splitting into three apps would
force redundant bank loading and break workflows like "notice a
feature anomaly → check ML output on it → save as observation."

The paper-figure-prep flow has a fundamentally different *rhythm*
(config-driven, batch, reproducibility-critical) — which is exactly
what ADR-005's headless API handles. The GUI editor for paper figures
is interactive; the actual rendering is a function call.

### Consequences

- `pyproject.toml` declares two console scripts: `egm-studio` and
  `egm-studio-render`.
- Module structure:
  - `myocard_egm_studio.figures` — framework-agnostic, importable
    anywhere; powers both GUI buttons and the headless CLI.
  - `myocard_egm_studio.gui` — Qt shell; mode switcher + views +
    Phase tree.
  - `myocard_egm_studio.cli` — entry points for both scripts.
- Mode-switching UX surfaces in the layout shell (top-bar segmented
  control or left-sidebar tabs — implementation detail, defer to
  build time).
- Future "advanced" use cases (e.g. running the GUI on a remote
  workstation while the renderer runs on a CI box) are supported
  because the headless path doesn't depend on the GUI shell.

---

## ADR-016: GUI framework — PySide6 + pyqtgraph + matplotlib

**Date:** 2026-06-24 (initial); **Locked:** 2026-06-25 (Block 0.5)
**Status:** Accepted

### Context

The interactive GUI shell needs a framework. The headless figure
renderer needs a plotting library. The reference-app study (Block
0.4) and user-flow walkthroughs (Block 0.3) gave us the inputs to
lock this in.

### Decision

- **GUI shell: PySide6 (Qt for Python).**
- **Interactive plotting: pyqtgraph.**
- **Headless / publication figures: matplotlib.**

Same stack as the legacy `egm_viewer_old`; proven on this domain.

### Options considered

1. **PySide6 + pyqtgraph + matplotlib** (chosen).
2. **Streamlit / Dash** (web-based) — rejected: web round-trip
   latency kills the live-preview slider→render pattern (ADR-019);
   limited control over multi-pane layout; not how scientific tools
   feel.
3. **Napari** — rejected: specialized for image-like volumetric
   data; trace-data fit is poor; mismatch in mental model.
4. **Plotly Dash** — rejected: perf ceiling lower than pyqtgraph
   for many-trace displays (per ADR-024 N can reach 64+ in later
   phases); web-deploy assumption doesn't match our desktop-app
   shape (ADR-007).

### Rationale — alignment with already-accepted ADRs

| ADR | How PySide6 + pyqtgraph + matplotlib satisfies it |
|---|---|
| ADR-007 distribution (`pip install` + console script) | Standard Python packaging; both `egm-studio` and `egm-studio-render` ship as console scripts |
| ADR-012 dark default + light toggle | Qt's QSS (CSS-like stylesheet language) handles both themes; dark/light is a stylesheet swap |
| ADR-019 live-preview (slider → re-render) | Qt sliders + PyQtGraph signal/slot is the direct Qt analog of ipywidgets `@interact`; transfer is essentially mechanical |
| ADR-023 image storage (figures rendered from spec) | matplotlib's Agg backend renders headlessly without a display |
| ADR-024 composable trace widget | PyQtGraph's `GraphicsLayoutWidget` natively hosts N PlotItems with shared X-axis |
| ADR-025 layout — resizable columns + collapsible sidebars | Qt's `QSplitter` handles resizable columns; `QDockWidget` (or a lightweight collapsible custom container) handles the side panels; Activity-Bar-style icon strip is a vanilla Qt pattern |
| ADR-013 testing — pytest-qt + pytest-mpl | Both pytest-qt and pytest-mpl assume PySide/PyQt + matplotlib; nothing exotic |

### The "looks engineer-y" concern

Initial framing flagged a worry that Qt apps look engineer-y by
default. ADR-012 (dark theme + QSS work) is how we solve it. The
reference-app study shows that intentional styling on top of Qt can
produce tools that look as polished as RStudio's Electron-based
shell — it's a question of deliberate styling effort, not framework
ceiling.

### Performance — confirmed adequate

The user-flow walkthroughs surfaced the concrete data scale: banks
up to ~10k traces, multi-trace display up to N≈64 (Rhythmia HDx-
scale, future phases), live-preview re-render latency budget of
sub-1-second. PyQtGraph's published benchmarks and the existing
`egm_viewer_old` performance both confirm this is comfortably within
the stack's envelope.

### Consequences

- `pyproject.toml` declares `PySide6`, `pyqtgraph`, `matplotlib` as
  direct deps.
- Module structure: `myocard_egm_studio.gui` imports Qt;
  `myocard_egm_studio.figures` imports matplotlib but NOT Qt (per
  ADR-005, so the headless path stays GUI-framework-independent).
- CI needs `xvfb-run` for the integration test layer (ADR-013).
- No web frontend story for v0.1; future web work (if any) would
  reuse the figures module (matplotlib renders the same on the web
  via mpld3 / similar) but the shell would be a from-scratch rewrite.

---

## ADR-017: Unified Save schema — observations (with embedded trace sets) in the meta repo

**Date:** 2026-06-25
**Status:** Accepted (via cross-artifact linkage deep-dive)

### Context

User-flow walkthroughs surfaced the need for users to save
"interesting things they noticed" — observations with optional trace
lists and optional view-state — so they don't have to re-derive the
same noticing later. The unified Save schema covers both
observations + trace sets, since trace sets always live inside
observations per the cross-artifact deep-dive (a pure trace list
with no prose isn't an observation; saving the observation requires
a body explaining what was noticed).

### Decision

Defer to the cross-artifact linkage design doc:
**`intracardiac-platform/project/cross_artifact_linkage_design.md`**.

Key points relevant to egm-studio:

- **Observation files are standalone JSON files** stored in the meta
  repo at `intracardiac-platform/project/phases/phase_X/observations/<id>.json`.
- **`description` (prose) is required**; `traces` (embedded trace list) and
  `view_state` (egm-studio reload state) are optional. (Shipped as JSON with
  the prose field named `description`, not `body` — see the reconciliation note
  at the top of this doc.)
- **Bank refs are derived** from `view_state.banks_loaded` +
  `traces[].bank`; no separate `references.banks` field.
- **egm-studio writes the file + updates the phase manifest** when
  Save is invoked.
- **Scratch mode** saves to a scratch area when no phase is loaded;
  "Promote to Phase" moves + indexes. *As built, the scratch area grew
  into a full mini-phase (its own manifest, cross-scope resolution,
  save-target choice, auto-add) and lives in per-user app-data, not
  `intracardiac-platform/project/scratch/` — see **ADR-026**.*

### Rationale

Amends ADR-003 ("no session persistence in v0.1"). Partial
persistence — observations + their attached state, but NOT generic
workspace state — is meaningfully different from full session
persistence and is load-bearing for the diagnostic workflows.

### Consequences

- egm-studio v0.1 P0 features include the Save Observation flow.
- egm-contracts v0.5.0 ships a new `observation` schema.
- The Phase GUI (right-rail sidebar) gates the writing path.
- See the cross-artifact design doc for the full schema +
  cross-repo coordination.

---

## ADR-018: Responsive UI sizing strategy

**Date:** 2026-06-25 (**Accepted** + implemented 2026-07-03, B7.7b/c)
**Status:** Accepted

### Context

The bank-summary view shows an 11-panel feature-distribution
thumbnail grid. Fixed sizing breaks on small laptop screens
(panels crowd) and oversized on external monitors (panels balloon).
Naive fit-to-window scales everything uniformly, which hits one of
those failure modes depending on screen size.

### Decision

**Per-panel min/max size clamps + user-selectable global scale
factor + grid-wrap on overflow.** When the window is too narrow to
fit all panels at min size, the grid wraps to more rows; when too
wide for max size, panels stay at max with extra whitespace. Global
scale factor lives in user preferences and persists across
sessions.

Realized in `gui/widgets/feature_grid.py` (B7.7b): a wrapping flow
layout + scroll area of per-feature pyqtgraph panels, each fixed to
`clamp(base * scale, min, max)`, with the scale factor on a slider
and persisted as the `appearance/ui_scale` preference. Revisit if
the wrap behavior feels weird on real devices.

### Consequences

- Layout engine for grid-based views needs to support per-panel
  min/max + wrap, not just uniform scaling.
- User-preference system (XDG-respecting) needs a `ui_scale_factor`
  key.
- Carries through to other multi-panel views (the matched-pair
  comparison grids, the figure-prep preview).

---

## ADR-019: Live-preview strategy for figure-prep + parameter exploration

**Date:** 2026-06-25 (initial); **Updated:** 2026-06-25 (reference-app study)
**Status:** Tentative → **figure-prep case shipped in Block 9 (2026-07-04)**; the
broader parameter-exploration slider vision (egm-features / activation-peak tuning)
remains future.

**As-built (Block 9 — figure prep).** Resolved to a **Matplotlib WYSIWYG** preview,
*not* the `@interact` pyqtgraph-slider pattern below. The preview is a raster of the
real matplotlib recipe (`figures.preview_png`, the same `draw_figure` + `paper_style`
+ `savefig` pipeline as the export), so preview is pixel-identical to the exported PDF
by construction — the exit criterion for free — and every recipe previews with no new
drawing code. A pyqtgraph fast-preview was rejected: only one of the eight paper
recipes has a pyqtgraph twin, and preview ≠ export defeats a figure composer. Sliders
became a **curated form + debounce**; the "manual Run for expensive ops" survived as a
Refresh button that gates the feature-heavy recipes. The perf concern the ADR flags
(real-bank latency) was met by moving the resolve **off the UI thread** (a worker;
requests coalesce, a gated busy dialog shows) rather than by caching/sampling — a
Post-v0.1 perf revision can still supersede this if needed.

### Context

Originally framed around Flow C step 7's "sub-1-sec preview re-render
on each field change" in the figure-prep editor. The reference-app
study widened the scope: Daniel specifically called out the JupyterLab
ipywidgets `@interact` pattern as directly useful for parameter
exploration on real data — e.g. dragging a `sec_peak_threshold_frac`
slider and watching detected secondary peaks appear/disappear on the
trace; dragging a dV/dt-max smoothing-window slider and watching the
activation-peak marker shift.

So live-preview is not just a figure-prep concern. It's a general
parameter-exploration interaction pattern that egm-studio should
support across multiple views (signal exploration, ML diagnostics,
figure-prep).

### Concrete v0.1 use cases

- **egm-features parameter tuning** — drag any tunable kwarg on a
  per-feature function (e.g. `sec_peak_threshold_frac`,
  `lz_binarize_method`, `sample_entropy_r_frac`), watch the
  computed feature value / annotated trace update in real time.
- **Activation-peak anchoring tuning** — drag dV/dt smoothing-window
  width, watch the activation marker shift on the displayed trace.
- **Figure-prep editor** — drag any spec field (axis limits, color
  mapping, similarity-pair selection), watch the preview update.

### Pattern reference: JupyterLab `@interact`

```python
@interact(amplitude=(0.0, 2.0, 0.1), frequency=(1.0, 50.0, 1.0))
def plot_sine(amplitude, frequency):
    ...
```

Slider widget tuple `(min, max, step)` → re-runs the function on drag
→ plot re-renders. For expensive functions, `interact_manual` adds a
"Run" button.

### Options considered

1. **Cached / incremental DataFrames** — compute once per bank-load,
   cache in memory, recompute only on data-source changes.
2. **Preview with a sample** — use a random subsample of the bank for
   live preview; run the full data only on Export.
3. **Manual-trigger fallback** — for very expensive operations, a
   manual "Run" button (the `interact_manual` analog).
4. **Both/all** — caching to avoid recomputation when possible;
   sampling as a fallback for huge banks; manual-trigger for
   prohibitively expensive operations.

### Decision (tentative)

**Adopt the `@interact`-equivalent pattern**, implemented as Qt
sliders bound to plot-redraw callbacks via PyQtGraph's signal/slot
system. Combine with:

- Per-bank feature DataFrame caching (recompute only on bank load /
  source change).
- Debouncing on slider drag (avoid recomputing on every intermediate
  value).
- Manual-trigger fallback (a "Run" button) for operations that exceed
  the latency budget even with caching + debouncing.

**Tentative** because the actual perf characteristics on real banks
need to be validated at implementation time; the architectural choice
is stable, the parameter tuning is what's tentative.

### Rationale

The pattern transfers natively from JupyterLab to Qt — same
architectural idea (slider → callback → re-render), different
framework. No reason to defer the pattern itself, only the perf-tuning
details.

### Consequences

- Trace-display widgets need a clean "rebind to new parameters"
  pathway, not just one-time-render.
- Feature-extraction pipeline needs to be importable into the GUI
  thread cheaply (no heavy module-level work).
- Manual-trigger UI affordance (the "Run" button pattern) gets added
  to the widget library used by the figure-prep editor.

### Next step

Validate at implementation time. If real-bank perf forces a major
strategy change, revise this ADR with a Superseded-by-ADR-NNN status.

---

## ADR-020: Per-feature similarity metric in v0.1; joint metric deferred

**Date:** 2026-06-25
**Status:** Accepted

### Context

ADR-002's filter taxonomy includes similarity-based selection
("show me the IAFDB trace most similar to this synthetic one").
"Similar" requires a distance function. Options range from cheap
per-feature distance ("nearest along `sample_entropy`") to joint
multi-feature distance (Euclidean over normalized features, learned
embedding, weighted average, etc.).

### Decision

**v0.1 ships per-feature similarity only.** User picks a feature
from a dropdown (`sample_entropy`, `peak_to_peak`, etc.); the
nearest trace is computed by sorting by `|target_value - candidate_value|`
along that feature axis. Cheap, transparent, easy to validate.

**Joint multi-feature similarity is deferred** to a future ADR.
Needs more design thought (which features get weighted how? are
features normalized before combining? does a learned embedding
beat hand-engineered features?). v0.1 usage data informs the joint
metric decision.

### Consequences

- Flow A step 7's 3-pane comparison view uses per-feature
  similarity dropdowns.
- Flow B's "nearest correctly-classified counterpart" pattern uses
  per-feature similarity in v0.1 too; this is a known v0.1
  limitation since the most-useful diagnostic similarity might be a
  joint metric.
- Future ADR slot reserved; trigger condition is "first time v0.1
  usage data makes the joint-metric trade-offs clear."

---

## ADR-021: Per-phase manifest file in the meta repo

**Date:** 2026-06-25
**Status:** Accepted (via cross-artifact linkage deep-dive)

### Context

User-flow walkthroughs and high-level review surfaced the need for
a per-phase index of all artifacts (banks, models, observations,
figures, papers) that went into a paper. Without this, "what
produced this paper?" becomes archaeology three months later.

### Decision

Defer to the cross-artifact linkage design doc:
**`intracardiac-platform/project/cross_artifact_linkage_design.md`**.

Key points relevant to egm-studio:

- One **manifest JSON per phase** at
  `intracardiac-platform/project/phases/phase_X/manifest.json`.
- Shallow-index structure with named relationship fields (mapped
  to future graph-edge types in case we ever upgrade).
- **egm-studio is the canonical curator** — the Phase GUI updates
  the manifest as observations / figures / etc. get saved.
- Producers do NOT touch the manifest; they stamp stable IDs on
  their outputs.
- Scan-and-validate script
  (`intracardiac-platform/scripts/validate_manifest.py`) is the
  safety net; run as a release gate before any phase ships a
  paper.

### Consequences

- egm-studio v0.1 includes manifest read + write logic.
- egm-contracts v0.5.0 ships a `phase_manifest` schema.
- The Phase GUI's bottom-section artifact tree displays the
  manifest contents grouped by role-based bank type + non-bank
  artifacts (10 groups total). The 10 groups are a *display* grouping
  derived from each artifact's id prefix; in the manifest the banks live
  in just two lists — `egm_banks` (tbank_ / ptbank_ / lpred_ / upred_)
  and `noise_banks` (nbank_).
- See the cross-artifact design doc for the full spec.

---

## ADR-022: Model unique-ID + cross-artifact linkage

**Date:** 2026-06-25
**Status:** Accepted (via cross-artifact linkage deep-dive)

### Context

Currently every cross-reference between artifacts is a relative
file path. That breaks down for sharing artifacts across machines,
tracking "which model produced this predictions bank" if files
move, aggregating across phases, etc.

### Decision

Defer to the cross-artifact linkage design doc:
**`intracardiac-platform/project/cross_artifact_linkage_design.md`**.

Key points relevant to egm-studio:

- **Stable IDs** with the format `<role-prefix>_<descriptive_name>_<YYYY-MM-DD>`,
  where the role prefix tells consumers what they can do with the
  artifact (`tbank_` / `lpred_` / `upred_` / `ptbank_` / `nbank_` /
  `run_` / `model_` / `obs_` / `fig_` / `paper_`).
- Stable IDs are assigned at write time by the producer and live in
  the artifact's provenance record.
- egm-studio uses the role prefix to drive UI behavior — e.g. the
  `lpred_` / `upred_` split tells Flow B whether a loaded predictions
  bank carries truth labels, selecting the full-metrics vs qualitative
  branch. (As shipped in Block 8 this routes off the loaded bank's
  outcome columns via `gui/sources.frame_eval_mode`, on the single
  Open-bank path — there is no separate "Load Evaluated Bank" entry.)

### Consequences

- Producer repos (egm-classifier, synthetic-egm-pipeline,
  iafdb-pipeline) all need to stamp IDs at write time.
- egm-contracts v0.5.0 ships `id` fields on existing schemas.
- egm-studio's loaders and Phase GUI assume the new ID scheme;
  this is the first egm-studio version, so no migration concern.
- See the cross-artifact design doc for the full ID scheme.

---

## ADR-023: Figure image storage strategy — gitignored + GitHub Releases for banks

**Date:** 2026-06-25
**Status:** Accepted

### Context

Figure spec YAMLs are git-tracked source of truth; the rendered
PDFs / PNGs are deterministic outputs. Tracking binary images in
git pollutes history. Banks have a separate question: how to share
them with collaborators without signing up for a new service.

### Decision

- **Images: `.gitignore`d in the paper repo + regenerated locally
  from spec YAMLs at paper-build time.** Spec is the artifact;
  image is build output.
- **Banks: GitHub Releases attached to producer-repo version tags.**
  Manifest entries carry both local path + (release-time only)
  `download_url`. Uses existing GitHub infrastructure; no new
  service signup.
- **Hugging Face Datasets** as the upgrade trigger when active
  multi-collaborator bank sharing becomes painful via the Release
  download workflow. Daniel already has an HF account.
- **Zenodo** for paper-archival data once a paper actually
  publishes; provides a citable DOI.

### Rationale

Daniel's stated constraint: "preferably without signing up for
another service." GitHub Releases + gitignored images satisfy this
with infrastructure already in use. The HF / Zenodo upgrades have
clear trigger conditions; they're not v0.1 burden.

### Consequences

- Paper repo gets a build-time figure regeneration step (Makefile
  / CI).
- Producer repos (egm-classifier, synthetic-egm-pipeline,
  iafdb-pipeline) need a release workflow that uploads banks as
  assets.
- Scan-and-validate's release-gate mode (Check C in the
  cross-artifact design doc §8) enforces `download_url` presence
  on bank + model entries before the phase is declared shipped.

---

## ADR-024: Composable trace widget (not a singleton trace tab)

**Date:** 2026-06-25
**Status:** Accepted (via reference-app study)

### Context

The reference-app study surfaced a convergent pattern across all three
intracardiac mapping system vendors (CARTO 3, EnSite X, Rhythmia HDx):
multiple traces are displayed as **vertically-stacked tiles with a
shared X-axis**, with N ranging from a few (CARTO mapping window) to
64+ (Rhythmia HDx Orion basket). This is the right mental model for
egm-studio's trace display.

The architectural question: design the trace display as a single
hardcoded "trace tab" with N=1 baked in, or as a **composable widget
unit** that can host N traces with shared X-axis from day one?

### Options considered

1. **Singleton trace tab** — v0.1 ships "the trace tab", a single
   widget that owns its own data-fetch, axis, and toolbar. Future
   multi-trace work requires a rewrite (extract data-fetch from the
   widget, move axis ownership to a parent, redesign the toolbar to
   apply to all traces or per-trace).
2. **Composable widget unit** — v0.1 ships a `TraceWidget` class that
   takes one trace + metadata and renders it, hosted inside a
   `GraphicsLayoutWidget` that can hold N PlotItems. Default N=1, but
   the underlying layout supports N≥1 with shared X-axis natively. No
   rewrite needed when Phase 4 (multi-beat) or future multi-electrode
   work hits.

### Decision

**Composable widget unit, default N=1 at v0.1.**

The `TraceWidget` takes one trace + metadata and renders it.
`GraphicsLayoutWidget` (PyQtGraph's built-in stacked-plot container)
hosts N PlotItems sharing an X-axis. The v0.1 UI instantiates N=1
most of the time; the architecture is already correct for N=8, N=20,
N=64 when later phases need them.

### Rationale

- **Cheap now:** PyQtGraph's `GraphicsLayoutWidget` natively supports
  multi-PlotItem stacking with shared axis; the architectural
  overhead is essentially nil (~30 minutes of design care at
  implementation time vs. an afternoon for the alternative).
- **Expensive later if not done:** retrofitting a singleton to N
  instances means rewriting the data-fetch path, the axis-ownership
  pattern, the toolbar bindings, and the save-state shape — days of
  work + correctness risk.
- **Aligned with industry standard:** the clinical-system mental
  model is "N parallel single-trace tiles sharing an X-axis." We're
  building toward that on day 1 even though v0.1 only uses N=1.
- **Phase 4 (multi-beat) and Phase 5+ (multi-electrode / catheter-
  grid) work both rely on this.** Cf. Phase 8+ live playback (task
  #311) — also rides on this pattern.

### Consequences

- `TraceWidget` lives in `myocard_egm_studio.widgets.trace` (or
  similar), with no assumption that it's the only one in the window.
- The trace-display **container** owns the shared X-axis and
  per-trace layout; individual `TraceWidget` instances render against
  the container's axis rather than owning their own.
- Toolbar actions (pan, zoom, time-scale slider) bind to the
  container, not to a specific widget — so they automatically apply
  to all hosted traces.
- Save-state shape (ADR-017) records `List[TraceRef]`, not
  `TraceRef`. v0.1 typically saves length-1 lists; that's fine.
- Phase 4 + Phase 8+ + any future multi-electrode work get the
  composable substrate "for free" rather than triggering a rewrite.

---

## ADR-025: Layout model — resizable columns with collapsible side panels

**Date:** 2026-06-25
**Status:** Accepted (via reference-app study)

### Context

The reference-app study examined two opposite poles:

- **RStudio**: fixed 4-quadrant grid with optional sidebar — highly
  predictable, easy to test, but rigid. Cramming long intracardiac
  traces into a quadrant wastes their primary informative dimension
  (time).
- **JupyterLab**: free-form dock with drag-anywhere tab placement —
  maximally flexible, but overkill for our use cases and hard to
  write architectural ADRs around.

Daniel's explicit constraints after seeing both options:

- **Not** a fixed 4-quadrant grid.
- Trace display must be able to span the **full window width**
  (rather than be cramped into a corner).
- Acceptable to have either **one big main region** or **two
  side-by-side smaller regions**.

This points to a middle-ground layout model.

### Decision

A **resizable column layout with collapsible side panels**:

- **Top:** menu / header bar (fixed).
- **Optional left sidebar** (collapsible) — channel selection /
  filter controls / query UI; mirrors the clinical-system "channel
  picker" pattern.
- **Main work area:** one or two columns.
  - Single full-width column when the user is focused on traces (the
    typical signal-exploration and figure-prep case).
  - Two side-by-side columns when comparing two things (e.g.
    pair-comparison view from ADR-002).
  - Within each column, vertical stacking is allowed (e.g. traces on
    top + metadata table below).
- **Optional right sidebar** (collapsible) — Phase artifact tree from
  the cross-artifact linkage design.
- All column / sidebar separators are draggable for resize.
- Sidebars collapse to a thin icon strip (Activity-Bar-style from
  JupyterLab) when hidden; click an icon to expand.

### Options considered

1. **Fixed 4-quadrant** (RStudio model) — rejected per Daniel's
   constraint; traces need full window width.
2. **Free-form dock** (JupyterLab model) — rejected as too flexible
   and hard to test; we don't need users dragging tabs into arbitrary
   arrangements.
3. **Resizable columns + collapsible sidebars** (this decision) —
   the middle ground that matches the actual use cases.

### Rationale

- Honors the trace-display constraint (full-width when wanted).
- Honors the comparison-view constraint (two side-by-side columns).
- Honors the cross-artifact design (Phase tree as collapsible right
  sidebar; filter UI as collapsible left sidebar).
- Avoids the design / test burden of full free-form dragging.
- Predictable enough to write tests against; flexible enough to
  accommodate the three user-flow walkthroughs (signal exploration,
  ML diagnostics, paper-figure prep) without contortion.

### Consequences

- Layout shell is a vertical-column container with collapse buttons
  on the left and right sidebars, and a draggable splitter between
  any two main columns.
- ADR-018 (responsive UI sizing) interacts with this — the per-panel
  min/max + grid-wrap behavior applies *within* each column, not
  across the whole window.
- Save-state (ADR-017) records column widths, sidebar
  collapsed/expanded state, and which content is in each column —
  natural extension of the JupyterLab "workspaces" precedent.
- ADR-024 (composable trace widget) lives naturally inside any column
  of any width — the container is column-agnostic.

### Deferred to a later ADR

- **Bottom panel** (JupyterLab "down area" equivalent — for log
  output, status messages, etc.) — not needed for v0.1; revisit if a
  use case emerges.
- **Single-column vs. 2-column switching mechanism** (drag a panel to
  split? menu item? both?) — implementation detail, decide at build
  time.

---

## ADR-026: Scratch is a curated mini-phase — cross-scope resolution + auto-add

**Date:** 2026-07-05
**Status:** Accepted (implemented, B10h)

### Context

ADR-017 introduced "scratch mode": with no phase open, saves land in a
scratch folder and a later Promote-to-Phase moves them in. As Block 10
was built out, scratch had to do much more than hold a couple of loose
files:

- A user with no phase open still wants the same tree, status dots, and
  viewers a phase gives them.
- Observations / figures saved to scratch reference banks; those banks
  (loaded producers) need somewhere to live before a phase exists.
- Promoting a figure *without* its banks writes a broken phase entry —
  the concrete bug that kicked this off.
- The original location (`intracardiac-platform/project/scratch/`)
  assumed the meta repo is always checked out at a fixed relative path,
  which isn't true for an installed GUI.

### Options considered

1. **Loose files + a flat sidebar list** — minimal, but no status /
   validation / viewers, and no way to carry dependencies on promote.
2. **Scratch as a real, self-contained mini-phase** (its own
   `manifest.json`, rendered by the same Phase-tree widget) — more
   machinery, but scratch and phase then share one code path.

### Decision

Scratch is a **real mini-phase**: a per-user app-data folder
(`<app-data>/scratch`, Settings-editable) with its own `manifest.json`,
rendered by the same `phase_tree` widget and validated the same way. On
top of that:

- **Cross-scope resolution.** A scratch artifact resolves its dependency
  ids against **scratch + the loaded phase**; a phase artifact resolves
  against the **phase only**. Scratch is a staging area that may lean on
  the phase; the phase must stay self-contained.
- **Save-target choice.** With a phase open, Save observation / Save
  figure offer **Add to scratch / Add to phase**; the to-phase target is
  enabled only while a phase is loaded.
- **Auto-add dependencies.** Promoting, or saving / loading into a
  phase, pulls the artifact's scratch-resident dependency closure
  (transitive, cycle-safe) into the phase, so a promoted figure brings
  its banks. A Settings toggle (default on) disables it.
- **Producer indexing.** Loaded producers (banks, training runs) are
  indexed as **path-pointer** entries (ADR-021: egm-studio never copies
  producer files). Pending an egm-contracts change to make
  `produced_by_*` optional, indexed producers carry sentinel provenance
  (`unknown` / `0`).

### Rationale

One widget + one manifest schema + one validation path serve both
scratch and phase — no parallel "scratch" code. Cross-scope resolution
matches how people actually work (stage loosely, then curate into a
self-contained phase). Auto-add removes the most common promote
foot-gun (orphaned dependencies) while the toggle preserves manual
control.

### Consequences

- Amends ADR-017's scratch-mode bullet (location + behavior); ADR-021's
  "manifest curator, never copies producer files" boundary is unchanged
  and now applies to scratch too.
- The scan-and-validate hook (call `validate_manifest.py` after writes)
  and **B10g** (manual add / remove of producer entries in a *phase*)
  remain open.
- Deferred egm-contracts: make
  `produced_by_package` / `produced_by_version` optional; add an
  active-view / tab field to observation `view_state`.
- Shipped across B10h (2026-07-05): dependency-aware verification (1a),
  scratch-as-mini-phase (2a), producer load submenus (2b), cross-scope
  resolution + scratch viewers (2c), save-target submenus (2d),
  auto-add (1b).

---

## ADR-027: Noise is a fourth top-level mode, not a Flow A sub-tab

**Date:** 2026-07-06
**Status:** Accepted (implemented, B10g)

### Context

A noise bank (raw IAFDB noise segments extracted by iafdb-pipeline) had
no viewer. The first cut was a right-click pop-up dialog that crammed ~24
segment tiles into a grid — illegible, and clearly not a real feature.
The question was where a proper segment browser belongs. The natural-
looking home was a new tab inside **Signal exploration** (Flow A).

The obstacle: **every Flow A sub-tab operates on a *loaded classifier
bank*** — the Summary landing, the Explore result list, and the Scatter
all read the unified per-trace view-model of banks the user opened. A
noise bank is a *different artifact*: N raw segments, each tagged with
the record + channel it was cut from, with no features, labels, or
predictions. Forcing it into a Flow A tab would mean a tab that ignores
the loaded banks and the shared filter — a foot-gun.

### Options considered

1. **A Flow A sub-tab.** Visually tidy, but the tab would operate on a
   data source unrelated to the rest of Flow A (which all share the
   loaded-bank view-model + filter). Mixes two artifact types in one
   flow.
2. **A top-level mode** on par with Signal exploration / ML diagnostics /
   Paper figures. More chrome (a fourth mode button), but the Noise view
   then owns its own data source cleanly.

### Decision

Noise is a **fourth top-level mode**, ordered **Signal exploration ·
Noise · ML diagnostics · Paper figures** (Noise next to Signal
exploration — both are raw-signal views — ahead of the ML / figure
workflows). Supporting decisions:

- **Mode-driven left sidebar.** The left rail swaps with the mode: the
  noise controls (overview + record/channel filters + segment table)
  replace *Banks & filters* in Noise mode, and it returns for the other
  modes. Both bodies live in one stack so neither rebuilds.
- **Controls in the sidebar, plot in the main area.** The view is split
  (`NoiseControls` emits the chosen segment; `NoiseExplorationView`
  renders it) so each half hosts where it belongs, mirroring Flow A's
  sidebar-filter / main-list split.
- **Aspect-capped plot.** A single trace in a tall pane stretches
  vertically; the plot height is capped to a fraction of its width and
  centred, so it reads as a signal band.
- **Off-thread load.** The whole `.h5` (66k+ segments) is read under a
  progress dialog; the table filters by hiding rows, not repopulating.

### Rationale

Data coherence wins over visual tidiness: a mode's data source should be
one thing. Keeping noise out of Flow A means the loaded-bank view-model
and the shared filter stay meaningful everywhere in Flow A. The fourth
mode is cheap (one more segmented-control button) next to the confusion a
mismatched sub-tab would cause.

### Consequences

- The header segmented control + the modes stack grow from three to four;
  `_MODE_*` constants replace the earlier literal indices.
- The noise `.h5` carries no stable id, so the Noise view reads `bank_id`
  from the sibling `<stem>_run_record.json`. A deferred egm-data change to
  stamp the id into the `.h5` will retire that lookup.
- If Phase 1.5 pursues rigorous signal analysis of the noise itself
  (spectra, statistics), the Noise view is the place those panels land.

---

## Open questions (post-0.5)

All Block 0 ADRs are now Accepted or have a concrete next-step
(ADR-019 is Tentative pending implementation-time validation). The
remaining open items are forward-looking trigger conditions, not
blockers for v0.1:

- **Joint similarity metric for trace pairing** (raised in ADR-002,
  deferred per ADR-020): trigger condition is "first time v0.1 usage
  data makes the trade-offs clear." Options include Euclidean /
  cosine over the egm-features bundle vector, DTW on raw traces,
  learned embedding from an intermediate model layer, or per-mode
  hybrid (cheap for interactive scrubbing, expensive for paper-
  figure pair selection).
- **ADR-019 live-preview perf tuning**: trigger condition is "real-
  bank perf forces a major strategy change at implementation time."
  Revise this ADR with a Superseded-by-ADR-NNN status if it happens.
- **Bottom panel (JupyterLab "down area" equivalent)** (raised in
  ADR-025): trigger condition is "a use case emerges that the
  resizable-column layout doesn't cleanly accommodate."
- **Phase 8+ live playback** (task #311): real-time animated time-
  cursor playback over recorded traces, like clinical mapping system
  live signal streaming. Rides on ADR-024's composable trace widget
  substrate.

### Block 1+ implementation plan

Enumerated at `project/roadmap.md` — 14 blocks total (1 retroactive
done + 13 to do), ~11-15 days focused effort. The first
implementation block (Block 2) is gated on
`myocard-egm-contracts` v0.5.0.
