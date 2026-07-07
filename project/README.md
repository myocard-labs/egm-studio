# project/ — internal design + investigations

**What this is:** the docs *for the people building and maintaining egm-studio* —
the current-state architecture, the decision record behind it, the plan, and the
investigations that drove specific choices. If you're here to *use* the repo
(install, run, call it), you want [`../docs/`](../docs/) instead.

**New to the repo?** Read [`architecture.md`](architecture.md) first (what's
built + how it fits), then dip into [`design.md`](design.md) for the *why* behind
any decision its `[ADR-N]` pointers reference.

## Index

| Doc | What it is | When you'd read it |
|---|---|---|
| [architecture.md](architecture.md) | Current-state "how it's built": the core invariants, module map, the three-layer rendering split, the registry pattern, cross-repo deps, and the data-flow model. Stays in lock-step with the code. | **Start here** — to understand what exists today. |
| [design.md](design.md) | The ADR log — every design decision (28 ADRs) with its context, the options weighed, and the rationale. The source of record `architecture.md` points into. | To understand *why* a choice was made, or before revisiting one. |
| [roadmap.md](roadmap.md) | The block-by-block build plan (14 blocks) with shipped-status annotations and forward-looking follow-ups. | To see what's shipped, what's next, and where a feature is tracked. |
| [user_flow_walkthroughs.md](user_flow_walkthroughs.md) | As-built click-throughs of each flow (signal exploration, ML diagnostics, paper-figure prep, save). | To learn what the app actually does, screen by screen. |
| [paper_figure_inventory.md](paper_figure_inventory.md) | The catalog of paper-figure recipes — each figure's purpose, inputs, and status. | When adding or wiring up a figure recipe. |
| [optimization_survey.md](optimization_survey.md) | The Block 11 performance investigation: profiling findings + the out-of-core / large-data techniques weighed (feeds ADR-028). | When touching load performance or the view-model cache. |
## What belongs here (vs `docs/`)

`project/` is internal: design rationale, roadmaps, and repo-specific
investigations. `docs/` is external: install, run, call, and read-the-figures
guides for someone consuming the package. Each folder opens with its own index.

Two things do **not** belong here:

- **Cross-component investigations** (ones that drove decisions in more than one
  repo) live in the meta repo's `intracardiac-platform/project/`, not here.
- **Disposable scratch notes** from a single chat — keep them out of git until
  they crystalize into a decision (then they become an ADR in `design.md`).

This split is the myocard-labs convention; see the
`feedback-docs-vs-project-folders` note.
