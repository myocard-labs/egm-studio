# myocard-egm-studio

> Desktop application for intracardiac EGM signal exploration, ML
> training-result diagnostics, and reproducible paper-figure generation.

Part of the [myocard-labs](https://github.com/myocard-labs) cardiac
signal-processing toolkit.

---

## Why

`myocard-egm-studio` is the consumer-facing desktop app of the myocard-labs
stack. It loads the HDF5 banks, JSON training records, and predictions banks
the producers write — always through `myocard-egm-data` against
`myocard-egm-contracts` schemas, never raw file I/O — and turns them into an
interactive analysis surface plus publication-ready figures.

Three modes from one shell:

- **Signal exploration** — query, filter, and inspect EGM traces by any
  combination of trace-level features (peak-to-peak, sample entropy, dominant
  frequency, ...). Filter-and-sort-first, not browse-the-whole-bank.
- **ML diagnostics** — open a training run (`run.json` + `metrics.csv` +
  predictions bank), inspect failure cases, and surface the most informative
  examples by predicted probability or model disagreement.
- **Paper-figure prep** — build publication-quality, reproducible figures from
  per-figure JSON specs, iterated interactively and regenerable headlessly.

A three-layer rendering split keeps the figure code framework-agnostic:
`analysis/` (pure numpy / pandas / scipy / egm-features computation — no Qt, no
matplotlib) feeds `charts/` (matplotlib for static export, pyqtgraph for the
GUI), which `figures/` exposes as a thin headless `render(spec)`. The Qt shell
is a frontend on top; the same `render()` powers the `egm-studio-render` CLI
with no shell — so the figure path runs in notebooks and CI without a display.

Unlike the leaf libraries, egm-studio sits at the bottom of the dependency
graph: it consumes `myocard-egm-contracts`, `myocard-egm-data`, and
`myocard-egm-features`, and reads the banks the producers (`egm-classifier`,
`synthetic-egm-pipeline`, `iafdb-pipeline`) write — but depends on none of the
producers directly.

---

## Install

From PyPI (when published):

```bash
pip install myocard-egm-studio
```

From source during pre-1.0 iteration:

```bash
pip install git+https://github.com/myocard-labs/egm-studio.git
```

Editable install for development:

```bash
git clone https://github.com/myocard-labs/egm-studio.git
cd egm-studio
pip install -e ".[dev]"
pre-commit install
```

Runtime deps: `myocard-egm-contracts`, `myocard-egm-data`,
`myocard-egm-features` (pinned to git tags pre-1.0), plus `matplotlib`,
`numpy`, `pandas`, `scipy`. The interactive GUI stack (PySide6 + pyqtgraph) is
added with Block 4.

---

## Programmatic usage

egm-studio is primarily a desktop app, but its figure-generation core is
framework-agnostic and importable — the same `render` the GUI and the
`egm-studio-render` CLI call:

```python
from myocard_egm_data.phases import load_figure_spec
from myocard_egm_studio.figures import render

# Read a figure_spec JSON (validated against the egm-contracts schema) and
# render it to the path it names. Recipes are registered by charts/matplotlib;
# until Block 3 fills that registry, render() raises a clear UnknownRecipeError.
spec = load_figure_spec("figure_specs/fig_feature_distributions.json")
render(spec)
```

The same renderer is a console script for batch / scripted regeneration:

```bash
egm-studio-render figure_specs/fig_feature_distributions.json -o figure.pdf
```

The analysis layer stands alone too — pure functions over the egm-features
view-model, no GUI required:

```python
from myocard_egm_studio.analysis import distributions

ks = distributions.ks_distance(synthetic_feature_values, iafdb_feature_values)
```

---

## Module map

| Module | What's in it |
|---|---|
| `myocard_egm_studio.analysis` | Pure data computation (no rendering, no Qt): `distributions` (CDF / KS / Wasserstein / histogram / KDE), `aggregation` (between-group feature distance), `similarity` (per-feature nearest). |
| `myocard_egm_studio.view_model` | `build_view_model` — the unified per-trace table joining identity + bank metadata + the egm-features columns. |
| `myocard_egm_studio.charts.matplotlib` | The publication (static) rendering backend + the recipe registry the dispatch fills. |
| `myocard_egm_studio.figures` | `render(spec) -> Path` — the thin headless dispatch over `charts/matplotlib`. |
| `myocard_egm_studio.cli` | Console-script entry points: `render` (`egm-studio-render`). |

The interactive Qt shell (`gui/`), the `charts/pyqtgraph/` backend, and the
`loaders/` + `save/` layers land in Blocks 4–10 — see
[`project/roadmap.md`](project/roadmap.md).

---

## Tests

```bash
pytest                  # full suite (no display required)
pytest --cov            # with coverage
ruff check .            # lint
ruff format --check .   # format check
mypy                    # type check
```

CI runs the same checks on Python 3.10, 3.11, and 3.12 — see
`.github/workflows/ci.yml`. The unit + snapshot layers run without a display;
the GUI integration layer (added with the Qt shell) runs under `xvfb-run`.

---

## Project status

Pre-v0.1.0; built across 13 blocks (see
[`project/roadmap.md`](project/roadmap.md)). **Block 2 is done:** the
`analysis/` + `view_model/` + `figures/` framework-agnostic foundation and the
`egm-studio-render` CLI skeleton. The figure recipes (Block 3) and the
interactive Qt GUI (Block 4+) are next, so the app is not yet
end-user-runnable. Pins `myocard-egm-contracts v0.5.1`, `myocard-egm-data
v0.4.1`, `myocard-egm-features v0.1.1`.

- For the design rationale (the 25 ADRs, the three-layer rendering split, the
  layout + save models), see [`project/architecture.md`](project/architecture.md)
  and the ADR log [`project/design.md`](project/design.md).
- For the block-by-block implementation plan, see
  [`project/roadmap.md`](project/roadmap.md).
- The full user manual lands in Block 12 at `docs/usage.md`.
- For the broader refactor context, see
  `intracardiac-platform/project/project_plan.md`.

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
