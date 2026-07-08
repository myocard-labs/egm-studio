# Getting started

**What this is:** a from-scratch setup for developing on `myocard-egm-studio` —
the desktop app for intracardiac-EGM signal exploration, ML diagnostics, and
paper-figure generation. It takes you from a clean machine to running the app,
the CLI, and the test suite, then hands off to the dev loop.

**Who it's for:** a developer new to the repo. If you only want to *use* the
published package, `pip install myocard-egm-studio` and skip to
[Running the app](#running-the-app).

---

## Prerequisites

- **Python 3.10+** (CI tests 3.10 / 3.11 / 3.12).
- **git**, and access to the [myocard-labs](https://github.com/myocard-labs)
  GitHub organization — the sibling packages are pinned to git tags (see below).
- **A display** to run the GUI. Headless machines (CI, containers) can still run
  the GUI *tests* under Qt's offscreen platform — see [Tests](#tests).
- **Linux only:** PySide6 dlopens Qt's system libraries. On a fresh Ubuntu:

  ```bash
  sudo apt-get install -y --no-install-recommends libegl1 libgl1 libxkbcommon0 libdbus-1-3
  ```

  (macOS / Windows ship these with the OS.)

---

## Install for development

```bash
git clone https://github.com/myocard-labs/egm-studio.git
cd egm-studio
python -m venv .venv && source .venv/bin/activate   # or your env manager of choice
pip install -e ".[dev]"
pre-commit install
```

`pip install -e ".[dev]"` pulls the runtime + dev dependencies, including the
three sibling packages, which are **pinned to git tags** in `pyproject.toml`:

| Sibling | Pin | Role |
|---|---|---|
| `myocard-egm-contracts` | `v0.5.3` | The schemas + typed models for every cross-component format. |
| `myocard-egm-data` | `v0.5.0` | All bank + phase-artifact I/O (egm-studio never opens an HDF5 / JSON directly). |
| `myocard-egm-features` | `v0.1.1` | The per-trace feature extractors (`bundle.extract_all`). |

pip fetches those tags from GitHub automatically — no manual step.

**Working across siblings.** If you're editing a sibling (say egm-features) at
the same time, clone it next to this repo and install it editable *after* the
line above, so your local checkout shadows the pinned tag:

```bash
pip install -e ../egm-features        # now imports resolve to your working copy
```

(There is no `requirements-dev.txt` or lockfile — the git pins are the single
source of truth; a local editable install is the intentional override.)

---

## Running the app

```bash
egm-studio
```

Then:

- **File ▸ Open bank** — load a classifier or predictions bank (`.h5`). A
  predictions bank auto-populates the **ML diagnostics** mode; opening a second
  bank *adds* it (both are pooled into one filterable table).
- **File ▸ Open phase** — load a phase folder's `manifest.json` into the
  right-rail artifact tree.
- The four modes (Signal exploration · Noise · ML diagnostics · Paper figures)
  switch from the segmented control in the header. See
  [user_flow_walkthroughs.md](../project/user_flow_walkthroughs.md) for a
  click-through of each.

Preferences (theme, scratch folder, the view-model cache ceiling) live under
**File ▸ Settings** and persist across launches.

---

## Rendering figures from the CLI

The paper-figure pipeline runs headlessly — no shell, no display:

```bash
# Resolve a spec's bank ids through a phase manifest…
egm-studio-render fig_prediction_histogram.json --phase path/to/phase/

# …or supply an id→path map by hand:
egm-studio-render fig_prediction_histogram.json --banks banks.json -o figure.pdf
egm-studio-render fig_prediction_histogram.json --bank BANK_ID=preds.h5   # repeatable
```

Copy `examples/bank_paths.example.json` to a local (git-ignored) `banks.json`
and fill in absolute paths. An already-rendered output is skipped unless you
pass `--overwrite`. The same `render()` is importable — see
[Programmatic usage in the README](../README.md#programmatic-usage).

---

## Tests

```bash
pytest                                   # full suite
pytest -m "not gui"                      # fast set — skips the slow pytest-qt GUI tests
pytest --cov                             # with coverage
ruff check . && ruff format --check .    # lint + format
mypy                                     # type check
```

The pytest-qt GUI tests spin up real Qt widgets and run headless under the
**offscreen** platform. On a machine with no display, export the platform first:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

Every test under `tests/gui/` is auto-tagged `gui`, so `-m "not gui"` gives a
fast inner-loop run; CI runs the fast set on `development` pushes and the full
suite on `release` + PRs (`.github/workflows/ci.yml`).

---

## The dev loop

- **Branches.** Active work lands on `development`; `release` is the stable
  branch, tagged at phase boundaries. PRs go `development → release`.
- **Before every commit,** the pre-commit hook runs `ruff format` + `ruff check`
  (and reformats — re-stage if it does). Match it locally with
  `ruff format . && ruff check .`.
- **Commit messages** are `[Type] Subject` (e.g. `[Feature]`, `[Fix]`, `[Test]`,
  `[Docs]`, `[Build]`) with an asterisk-bullet body; keep feature / test / docs
  changes in separate commits.
- **Type + test everything.** `mypy` runs strict; new behavior ships with tests
  in the mirror `tests/` tree.

---

## Where to go next

- **[project/architecture.md](../project/architecture.md)** — how the app is
  built: the three-layer rendering split, the module map, and the ADR index.
- **[project/design.md](../project/design.md)** — the ADR log (every decision
  with its context + rationale).
- **[docs/theory.md](theory.md)** — the math behind the figures.
- **[docs/saving_work.md](saving_work.md)** — the save / phase / scratch flow.
- **[project/roadmap.md](../project/roadmap.md)** — the block-by-block plan and
  what's shipped.
