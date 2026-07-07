# Changelog

All notable changes to `myocard-egm-studio` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — unreleased

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
