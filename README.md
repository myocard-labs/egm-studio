# myocard-egm-studio

> Desktop application for intracardiac EGM signal exploration, ML
> training-result diagnostics, and reproducible paper-figure generation.

Part of the [myocard-labs](https://github.com/myocard-labs) cardiac
signal-processing toolkit.

---

## What it is

`myocard-egm-studio` is the consumer-facing desktop app of the myocard-labs
stack. It loads the HDF5 banks, JSON training records, and predictions banks the
producers write — always through `myocard-egm-data` against
`myocard-egm-contracts` schemas, never raw file I/O — and turns them into an
interactive analysis surface plus publication-ready figures.

One shell, four modes:

- **Signal exploration** — filter and inspect EGM traces by any combination of
  trace-level features (peak-to-peak, sample entropy, dominant frequency, …).
  Filter-and-sort-first, not browse-the-whole-bank.
- **Noise** — browse the raw noise segments of an IAFDB noise bank, by record
  and channel.
- **ML diagnostics** — open an evaluated predictions bank and compare model
  runs: output distributions (P(positive) per source), the metric suite (ROC /
  calibration / confusion), training curves, and an Explore tab that filters to
  the failure cases (FP / FN) and finds each one's nearest correctly-classified
  counterpart.
- **Paper-figure prep** — edit a per-figure JSON spec in a curated form beside a
  live WYSIWYG preview (a raster of the real recipe, pixel-identical to the
  export), then render.

The figure code is **framework-agnostic** by design: `analysis/` (pure
numpy / pandas / scipy / egm-features computation — no Qt, no matplotlib) feeds
`charts/` (matplotlib for static export, pyqtgraph for the GUI), which
`figures/` exposes as a thin headless `render()`. The Qt shell is a frontend on
top; the same `render()` backs the `egm-studio-render` CLI, so figures
regenerate in notebooks and CI with no display.

egm-studio sits at the **bottom of the dependency graph**: it consumes
`myocard-egm-contracts` / `-data` / `-features` and reads the banks the producers
(`egm-classifier`, `synthetic-egm-pipeline`, `iafdb-pipeline`) write — but
depends on none of the producers.

---

## Install

```bash
# From PyPI (when published)
pip install myocard-egm-studio

# From source, during pre-1.0 iteration
pip install git+https://github.com/myocard-labs/egm-studio.git
```

For a development setup — the editable install, the sibling git pins, the
headless-Qt system libraries, and the dev loop — see
**[docs/getting-started.md](docs/getting-started.md)**.

---

## Quick start

Launch the desktop app:

```bash
egm-studio
```

Then **File ▸ Open bank** to load a classifier or predictions bank (`.h5`). A
predictions bank lights up the ML-diagnostics mode automatically;
**File ▸ Open phase** loads a phase's artifact tree into the right rail.

Render a paper figure headlessly (no shell):

```bash
# Resolve a spec's bank ids through a phase manifest…
egm-studio-render fig_prediction_histogram.json --phase path/to/phase/

# …or map ids to files by hand (a {bank_id: path} JSON, or repeated --bank):
egm-studio-render fig_prediction_histogram.json --banks banks.json -o figure.pdf
```

`examples/bank_paths.example.json` is a starter `--banks` map. An
already-rendered output is skipped unless you pass `--overwrite`.

---

## Programmatic usage

The figure-generation core is framework-agnostic and importable — the same
`render` the GUI and CLI call:

```python
from myocard_egm_data.banks import load_classifier_bank
from myocard_egm_data.phases import load_figure_spec
from myocard_egm_studio.figures import render
from myocard_egm_studio.loaders import prediction_group_from_bank

# A figure_spec names a recipe + the bank ids its groups draw from. Recipes are
# pure plotting, so render() takes already-prepared data — build it with the adapter.
spec = load_figure_spec("figure_specs/fig_prediction_histogram.json")
group = prediction_group_from_bank(load_classifier_bank("preds_synth.h5"), name="Synthetic val")
render(spec, data=[group])
```

The analysis layer stands alone too — pure functions over the egm-features
view-model, no GUI required:

```python
from myocard_egm_studio.analysis import distributions

ks = distributions.ks_distance(synthetic_feature_values, iafdb_feature_values)
```

---

## Repository layout

| Package | Responsibility |
|---|---|
| `analysis/` | Pure data computation — distributions (CDF / KS / Wasserstein / KDE), between-group feature distance, per-feature similarity. No rendering, no Qt. |
| `view_model/` | The Qt-free per-trace view-model: `build_view_model` (identity + metadata + egm-features, plus ML-outcome columns), multi-bank `combine`, bank summaries, per-trace detail + similarity, the Phase-tree models, and the tiered view-model `cache` (RAM + write-through disk). |
| `charts/` | Rendering backends — `matplotlib` (static export + the recipe registry) and `pyqtgraph` (the GUI-embedded charts + GUI-only recipes). Shared `inputs` / `palette` keep a chart matching its twin. |
| `figures/` | `render(spec, *, data) -> Path`, the thin headless dispatch over `charts/matplotlib`, plus `preview_png` for the GUI's WYSIWYG preview. |
| `loaders/` | ids/paths → in-memory recipe inputs; view-model frame → chart inputs; phase manifest → `{artifact_id: path}`. |
| `gui/` | The PySide6 shell — `app` / `shell` (layout + the 4-mode switch) / `theme` / `preferences`, the `widgets/` primitives, and the `views/` that assemble each mode. |
| `cli/` | Console entry points — `egm-studio-render`. |

The full module-by-module map + the design rationale live in
**[project/architecture.md](project/architecture.md)**.

---

## Documentation

| Doc | For |
|---|---|
| **[docs/getting-started.md](docs/getting-started.md)** | Install from scratch, run the app + CLI, run the tests, the dev loop. **Start here.** |
| [docs/saving_work.md](docs/saving_work.md) | The save flow — observations, figures, phases, and the scratch area. |
| [docs/theory.md](docs/theory.md) | The math behind the figures and how to read each plot. |
| [project/architecture.md](project/architecture.md) | Current-state synthesis: the layering, the module map, the ADR index. |
| [project/design.md](project/design.md) | The ADR log — every design decision with its context + rationale. |
| [project/roadmap.md](project/roadmap.md) | The block-by-block plan and what shipped. |
| [project/user_flow_walkthroughs.md](project/user_flow_walkthroughs.md) | As-built click-throughs of each flow. |

---

## Development

```bash
git clone https://github.com/myocard-labs/egm-studio.git
cd egm-studio
pip install -e ".[dev]"
pre-commit install
```

```bash
pytest                                   # full suite (pytest -m "not gui" skips the slow Qt tests)
ruff check . && ruff format --check .    # lint + format
mypy                                     # type check
```

The pytest-qt GUI tests run headless under Qt's **offscreen** platform — set
`QT_QPA_PLATFORM=offscreen` if you run the suite on a machine with no display.
CI runs the same checks on Python 3.10 / 3.11 / 3.12; a push to `development`
runs the fast set and `release` + PRs run the full suite. See
`.github/workflows/ci.yml`.

---

## Project status

Built as a 14-block roadmap, now complete — **`v0.1.0` is tagged.** Blocks 2–13 built the app: the
headless figure pipeline + eight paper-figure recipes (Blocks 2–3), the Qt shell
(4), the trace-display widgets + pyqtgraph backend (5), the read-only Phase tree
(6), the three interactive flows — Signal exploration (7), ML diagnostics (8),
Paper-figure prep (9) — the save flow (10), a performance pass (11: a
virtualized result table, a tiered view-model cache, opt-in scatter decimation,
and a CI fast/slow test split), a documentation professionalization pass (12),
and the full user manual (13); Block 14 cut the release. `development` now pins
`myocard-egm-contracts v0.5.3`, `myocard-egm-data v0.5.0`,
`myocard-egm-features v0.1.1`. See [project/roadmap.md](project/roadmap.md) for
the full block-by-block history and [project/design.md](project/design.md) for
the 28 ADRs.

---

## Citation

If you use this software in academic work, please cite:

```bibtex
@software{klein_myocard_egm_studio_2026,
  author  = {Klein, Daniel},
  title   = {myocard-egm-studio: desktop analysis, ML diagnostics, and
             reproducible paper figures for intracardiac EGM data},
  year    = {2026},
  url     = {https://github.com/myocard-labs/egm-studio},
}
```

---

## License

MIT — see [LICENSE](LICENSE). Third-party software-license acknowledgements are
in [NOTICE](NOTICE).
