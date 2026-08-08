# Changelog

All notable changes to `myocard-egm-studio` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **A phase folder now owns its artifacts.** Indexing a bank, run or model into a phase
  **copies the file in** under `phases/phase_<N>/<type>/` and records a path relative to
  the phase, so the folder can be moved, archived or handed over whole. Promoting from
  scratch does the same. Scratch still records absolute pointers — it is a working area,
  not an archive. The producer's original is never moved or deleted, and removing an
  artifact from a phase deletes only the phase's copy.
- **A bank's companions travel with it.** A synthetic bank names its θ bank and the noise
  bank it was mixed with by paths resolved beside its own `.h5`, so copying it alone left
  a phase holding a bank whose θ could not be found. Those files are now copied alongside
  it, as a noise bank's run-record sidecar already was.
- **Large copies no longer freeze the window.** Copying a 100–500 MB bank into a phase runs
  off the UI thread behind a progress dialog with a working Cancel. Free space is checked
  before the first byte is written, and a cancelled or failed copy leaves nothing behind —
  files land under their real name only once every byte is there.
- **Show metadata reports how a synthetic bank was generated.** After the `synthetic_bank`
  2.0 restructure moved the physics off the ClassifierBank, the summary reads the paired θ
  bank and renders each simulation's geometry / cell model / substrate / activation /
  electrodes / backend config, with the declared θ-spec knobs alongside. Banks with no
  generation side (IAFDB) are unaffected.
- **A noise bank's metadata shows its `bank_id`**, read from the bank itself.

### Changed

- **A noise bank is identified by its own `bank_id`**, read from the `noise_bank` 1.1 root
  attribute rather than from the sibling `_run_record.json`. The sidecar is still read as a
  fallback for banks written before that attribute existed; when both are present and
  disagree, the bank is refused rather than indexed under an id from someone else's run
  record. A sidecar with no `bank_id` no longer blocks a bank that has one.
- **Curator-indexed artifacts record no producer instead of a fake one.** Files indexed
  into a phase or scratch previously carried `produced_by_package = "unknown"` /
  `produced_by_version = "0"`, which reads as a claim about provenance. Those fields are
  now simply absent, and the Phase tree shows *not recorded*.
- **Indexing errors name the actual failure.** Every failure used to end with the same
  advice — that the file must carry a stable id and should be re-generated — which was
  wrong for every other cause. A file that will not parse as a training-run record now
  says so in one sentence (and points at the noise-bank picker, the usual mis-pick),
  instead of a wall of schema-validation errors.
- **Predictions banks standardize on the `.classifier.h5` extension**, so a predictions
  bank and the source bank it was evaluated against are named the same way.
- **A synthetic bank's per-trace metadata no longer carries generation parameters.**
  Following the `synthetic_bank` 2.0 restructure, `fibrosis_density`,
  `fibrosis_density_realized`, `electrode_row`, `electrode_height_mm`, `stim_edge` and
  `seed` are gone from the ClassifierBank; it keeps identity plus the `simulation_id`
  join key. The generation config lives on the parallel `synthetic_bank` and is reached
  through egm-data's join. Filtering or plotting a synthetic bank by one of those fields
  is no longer possible from the ClassifierBank alone.
- **Banks written against `synthetic_bank` 1.1 are refused, not partially read.** There is
  no migration path by design — regenerate them with a current producer.

### Fixed

- **`.gitignore` output-dir patterns are root-anchored**, so a source package named
  `data/`, `artifacts/`, `runs/` … is no longer silently untracked (green locally,
  `ModuleNotFoundError` in CI). `out/` deliberately still matches at any depth, because
  every shipped example spec writes a relative `out/…` path.

### Dependencies

Re-pinned to the Phase-1.5 Wave-1 tags: `myocard-egm-contracts` **v0.6.0**,
`myocard-egm-data` **v0.6.1**, `myocard-egm-features` **v0.2.0** (from v0.5.3 / v0.5.0 /
v0.1.1). The catch22 extra is not taken yet. Dev tooling is now pinned exactly
(`ruff==0.15.17`, `mypy==2.1.0`) so a contributor run, the pre-commit hook and CI agree.

## [0.1.0] — 2026-07-07

First release: a desktop app for intracardiac-EGM signal exploration, ML-training
diagnostics, and reproducible paper-figure generation, plus a headless figure CLI. One
shell, four modes, sharing a single data layer.

### Added

- **Signal exploration** — filter and inspect EGM traces from one or more loaded banks
  by their egm-features values: an overlaid per-feature distribution summary (with KS
  distances), a composable filter over a sortable result table, a per-trace detail
  (waveform + feature values + nearest-in-other-bank similarity), and a 2-D feature
  scatter.
- **ML diagnostics** — compare model runs over an evaluated predictions bank: output
  P(positive) distributions, a metric suite (ROC / AUROC, calibration / ECE, confusion),
  training curves, and an Explore tab that filters to failure cases and finds each one's
  nearest correctly-classified counterpart. Unlabeled banks (IAFDB) get the
  qualitative-only subset — no metrics.
- **Paper-figure prep** — a curated per-recipe spec editor beside a live WYSIWYG preview
  (a raster of the real matplotlib recipe, pixel-identical to the export).
- **Noise mode** — browse the raw IAFDB noise segments of a noise bank by record and
  channel.
- **Headless figure rendering** — the `egm-studio-render` CLI renders any figure from
  its JSON spec, resolving bank ids through a phase manifest (`--phase`) or an explicit
  id→path map (`--banks` / `--bank`); the same `render()` backs both the GUI and the CLI.
- **Eight paper-figure recipes** — `prediction-histogram`, `feature-distribution-overlay`,
  `bar-chart-with-deltas`, `roc-curve-multi-line`, `calibration-reliability-diagram`,
  `trace-pair-gallery`, `summary-table`, `training-curve`.
- **Save flow** — save observations and figure specs into a phase, or into a per-user
  scratch mini-phase, curated by the right-rail Phase tree with per-artifact status and
  dependency-aware verification; **Promote to phase** and manual **Add to / Remove from
  phase**.
- **Performance** — a virtualized result table, a tiered (RAM + write-through disk)
  view-model cache, a cooperative-pumped distribution-grid rebuild, and opt-in scatter
  decimation, keeping the exploration loop responsive on large banks.
- **Theming** — dark (default), light, and vibrant themes, persisted across launches.

### Dependencies

Pins `myocard-egm-contracts v0.5.2`, `myocard-egm-data v0.4.2`, and
`myocard-egm-features v0.1.1`. All bank / record / phase I/O goes through egm-data
against egm-contracts schemas — never raw file access.

[0.1.0]: https://github.com/myocard-labs/egm-studio/releases/tag/v0.1.0
