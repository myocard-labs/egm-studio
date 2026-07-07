# docs/screenshots/

Images embedded in [`../usage.md`](../usage.md). These are a **regenerable cache**, not
hand-made assets — both are produced by committed scripts, so they're checked in only so
the manual renders on GitHub (and in a fresh clone) without a build step. Regenerate any
time; don't hand-edit.

**What's here**

- `NN-mode-view.png` — whole-window GUI screenshots (e.g. `03-signal-summary.png`,
  `09-ml-metrics.png`). The number orders them as they appear in the manual.
- `figures/<recipe>-{good,bad}.png` — the good/bad example renders for the figure-reading
  guide (§4), one pair per matplotlib recipe.

**Regenerate**

```bash
# GUI screenshots — offscreen Qt, dark theme, 1200x820, demo banks from banks/
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py        # all groups
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py signal # just one group

# §4 example figures — matplotlib only, seeded (deterministic)
python scripts/render_figure_examples.py
```

Run both from the repo root in an environment with the app + its siblings installed (see
[getting-started.md](../getting-started.md)). The screenshots pull from small synthetic
demo banks in `banks/`, so they carry no real-patient data.

**Conventions** (for anyone adding a slot): PNG, dark theme (the default), consistent
width so the manual reads evenly. Embed in `usage.md` as a click-to-expand thumbnail:
`<a href="screenshots/NN-....png"><img alt="..." src="screenshots/NN-....png" width="600"></a>`.
