# docs/ — user + developer documentation

External-facing documentation for `myocard-egm-studio`. Start with
**getting-started** if you're new to the repo.

| Doc | What it covers |
|---|---|
| [getting-started.md](getting-started.md) | From a clean machine to running the app, the CLI, and the tests, plus the dev loop. **Start here.** |
| [saving_work.md](saving_work.md) | The save flow — observations, figures, phases, and the scratch area. |
| [theory.md](theory.md) | The math behind the figures and how to read each plot. |

For the design rationale (the ADRs, the layering, the module map) see the
internal docs in [`../project/`](../project/) — start with
[`architecture.md`](../project/architecture.md).

---

**What belongs here** (vs `project/`): `docs/` is *for the people consuming the
repo* — how to install, run, and call it. Design rationale, roadmaps, and
investigation reports live in `project/`. Each page opens with "what this is /
who it's for." This split is the myocard-labs convention; see the
`feedback-docs-vs-project-folders` note.
