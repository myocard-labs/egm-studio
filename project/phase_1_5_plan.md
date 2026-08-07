# egm-studio — Phase 1.5 implementation plan

**Repo:** egm-studio · **Phase:** 1.5
**Phase design doc:** `intracardiac-platform/phases/phase_1_5/design.md`
**Status:** in progress · **Progress:** 2/43 steps done
**Repo estimate:** **103–232 h active** (44 pts) — cold-start ranges, see [Estimates](#estimates--complexity).

> **Second pass, 2026-07-28.** Every issue now broken to commit-sized steps against the actual code.
> Three first-pass steps were too big for one commit and split into sub-ids (**S5→S5a–c**,
> **S11→S11a–c**, **S14→S14a–b**); parent ids are preserved so the references already sent to the
> project-lead and headed for §6 still resolve. Decomposition moved the estimate up — see
> [What the second pass changed](#what-the-second-pass-changed).
>
> **B17 scope settled (2026-07-28): copy _all_ artifact types into the phase, banks included**;
> HDF5 is phase-stored locally but never committed. Authoritative layout = Phase-1.5 design §8. See
> [B17 storage scope](#b17-storage-scope--settled).
>
> **θ reversed (2026-07-28, [`synthetic_bank_source_of_truth.md`](../../intracardiac-platform/project/investigations/synthetic_bank_source_of_truth.md) §12).**
> θ does **not** ride on the ClassifierBank. T4 views consume the typed **`SyntheticBank`** egm-data
> returns and read θ from it. **S4 is reinstated** — as the SyntheticBank read path — and STU6 is no
> longer a small migration.

---

## Scope — what this plan covers

| Phase item | What it needs from this repo | Steps |
|---|---|---|
| STU6 | Adapt to v2.0 **and** consume the typed `SyntheticBank` for T4 (θ + per-sim config) | S0–S4, S7 |
| B17 · B19 | Phase-storage: sentinel removal, relative in-phase paths, copy-into-phase (all types) | S5a–S5d |
| B20 | Noise bank's `bank_id` from the `.h5` attr, not the sidecar | S6 |
| STU2 | Noise-bank frequency / statistics / outlier analysis + its Noise-mode read-out | S8–S10 |
| STU3 (+ B18, P3) | Training-run viewer overhaul — train/val/test series, split-aware inspection, seed spread, saturation metrics, paired cross-arm test | S11a–S11e, S12 |
| STU5 | Sim↔IAFDB feature-distribution comparison (success criterion #2) | S13, S14a–S14b |
| STU1 | Feature-vs-θ scatter | S15 |
| **STU7** | Feature-responsiveness / identifiability screening + read-out | S18–S19 |
| STU4 | Parameter estimator — sub-package, fifth GUI mode, paper recipes | S16–S17, S20–S31 |
| **STU8** *(new)* | Positional-sensitivity analysis over the SEP13 probe bank | S33–S34 |
| — | Docs + phase exit | S32 |

## Wave 1 — upstream state as of 2026-08-06

egm-studio is **the last Wave-1 repo** (design §7 step 10); steps 1–9 are ✅. Everything this repo
consumes is tagged, so nothing here is waiting:

| Dependency | Pin now | Pin to | Why |
|---|---|---|---|
| `myocard-egm-contracts` | v0.5.3 | **v0.6.0** | the coordinated schema bump (`synthetic_bank` 2.0, run-record 1.2, `phase_manifest`, `noise_bank`, `iafdb_bank`) |
| `myocard-egm-data` | v0.5.0 | **v0.6.1** | readers/writers + the **join** this repo needs; `.1` is the CL-136 RootModel-repr fix (non-breaking) |
| `myocard-egm-features` | v0.1.1 | **v0.2.0** | FEA1 — catch22 behind an optional extra, provider seam, `sets` registry, per-call selection |

**What actually changed under us**, beyond the schema itself:

- **The θ join is shipped, not ours to write.** `egm-data/banks/joins.py` gives
  `simulation_configs()` and `join_traces_with_simulations()`, returning typed `SimulationConfig` /
  `TraceWithSimulation`. S4 consumes it.
- **The ClassifierBank got much thinner** (CL-109). Synthetic-egm de-duplicated per §12: five
  bank-level keys where v1.1 had 23, three per-trace keys plus three more *only when the mixer ran*.
  `seed` is gone as well as the five generation fields.
- **catch22's usable-now subset is now our code, not the library's** (CL-142), and we should request
  only the features we want (CL-141).
- **`T` = 192 ms at 1 kHz** is settled (CL-024 §4) — egm-features' reliability analysis is written at
  that window.
- **Three of our tests will fail on re-pin**, pre-swept by egm-data: `conftest.py:78`,
  `test_builder.py:48,58`, `test_artifact_metadata.py:60,77`. S1 fixes them so the step ends green.
- **Two inbox chores** (CL-085 dev pins + `type: ignore` reasons, CL-099 `.gitignore` anchoring) →
  new **S0**, landing first as a `[Chore]` the way egm-features cleared theirs in-session.

## Design notes

**STU6 is two jobs, not one** (revised 2026-07-28 per investigation §12). The artifact-purpose reframe
makes the ClassifierBank a **source-agnostic ML compression** — signal + label + a `LabelPolicy` id +
the `simulation_id` / `pair_index` **join key**, and nothing else from generation. θ and the per-sim
typed config live on the **parallel `synthetic_bank`**. So STU6 is:

1. **Adapt the existing ClassifierBank path to v2.0** — it simply *loses* `fibrosis_density`,
   `fibrosis_density_realized`, `electrode_row`, `electrode_height_mm`, `stim_edge`; no θ arrives to
   replace them. `view_model/builder.py:172–175` flattens `trace_metadata` generically, so this is
   fixtures, the documented column contract, and the `label` path (a plain int under the per-sim
   `label_policy`).
2. **Open a second read path** — the typed `SyntheticBank` from egm-data, for the T4 views (S4).
   egm-studio has only ever called `load_classifier_bank`; this is a genuinely new artifact shape in
   `loaders/` + `view_model/`, and it is where θ, the θ-spec, and the per-sim config now come from.

**A visible regression to name.** Flow A can filter and scatter a synthetic bank by
`fibrosis_density` / `electrode_height_mm` today; after v2.0 those columns are gone from the
ClassifierBank path. Restoring them in Flow A means the same `simulation_id` join the T4 path does.
S4 makes the join available; whether Flow A picks it up is a scoping call, flagged below.

**Provenance moves too.** `view_model/artifact_metadata.py:162` renders nested values as
`json.dumps(value)` — one unreadable line for v2.0's typed polymorphic `simulations/` group. S3 gives
it a recursive indented render, now sourced from the typed `SyntheticBank` rather than the
ClassifierBank's `bank_metadata`.

**Repo-local decisions** (each gets its ADR at the step that needs it):

- **ADR-029 — Calibration is a fifth top-level mode**, extending ADR-027's four-mode shell, for the
  same reason ADR-027 gave Noise its own mode: the estimator operates on a *generator*, not on a
  loaded bank or a model run. Written at S28.
- **ADR-030 — the extraction-ready boundary.** Design §4.3 + E.2: zero Qt imports under
  `parameter_estimator/`; the core imports only `ports.py`; studio touchpoints live outside and
  depend inward. Enforced by an import-boundary test beside the existing `analysis/` rules. STU7's
  `screening.py` lives inside this boundary despite being a separate §3 issue — the split is
  scheduling, not module ownership.
- **New dependencies: `scikit-learn` + `dcor`.** `GaussianProcessRegressor` is the only maintained
  GP that stays torch-free (GPyTorch pulls torch and breaks the foundation rule; GPy is
  unmaintained). MMD is DIY over `sklearn.metrics.pairwise.rbf_kernel` with the median heuristic;
  energy distance is `dcor.energy_distance` (multivariate — scipy's is 1-D only). Not taking `hyppo`
  (heavy) or `sbi` (a framework where we need one distance and one GP).
- **Per-feature diagnostics reuse `analysis/distributions.py`.** `ks_distance` /
  `wasserstein_distance` already exist and already back `bar-chart-with-deltas`.
  `parameter_estimator/distances.py` owns only the two *joint* distances.

**Two cross-issue ordering facts** (both feed §7 — see [Follow-up](#follow-up-for-7)):

1. `distances.py` (S17) is scored under STU4 but is a **STU5** dependency — S14a is the same call.
2. `ports.py` (S16) + the shared `FeatureExtractor` (S20) are scored under STU4 but are **STU7**
   dependencies — `screening.py` imports only `ports.py`, and screening must measure with the
   extractor the optimiser will use or the set it selects doesn't transfer.

## Steps

☐ todo · 🔨 wip · ✅ done · ⊘ dropped. Waves follow design §7. **Mark a step ✅ here as it lands.**

### Wave 1 — schema migration (STU6 · B17 · B19 · B20)

#### S0 — Clear the inbox ✅ (1–2 h) *(new — CL-085 · CL-099)*
- **Change:** three chores, independent of the migration, so they land first as one `[Chore]`.
  **(a)** pin the dev tools exactly in `[dev]` — `ruff==0.15.17`, `mypy==2.1.0` (currently
  `ruff>=0.6.0` / `mypy>=1.10`; egm-studio and egm-features were the last two unbounded repos, and
  egm-features has now shipped theirs). **(b)** give each of the **6 `type: ignore`s** in `src/` a
  reason comment, per the new fleet convention (CL-085 counted 7 — the seventh grep hit is a docstring
  mention in `trace.py`, not an ignore). Only two are the pyqtgraph-has-no-`py.typed` case; three are
  mypy failing to carry a narrowing into a comprehension, and one is a deliberately loose `object`
  parameter — which is why a generic reason would have been worse than none. **(c)** root-anchor the `.gitignore`
  output-dir patterns: `data/` `checkpoints/` `runs/` `logs/` `artifacts/` → `/data/` etc. Unanchored,
  `data/` matches at any depth and would silently swallow a `src/<pkg>/data/` source package — green
  locally, `ModuleNotFoundError` in CI, which is exactly how egm-classifier went red at Refactor Step 8.
  **`out/` is the deliberate exception** — every shipped example spec writes a *relative* `out/...`
  path, so running one from `examples/` creates `examples/out/`; anchoring it to `/out/` would leave
  that unignored in every clone. So `out/` matches at any depth, paired with `!src/**/out/` to keep the
  landmine defused.
- **Verify:** `git check-ignore -v` all three directions — a same-named source package (incl.
  `src/<pkg>/out/`) is **no longer** ignored, a top-level output dir **still** is, and a nested
  `examples/out/` **is**; `ruff` + `mypy` run at the pinned versions.
- **Depends on:** none.

#### S1 — Re-pin to the Wave-1 tags ✅ (2–5 h)
- **Change:** `pyproject.toml` → **egm-contracts v0.6.0**, **egm-data v0.6.1**, **egm-features
  v0.2.0** (all three move; egm-data's `.1` is the CL-136 RootModel-repr fix, non-breaking). Open a
  `CHANGELOG.md` `[Unreleased]` section and backfill the post-v0.1.0 commits already on `development`.
  Then fix the breakage egm-data pre-swept for us, so the step ends green: `tests/conftest.py:78`
  (`sim_id` → `simulation_id`), `tests/view_model/test_builder.py:48,58` (asserts a `sim_id` column),
  `tests/view_model/test_artifact_metadata.py:60,77` (asserts `bank_metadata` carries
  `fibrosis_density` / `simulator` — both gone). Not taking the `[catch22]` extra yet; that rides S13.
- **Verify:** `pytest -m "not gui"` green, full suite green on the PR; no test references a removed key.
- **Depends on:** S0. Upstream is **already tagged** — nothing to wait for.

#### S2 — STU6a: view-model against the v2.0 trace keyset ☐ (2–4 h)
- **Change:** the documented metadata-key contract in `view_model/builder.py`. The **exact** shipped
  keyset (CL-109, after synthetic-egm de-duplicated per §12 — narrower than this plan first assumed,
  and **`seed` is gone too**):
  - **per trace:** `simulation_id`, `pair_index`, `patient_id` — plus `snr_db` / `noise_record` /
    `noise_channel` **only when the mixer ran**. A clean bank **omits** them rather than writing NaN:
    absence means it didn't happen, so missing ≠ unknown.
  - **bank-level:** `producer`, `producer_version`, `description`, `trace_duration_ms`, `label_policy`
    (identity only) — five keys, where v1.1 carried 23.

  Resolve `label` through the per-sim `label_policy`; surface the `LabelPolicy` identity; fix
  `view_model/filtering.py`'s `electrode_height` docstring example (a removed field). **`label_fn`
  semantics inverted** (CL-102): under 1.1 omitting it meant *unlabeled*; under 2.0 omitting it takes
  the bank's own labels, and unlabeled means passing a `label_fn` returning `None` — same call,
  opposite result. egm-studio never calls the converter, so this is a fixture-construction note.
- **Verify:** a v2.0 bank builds a view-model with the reduced keyset and a resolvable
  `simulation_id`; a **clean** (unmixed) bank yields no `snr_db` column at all rather than a NaN one;
  the Flow A tests pass. Real v2.0 banks exist to test against —
  `synthetic-egm-pipeline/banks/synthegm_test_0*.classifier.h5` with their `*_theta.synthetic.h5`
  partners — so this needn't rest on hand-built fixtures alone.
- **Depends on:** S1.

#### S3 — STU6b: recursive per-sim provenance render ☐ (2–4 h)
- **Change:** `view_model/artifact_metadata.py`. The premise shifted: the ClassifierBank's
  `bank_metadata` is now **five thin keys** (CL-109), so little is left to render there — the rich
  per-function config lives on the parallel `SyntheticBank`, reached through S4's `simulation_configs()`.
  Replace the flat `_render` `json.dumps` with an indented recursive render and walk each
  `SimulationConfig`'s per-function objects (geometry / cell_model / substrate / activation /
  electrodes / backend / label_policy) as nested blocks with their variant tags. Those fields are typed
  **contracts models**, not dicts — `SimulationConfig` passes them through as-is — so the renderer walks
  Pydantic models (`model_dump()`), which is what makes this more than reformatting.
- **Verify:** "Show metadata" on a two-simulation v2.0 fixture names every per-function object and
  its variant, one per line; a ClassifierBank with no paired synthetic bank renders as before.
- **Depends on:** S2 + S4.

#### S4 — STU6c: θ columns off egm-data's paired `SimulationConfig` ☐ (2–4 h) ♻ *reinstated, then re-scoped*
- **Change:** consume the join **egm-data already ships** (`banks/joins.py`, in v0.6.0):
  `simulation_configs(synthetic_bank) -> {simulation_id: SimulationConfig}` and
  `join_traces_with_simulations(classifier_bank, synthetic_bank) -> [TraceWithSimulation]`. Project the
  tuned knobs off the typed `SimulationConfig` into θ columns on the view-model. Reading θ off a typed
  object, **not** resolving a `TunedParam.path` grammar (CL-024 §2 keeps that out of v0.6.0). Plus a
  thin `SyntheticBank` reader for the operator's swap-to-synthetic signal source, and the config passed
  through to S3. **One θ frame, two selectable signal sources** (`classifier` default / `synthetic`).
  The join raises rather than guessing on all three silent-wrong-answer cases — banks that don't
  correspond, a trace with no `simulation_id`, a trace pointing at an absent simulation — and it is
  **synthetic-only** (an IAFDB bank is rejected, not silently empty). Surface those as clear GUI errors
  rather than letting them arrive as an empty table.
- **Verify:** a swept v2.0 fixture yields one θ column per tuned knob, correctly paired by
  `simulation_id`; both signal sources return the same row count and θ values but different signal
  arrays; a single-simulation bank degenerates to constant θ without special-casing.
- **Depends on:** S1. The join API is **already tagged** — this consumes it rather than waiting on it.
- **Note:** dropped 2026-07-27 (θ-via-`trace_metadata`), reinstated 2026-07-28 (investigation §12),
  re-scoped 2026-07-29 (CL-024 §2 option 1b — egm-data does the join and returns typed config, so the
  θ-spec resolver and the studio-side join both come out). Surviving three reversals on a stable id is
  why it was parked rather than renumbered.

#### S5a — B19: drop the curator provenance sentinel ☐ (1–2 h)
- **Change:** `save/producer.py:37–44` — remove the `UNKNOWN_PRODUCER` / `UNKNOWN_VERSION`
  (`"unknown"` / `"0"`) stamp from `_base` now that P4 makes `produced_by_*` optional; delete both
  constants and their `__all__` entries.
- **Verify:** an indexed producer entry validates with the fields absent; the phase-status view
  doesn't regress on an entry lacking provenance.
- **Depends on:** S1.

#### S5b — B17: relative in-phase paths ☐ (3–6 h)
- **Change:** write manifest `path`s relative to the manifest for in-phase artifacts
  (`save/artifacts.py:authored_path`, `save/figure.py`, `save/observation.py`), and resolve them
  back against the phase dir on read (`loaders/manifest.py:bank_paths_from_phase`,
  `view_model/phase_status.py`, `view_model/dependencies.py`, `view_model/figure_output.py`).
  Out-of-phase pointers stay absolute.
- **Verify:** a phase folder moved to a different parent directory still resolves every in-phase
  artifact; `manifest.json` contains no absolute path for an in-phase entry; ADR-026 cross-scope
  resolution tests stay green.
- **Depends on:** S5a.

#### S5c — B17: copy-into-phase on index + promote ☐ (3–6 h)
- **Change:** *Add to phase* copies the artifact into `phases/phase_1_5/<type>/` instead of
  recording a pointer (**all types, banks included** — settled below), and *Promote to phase*
  (`gui/shell.py:_promote_scratch`) moves rather than re-points; *Remove from phase* deletes the
  in-phase copy symmetrically, leaving any external original untouched. Two mechanics the JSON-only
  path didn't need: **sibling files travel with their artifact** (a noise bank's
  `<stem>_run_record.json`, which S6 still reads as a fallback and the metadata viewer opens), and
  **re-indexing is idempotent** — an artifact already resident in the phase is re-pointed, not
  re-copied.
- **Verify:** index → move the phase folder → every copied artifact still opens; a noise bank
  arrives with its sidecar; re-indexing the same file twice copies once; remove deletes only the
  in-phase copy.
- **Depends on:** S5b.

#### S5d — B17: large-artifact copy UX ☐ (3–6 h)
- **Change:** banks are 100–500 MB, so the copy can't run on the UI thread — move it to a worker
  with progress + cancel (the same coalesced-worker pattern Flow C's resolve uses, ADR-019
  as-built), plus a **free-space pre-check** that refuses with a clear message rather than
  half-copying, and cleanup of a partial file on cancel or failure.
- **Verify:** a large-fixture copy keeps the window responsive and can be cancelled; cancelling
  leaves no partial file and no manifest entry; a simulated no-space condition reports rather than
  corrupts; `git status` in `intracardiac-platform` shows nothing newly tracked after a bank copy
  (the `*.h5` / `*.hdf5` ignore holds).
- **Depends on:** S5c.

#### S6 — B20: noise `bank_id` from the bank ☐ (1–3 h)
- **Change:** `save/producer.py:noise_bank_entry` reads `bank_id` from the `noise_bank` root attr
  instead of the `<stem>_run_record.json` sidecar (sidecar kept as fallback for existing banks); and
  `view_model/noise.py:NoiseBankSegments` gains the `bank_id` its docstring currently says it can't
  carry, so the Noise view stops depending on a caller-supplied id.
- **Verify:** indexing a v1.1 noise bank with no sidecar succeeds; the Noise view header shows the
  id read from the `.h5`.
- **Depends on:** S1.

#### S7 — Wave-1 gate: no-behavior-change regression ☐ (1–2 h)
- **Change:** none — a test asserting a v2.0 fixture yields the same traces, labels, and feature
  values as its v1.1 predecessor.
- **Verify:** the assertion passes; this is egm-studio's half of §7's Wave-1 gate.
- **Depends on:** S2–S3.

### Wave 2 — STU2 (independent; runs while Wave 1 waits on contracts)

#### S8 — `analysis/noise_stats.py` ☐ (2–5 h)
- **Change:** per-segment Welch PSD, dominant frequency, band-power ratios including the 50/60 Hz
  powerline fraction, RMS, kurtosis. Pure functions over arrays — no Qt, no I/O.
- **Verify:** a synthesized 50 Hz tone lands its band-power in the powerline bin; a known-variance
  Gaussian recovers its RMS; a two-tone signal reports the stronger as dominant.
- **Depends on:** none.

#### S9 — Noise outlier detection ☐ (3–6 h)
- **Change:** robust distance from the noise-feature centroid — per-feature MAD-z and Mahalanobis
  over the feature vector — with a flag threshold.
  **Compositional fix (CL-074):** band-power *fractions* sum to 1, so their covariance is singular by
  construction and Mahalanobis is undefined on them. Apply an **Aitchison log-ratio** transform first.
  Note **CLR is not sufficient** — it sums to zero and stays rank-deficient; use **ILR** (an
  orthonormal basis, full rank) or equivalently drop-one **ALR**. Only the compositional block is
  transformed; RMS / kurtosis / dominant frequency are unconstrained and pass through.
- **Verify:** an injected outlier segment is flagged; a homogeneous set flags nothing; the covariance
  of the transformed block is **full rank** (the pre-transform one demonstrably isn't); a zero
  band-power component doesn't produce `-inf` (zero-replacement applied).
- **Depends on:** S8.

#### S10 — Noise-mode read-out ☐ (2–4 h)
- **Change:** `gui/views/noise_exploration.py` — per-segment stats table, PSD plot beside the
  waveform, outlier column + sort, following the existing mode-driven sidebar pattern.
- **Verify:** offscreen screenshot in all three themes; the segment table sorts by each new column.
- **Depends on:** S9.

### Wave 2 — STU3 + B18 + P3 (needs CLF2 / CON3)

#### S11a — Train/test metric series into `TrainingCurve` ☐ (2–4 h)
- **Change:** `loaders/figure_inputs.py:_training_curve` (~L543) reads `EpochRecord.train_metrics`
  alongside `val_metrics`, and the aligned `HeldOutTest.metrics` bundle (B18), emitting them as
  extra series. `charts/inputs.py:TrainingCurve` already holds `loss` / `metric` as
  `{series: values}` dicts, so no dataclass change is needed — only the population.
- **Verify:** a 1.2 fixture run record yields train + val (+ test) metric series; a 1.1 record still
  loads with val only, no exception.
- **Depends on:** S1 + CLF2 emitting train metrics.

#### S11b — Split selector + seed spread in the training view ☐ (3–7 h)
- **Change:** `gui/widgets/training_view.py` + `charts/pyqtgraph/training.py:training_curves_overlay`
  — render the selected split(s) for the metric panel (loss already draws train + val at L63–71),
  with a split selector in the view header. **Seed spread (CL-074 / CL-073):** with multi-seed runs
  landing in egm-classifier, show the across-seed band (median + min/max or ±1 sd) rather than N
  indistinguishable overlaid lines, so a metric difference can be read against run-to-run variance.
- **Verify:** offscreen screenshot with each selector state; a run lacking train metrics disables
  rather than crashes; a multi-seed group renders one band per split, and a single-seed run still
  renders a plain line.
- **Depends on:** S11a.

#### S11c — Split-aware inspection ☐ (1–2 h) ↓ *mostly already shipped*
- **Change:** far smaller than first scoped. Verified against `development`: `split` is already an
  `IDENTITY_COLUMNS` entry populated in `view_model/builder.py:168`, and `predicted_prob` /
  `predicted_class` already arrive via `ml_outcomes.ML_COLUMNS` — so filtering Flow B by split works
  today. CL-037 item 4 confirms the egm-data half of P3 also already ships (the `split` /
  `prediction` columns round-trip through `classifier_bank_io`). What's left is a regression test
  pinning that behaviour across the v0.6.0 re-pin, plus any label/enum drift in the new bank.
- **Verify:** an evaluated v2.0 fixture filters to train/val/test; a bank without the columns behaves
  as today.
- **Depends on:** S11a.

#### S11d — Saturation metrics in the Flow B output view ☐ (2–4 h) *(new, CL-074)*
- **Change:** the §8.5 saturation read-out — **mean predictive entropy** (threshold-free, so it
  doesn't inherit an arbitrary cut) plus an **ECDF of P(fibrotic)** with **≥2 marked cuts** — on the
  IAFDB `upred_` bank.
  **Homed in Flow B, not STU3** (CL-074 offered either): STU3 is the *training-run* viewer, whereas
  saturation is a property of a **prediction distribution on an unlabeled bank** — which is precisely
  what `charts/pyqtgraph/output_distribution.py` and Flow B's qualitative (unlabeled) mode already
  render. This extends an existing surface instead of adding a stat to a curve view it doesn't belong
  in.
- **Verify:** a synthetic all-0.999 fixture gives near-zero mean entropy and a step-shaped ECDF; a
  spread fixture gives visibly higher entropy; the panel appears for unlabeled banks (no labels
  required).
- **Depends on:** S11a.

#### S11e — Paired cross-arm comparison ☐ (2–5 h) *(new, CL-080)*
- **Change:** the "does arm A beat arm B once seed noise is accounted for" read-out, over the §8.4
  best-epoch criteria and the §8.5 architecture panel. **Paired by seed** — pairing is what removes
  seed-level variance and is the whole reason this is tractable at k≈3–5. Reports the per-seed
  differences, their mean, and an interval; egm-classifier owns the per-arm spread (CLF6), this owns
  the A-vs-B comparison because it spans *different* training runs.
- **Three things it must not get wrong** (see CL-082): pairing is only valid if the two arms **share a
  seed set** — verify against the run records' seed lists and refuse to pair otherwise; at k≈3–5 the
  honest output is an **effect size + interval + the raw per-seed numbers**, never a p-value dressed as
  significance; and the panel shows the **full pairwise matrix**, not just the winning pair, so the
  multiplicity is visible rather than hidden.
- **Verify:** a fixture where A and B differ by a constant offset recovers that offset exactly with
  zero spread; mismatched seed sets refuse to pair (and say why); a fixture with within-arm spread
  larger than the between-arm difference reports an interval spanning zero.
- **Depends on:** S11b + CLF6's seed lists.

#### S12 — `training-curve` recipe parity ☐ (1–3 h)
- **Change:** the matplotlib `training-curve` recipe gains the train/test series + a split knob in
  its curated spec fields, so the paper figure matches the GUI.
- **Verify:** `pytest-mpl` snapshot; `egm-studio-render` on an updated example spec.
- **Depends on:** S11b.

### Wave 2 — STU5 (needs FEA1 + STU6 + S17)

#### S13 — catch22 subset in the view-model ☐ (2–4 h)
- **Change:** extend `view_model/builder.py:FEATURE_COLUMNS` with the ~14-feature usable-now catch22
  subset (skip self-affine scaling; defer the linear-autocorrelation family per design B.3). Extend
  `feature_units` for any that carry one. Take the **`[catch22]` extra** on `myocard-egm-features`
  (it's optional — S1 deliberately didn't).
  **The subset is ours to encode (CL-142).** egm-features shipped and then *removed* a
  `catch22_usable_now` set: a curated judgement for one study at one window length doesn't belong in a
  general library, and per-feature `min_length` was rejected rather than deferred because there are no
  defensible thresholds (`dfa` degrades continuously — it doesn't work at 192 and fail at 191). So we
  build it with `sets.resolve([...])`, which validates every name and returns canonical order, and read
  `egm-features/docs/theory.md` §4.1.3 — the per-family reliability analysis at **T = 192**, the
  measured spread inflation, and the `whiten_timescale` degeneracy — to choose. The knowledge stayed in
  the library; only the decision moved to us. Bonus: the §8.2 screening's outcome then lands in our
  config rather than needing an egm-features release.
  **Ask only for what we want (CL-141):** `catch22_all` is a per-feature loop, not a fused kernel, so
  there is no bulk discount to give up — the usable-now 14 cost **0.44x** the full 22, one feature
  ~35x less. Pass `features=` explicitly; don't extract everything and slice.
  **Sample-rate guard (CL-015):** much of catch22 is indexed in *samples / lags*, not Hz, and nothing
  in the call signature carries `fs_hz` — a rate mismatch between the synthetic and IAFDB corpora
  raises no error and silently corrupts the STU5 / STU4 distance. Both sides are 1 kHz today, so this
  is latent; assert it explicitly rather than trusting it, since `whiten_timescale` and
  `embedding_dist` are in the usable-now 14.
- **Verify:** the ADR-028 tiered cache invalidates on the egm-features math-version bump; extraction
  stays chunked + cancellable (`_extract_features`); the distribution grid still renders; **comparing
  two corpora at different sample rates raises** rather than returning a number.
- **Depends on:** S2. FEA1 shipped as **egm-features v0.2.0** — already tagged.

#### S14a — Joint-distance comparison in `analysis/` ☐ (1–3 h)
- **Change:** a thin `analysis/` entry that takes two view-model frames + a feature list and returns
  the joint scalar (MMD or energy, via S17) beside the existing per-feature
  `aggregation.feature_distances` map — one call for the whole comparison read-out.
  **`activation_position` is excluded from the matched realism set by default** (CL-068): research
  settled that it is an **augmentation axis, not a realism axis** — we vary it deliberately to teach
  position-invariance, so it has no business in a realism metric. Exclusion is the correct default, not
  a hedge.
  **Leave-one-out, re-purposed:** still report the distance with and without it, but now as a
  **positive confirmation** that the coordinate carries no realism signal — no action pends on the
  result. (The earlier "non-zero by design" reading only applies in the fallback world where it stays
  in.)
- **Verify:** identical frames score ≈ 0; a knob-shifted frame scores higher; the per-feature map
  matches a direct `feature_distances` call; the default matched set **does not contain**
  `activation_position`; the with/without pair is reported.
- **Depends on:** S13 + S17.

#### S14b — Sim↔IAFDB comparison view ☐ (3–8 h)
- **Also (CL-053 + CL-062 + CL-068):** read the per-trace `activation_position` off **both** typed
  banks — the `IafdbBank` (a second loader alongside S4's, cheap only because S4 establishes the
  pattern) and the `SyntheticBank` (already loaded for θ, so ~free). Deliberately **not** via the
  ClassifierBank on either side; position is provenance and the ClassifierBank stays source-agnostic.
  Its uses are **provenance, faceting, the leave-one-out, and an optional detector-consistency
  diagnostic** ("does the detector place activations consistently across corpora?") — the last is a
  **separate, optional panel, not part of the realism number**, which is the reframe CL-068 makes
  relative to CL-053's original "compare the position distributions" wording.
- **The Wave-1 window is why the symmetric guard survives.** CL-062 adds the synthetic field
  *absent in Wave 1, populated by SEP2 in Wave 2*. So there is a real window where IAFDB carries a
  stored value and synthetic does not. Don't delete the fallback on the strength of "both sides store
  it now" — during Wave 1 both sides must still drop to computed.
- **Collision resolved (Daniel, 2026-07-29): one column, stored wins.** `activation_position` stays a
  single column. If the bank carries it, use that value; only compute it via egm-features when absent.
  A user-triggered recompute override is **deferred** — added only if preferring the stored value
  causes trouble. So no contract rename is needed, and no namespacing.
- **Two guards this needs** (see CL-055): (a) the preference is applied **symmetrically across the two
  corpora** — if either side lacks a stored value, *both* fall back to computed, because a
  stored-vs-computed comparison is not a comparison; (b) the column records **which provenance it
  came from**, so a figure caption and the T4 feature set can tell a set parameter from a measured one.
- **Where it counts — settled by research, CL-067/CL-068:** `activation_position` is an
  **augmentation axis, not a realism axis**, so it is **out of the STU5 matched realism distance
  *and* the STU4 calibration objective**, not merely out of the optimiser. This **supersedes** the
  earlier "keep it in the comparison and track the risk" position (CL-058). It stays fully available
  for provenance, faceting, the leave-one-out confirmation, and the optional detector-consistency
  diagnostic. S18's screening exclusion is unchanged and now belt-and-suspenders — screening would
  auto-drop it anyway, since it responds to no θ. SEP2's `𝒫_synth ⊇ 𝒫_iafdb` also stays: that range
  exists for T1 augmentation, a different purpose.
- **Change:** the success-criterion-#2 panel — joint scalar + per-feature KS / 1-D Wasserstein table
  + the before/after framing study §8.3 needs, over two loaded sources. Carries the `signal_source`
  selector; the default (ClassifierBank both sides) is the like-for-like comparison, and the panel
  labels which source produced the synthetic side so a swapped run isn't mistaken for the default.
- **Verify:** offscreen screenshot; the panel reads correctly with the two banks swapped; switching
  signal source relabels and re-scores without touching θ.
- **Depends on:** S14a.

### Wave 2 — STU1 (needs SEP11's design sweep + STU6)

#### S15 — Feature-vs-θ scatter ☐ (2–5 h)
- **Change:** widen the axis-combo source in `gui/widgets/feature_scatter.py` (which today fills
  from the feature columns) and `loaders/feature_group.py:scatter_series_by_source` to feature ∪ θ
  columns, θ coming from **S4's SyntheticBank view-model**. The scatter widget, decimation, and
  click-to-select already exist.
- **Verify:** offscreen screenshot on a swept fixture; θ axes offered only when a synthetic bank with
  a θ-spec is loaded; axis persistence across a filter re-apply still holds.
- **Depends on:** S4 + SEP11's design-sweep bank.

### Wave 2 — STU4 · A: foundations (+ the shared extractor; prerequisites of STU7)

#### S16 — `parameter_estimator/ports.py` + standardisation ☐ (2–4 h)
- **Change:** create the sub-package; the four Protocols (`Generator`, `FeatureExtractor`,
  `RealDataSource`, `Distance`); the `(N, F)` DataFrame convention; pooled per-coordinate z-scoring
  (design §3.1). Plus the ADR-030 import-boundary test.
- **Verify:** a fake `Generator` satisfies the Protocol under mypy; the boundary test fails if a Qt
  import is added under `parameter_estimator/`.
- **Depends on:** none. **Blocks STU7.**

#### S17 — `distances.py` — MMD + energy, with uncertainty ☐ (3–7 h)
- **Change:** MMD² unbiased estimator over an RBF kernel (median-heuristic bandwidth); energy
  distance via `dcor`. Both return `(scalar, per_feature)`, the per-feature half delegating to
  `analysis/distributions`.
  **Uncertainty (CL-074a):** every `d_m` also returns an **error bar** — bootstrap over the two
  samples, or the closed-form MMD variance. This is not optional polish: the pre-filtered IAFDB
  sub-banks are small, so `d_m` is a noisy two-sample estimate, and without a spread there is no way
  to tell a real minimum from a lucky draw.
- **Verify:** identical samples ≈ 0 within estimator noise; monotone in a mean shift and a variance
  shift; MMD and energy rank a fixture family identically; **the error bar shrinks as ~N^(-1/2)** on
  a fixture with growing sample size.
- **Depends on:** S16. **Blocks STU5 (S14a).**

#### S20 — `adapters/feature_extractor.py` ☐ (2–4 h)
- **Change:** the shared extractor both sides use, wrapping `bundle.extract_all` with the selectable
  set (`egm_features` | `egm_features+catch22`). Thin — the feature functions stay in egm-features.
- **Verify:** synthetic and IAFDB inputs produce identically-ordered columns.
- **Depends on:** S16 + S13. **Blocks STU7.** *(Scored under STU4 · C; scheduled with · A.)*

### Wave 2 — STU7: screening (own §3 issue as of 2026-07-28)

Consumes the **OAT run** of SEP11's sweep code; its output sets SEP11's design-sweep θ-spec
membership and STU4's optimiser feature set.

#### S18 — `screening.py` ☐ (3–8 h)
- **Change:** the responsiveness matrix over an OAT design, plus the two flags: a feature responding
  to no knob (drop from the optimiser set) and
  a knob moving no feature (not identifiable). **`activation_position` is excluded from the candidate
  pool**, reason recorded in code: screening is what *selects* the optimiser feature set, and a
  coordinate we set from `𝒫` would rank high against its own generating knob and crowd out real
  features. Same decision as excluding it from the optimiser (CL-056), applied where it sticks.
  **Estimator corrections (CL-074):** ρ's denominator is the **pooled within-level (residual) sd**,
  not the marginal sd — the marginal one contains the between-level variance the numerator is
  measuring, so it systematically *shrinks* ρ for exactly the features that respond most. And the
  design reads **≥3 levels with a rank correlation** (Spearman), not a 2-point hi/lo contrast, which
  returns ~0 for a genuinely responsive but **non-monotone** feature — a false negative that would
  silently delete a good comparison coordinate. Plus an explicit "responds" threshold rather than an
  eyeballed cut.
- **Verify:** a fixture where feature A responds only to knob 1 recovers exactly that structure; a
  constant feature is flagged; a zero-variance knob doesn't divide by zero; **a constructed
  non-monotone (U-shaped) responder is detected** — the case a 2-level contrast misses;
  `activation_position` never reaches the emitted optimiser set even when its ρ is the highest. *(Per CL-068
  this is belt-and-suspenders — screening auto-drops it, since it responds to no θ — but the explicit
  exclusion documents the intent and costs nothing.)*
- **Depends on:** S16 + S20 + SEP11's OAT banks.

#### S19 — Screening read-out + study artifact ☐ (2–5 h)
- **Change:** the feature×knob matrix as a chart plus the human-readable artifact study §8.2
  consumes.
- **Verify:** the artifact round-trips; the chart renders headless.
- **Depends on:** S18.

### Wave 2 — STU4 · C: adapters (remainder)

#### S21 — `adapters/iafdb_source.py` ☐ (2–4 h)
- **Change:** reference features + the Decision-5 pre-filter (patient / placement / rhythm);
  default = all IAFDB.
- **Verify:** the pre-filter narrows as specified; default returns the full set.
- **Depends on:** S20.

#### S22 — `adapters/bank_generator.py` ☐ (2–6 h)
- **Change:** `BankBackedGenerator` — filter the swept bank to the cell for θ (θ from **S4's
  SyntheticBank view-model**), featurise lazily, return `(N, F)`. Honours `signal_source`
  (ClassifierBank default), so a calibration run is explicit about which representation it matched.
- **Verify:** `generate(θ)` returns the right cell and shape; an unswept θ raises a clear error
  rather than snapping to a neighbour silently.
- **Depends on:** S20 + S4.

### Wave 2 — STU4 · D: core estimation

#### S23 — `emulator.py` — GP surrogate ☐ (5–11 h)
- **Change:** `GaussianProcessRegressor` over {(θ_m, d_m)}; posterior mean **and** sd at arbitrary θ;
  the active-learning hook returning high-uncertainty candidates near the minimum / boundary.
  **Nugget (CL-074a):** fit with a noise term (`alpha` / `WhiteKernel`) sized from S17's per-`d_m`
  error bars, so the GP **absorbs** observation noise instead of interpolating it. Without it the
  surrogate passes exactly through every noisy `d_m`, and its posterior is confidently wrong in the
  gaps — the failure mode that matters most near the acceptance boundary, which is where the region
  is decided.
  **Validate before it's load-bearing (CL-081):** leave-one-out of `d̂` against held-out `d_m`, plus a
  check that the fitted nugget matches the bootstrap two-sample noise scale from S17. A misfit GP
  doesn't fail loudly — it **launders noise into smooth bias**, which then propagates into the region
  and the marginals looking perfectly plausible.
- **Verify:** recovers a known smooth analytic function within tolerance; sd grows away from the
  design points; **on data with injected noise the fit does not interpolate** (residuals ≈ the
  injected scale, and the posterior sd covers it); LOO error and fitted nugget both report, and a
  deliberately mis-specified kernel is caught by them.
- **Depends on:** S17.

#### S24 — `region.py` — ε-acceptance + θ sampling ☐ (4–10 h)
- **Change:** rejection-ABC acceptance R_ε = {θ : d(θ) ≤ ε}, ABC-likelihood posterior weighting,
  per-knob marginals, and sampling θ from the region.
  **Acceptance runs on the smoothed surface, not raw `d_m`** — a consequence of S17/S23's noise
  handling worth stating explicitly: thresholding noisy per-cell estimates admits cells that got a
  lucky draw and rejects ones that didn't, and the error is worst exactly at the boundary where the
  region is defined. Accept on the GP posterior mean, and expose the boundary's uncertainty rather
  than drawing it as a hard line.
  **Soft region (CL-081, research-endorsed — the BOLFI construction):** define the region by the
  **acceptance probability** Pr[`d̂`(θ) ≤ ε] using the GP's `ŝ`(θ), with the point region (posterior
  mean ≤ ε) as its hard-cut special case. That carries emulator uncertainty into both the region *and*
  the identifiability marginals, instead of a hard mean cut that reports a confident boundary the data
  doesn't support. **ε** is set by an acceptance-rate quantile, not a magic number.
- **Verify:** on a landscape with a known sublevel set the accepted set matches analytically; a knob
  absent from the landscape gets a flat marginal; **injecting noise into `d_m` does not move the
  accepted set materially** (it would, under raw thresholding — that contrast is the test).
- **Depends on:** S23.

#### S25 — `orchestrator.py` — the use case ☐ (3–6 h)
- **Change:** score design → fit emulator → estimate region, logging d at every swept cell /
  iteration for the convergence curve. Imports only `ports.py`.
- **Verify:** end-to-end against the S16 fake `Generator` — no bank, no files, no Qt. This test is
  the hexagonal payoff and the guard on the extraction boundary.
- **Depends on:** S24.

#### S26 — Config + headless run entry ☐ (2–6 h)
- **Change:** one YAML per run with `type:` discriminators (`feature_set` / `distance` /
  `real_source` + `pre_filter` / `generator` / `sweep` / `search`) — the `feature_set` **excludes
  `activation_position` from the calibration objective** (CL-068) — plus **`signal_source:`**
  (`classifier` default / `synthetic`), matching synthetic's strategy-config idiom; a console entry
  point. Parsed into typed models, not dicts.
- **Verify:** `--help`; a fixture end-to-end run producing a region; the emitted artifact records
  which signal source it calibrated against.
- **Depends on:** S25 + S22 + S21.

#### S27 — Human-readable output artifact ☐ (2–4 h)
- **Change:** the realistic region + sampled-θ table as a self-describing CSV/JSON pair (design §4.4
  — deliberately not a cross-repo contract in 1.5).
- **Verify:** the file names its knobs, bounds, ε, distance, and feature set without reference to
  the run config.
- **Depends on:** S26.

### Wave 2 — STU4 · E: GUI (fifth mode) + paper figures

#### S28 — ADR-029 + ADR-030; mode shell + run-config panel ☐ (4–9 h)
- **Change:** both ADRs into `project/design.md`; the Calibration mode in the header segmented
  control; `gui/views/calibration.py` with the run-config panel — including the `signal_source`
  toggle — driving S26 on a worker thread.
- **Verify:** offscreen screenshots in all three themes; the run doesn't block the UI thread.
- **Depends on:** S26.

#### S29 — Distance landscape + realistic region view ☐ (4–9 h)
- **Change:** the 2-D landscape over swept knobs with the accepted region overlaid, plus per-knob
  identifiability marginals. **Adds (CL-074):** per-cell `d_m` **error bars** surfaced in the view,
  and **pairwise 2-D posterior joints** — not only the 1-D marginals. The Courtemanche degeneracy is a
  **ridge between knobs**, and a ridge is invisible in 1-D marginals: two knobs can each look
  well-constrained while only their *combination* is. The joint view is what shows it.
- **Verify:** offscreen screenshot on a fixture region; a 1-D sweep degrades gracefully; **a fixture
  with a deliberate ridge reads as a ridge in the joint panel while both 1-D marginals look tight** —
  the exact failure the joints exist to catch.
- **Depends on:** S28.

#### S30 — Per-feature diagnostics + convergence view ☐ (2–5 h)
- **Change:** before/after per-feature overlays and the convergence curve of d, reusing the existing
  pyqtgraph feature-distribution twin.
- **Verify:** offscreen screenshot; the before/after pair reads correctly on a fixture.
- **Depends on:** S29.

#### S31 — Five paper recipes + inventory ☐ (6–12 h)
- **Change:** `charts/matplotlib/` recipes for the convergence curve, the before/after per-feature
  overlay, the distance landscape / region, the identifiability marginals, and — added by CL-074 —
  the **2-D pairwise posterior joints**; each self-registering with a loader, an example spec, and a
  snapshot. The convergence and landscape recipes carry the `d_m` error bars. Enumerate them in
  `project/paper_figure_inventory.md` first (design §8.3 names this as a prerequisite sub-task);
  catalogue S19's screening matrix here too if the paper wants it.
- **Verify:** five snapshots; all five render headless.
- **Depends on:** S30.

### Wave 3 — STU8: positional-sensitivity analysis (new §3 issue, CL-074)

T1, not T4. Measures how a trained model's output moves as the activation is shifted within the
window — the direct test of the position-invariance the T1 augmentation work is *for*. Runs over
synthetic-egm's new **SEP13 probe bank** (a sweep of controlled offsets), so it can't start until
that bank exists.

#### S33 — Probe-bank analysis + output-vs-offset ☐ (3–6 h)
- **Change:** load the SEP13 probe bank, run each §8.9 arm's model over it, and plot **output vs
  activation offset** per arm — one curve per arm, offset on x, P(fibrotic) on y. A flat curve is
  position-invariance; a sloped or peaked one localises the shortcut.
- **Verify:** a synthetic fixture whose "model" is a pure function of offset reproduces that function;
  a constant-output fixture gives a flat line; arms with differing sensitivity are visually separable.
- **Depends on:** SEP13's probe bank + S11a's prediction plumbing.

#### S34 — Cross-eval read-out ☐ (2–5 h)
- **Change:** the cross-evaluation table — each arm's model against each arm's probe set — so
  train-position ↔ test-position interactions are visible rather than only the diagonal.
- **Verify:** the diagonal reproduces S33's per-arm numbers; an asymmetric fixture reads asymmetric
  (the table isn't accidentally symmetrised).
- **Depends on:** S33.

### Phase exit

#### S32 — Docs + phase exit ☐ (3–7 h)
- **Change:** `project/architecture.md` (the `parameter_estimator/` module map, the extraction
  boundary, the fifth mode, the two new deps), `docs/theory.md` (how to read a distance landscape, a
  marginal, a convergence curve — cross-linked to egm-classifier for the derivations),
  `docs/usage.md` (Calibration walkthrough + regenerated screenshots), `CHANGELOG.md`, `roadmap.md`.
- **Verify:** the full `intracardiac-platform/project/pr_checklist.md` run passes.
- **Depends on:** all prior steps.

## Estimates + complexity

The ledger is still **empty** (header only), so per the rubric's cold-start rule these remain
**estimates by analogy with wide ranges**, not `points × rate`. Anchors: S = `noise_bank` `bank_id`;
M = CLF2 train-split metrics; L = SEP12 v2.0 migration; **XL = STU4 · D core** (re-pointed by the
project-lead 2026-07-28).

| Issue / group | Steps | Cx | Estimate (active) |
|---|---|---|---|
| STU6 | S0–S4, S7 | M (3) | 10–21 h |
| B17 · B19 | S5a–S5d | **L (5)** ↑ | 10–20 h |
| B20 | S6 | XS (1) | 1–3 h |
| STU2 | S8–S10 | M (3) | 7–15 h |
| STU3 (+B18, P3) | S11a–S11e, S12 | **L (5)** | 11–25 h |
| STU5 | S13, S14a–b | M (3) | 6–15 h |
| STU1 | S15 | S (2) | 2–5 h |
| STU7 | S18–S19 | M (3) | 5–13 h |
| STU4 · A foundations | S16–S17 | ↓ | 5–11 h |
| STU4 · C adapters | S20–S22 | ↓ | 6–14 h |
| STU4 · D estimation core (incl. · A + · C) | S23–S27 | **XL (8)** *(the re-pointed anchor)* | 16–37 h |
| STU4 · E GUI + figures | S28–S31 | L (5) | 16–35 h |
| **STU4 composite** | | **13** | **43–97 h** |
| **STU8** *(new, CL-074)* | S33–S34 | M (3) | 5–11 h |
| Docs + phase exit | S32 | M (3) | 3–7 h |
| **Repo total** | | **44** | **103–232 h** |

*The re-pointed **XL = STU4's estimation core** covers · A and · C too — ports, distances, and the
adapters are the core's scaffolding, not independently-sized work — which is what makes STU4's
composite **13** (XL 8 + L 5) rather than the 16 an A/C/D/E sum would give. Hours stay split across
all four parts for planning; only the scoring merges.*

### What the second pass changed

Recorded because it's exactly the calibration signal the ledger exists to capture.

- **Estimate rose 62–145 h → 78–174 h (+26 % / +20 %)** without any scope being added. Decomposing
  three chunky steps into eleven surfaced work the blob estimates had absorbed — the classic
  decomposition effect. Worth a ledger note at cleanup: *first-pass issue-level estimates in this
  repo ran ~20–25 % under the step-level ones.*
- **Then 78–174 h → 81–180 h** when the B17 scope came back as *copy everything, banks included*
  (S5d added). Not a decomposition effect — a scope answer. Logged separately so the two causes stay
  distinguishable in the ledger.
- **Points net 37 → 41.** Three moves: **B17 · B19 M (3) → L (5)**, **STU4 16 → 13** once the
  re-pointed XL anchor was applied correctly (below), and **STU6 M (3) → L (5)** when the θ reversal
  turned it from a keyset migration into a migration *plus* a new read path. The B17 move, after reading
  `save/` — it touches `producer.py`, `artifacts.py`, `figure.py`, `observation.py`,
  `loaders/manifest.py`, three `view_model/` resolvers, and the ADR-026 scratch/promote path, with a
  move-the-folder verification. That's L surface, not M.
- **Two first-pass steps got smaller on inspection.** S2 (view-model keyset) — `builder.py` flattens
  metadata generically, so no logic change. S11a (metric series) — `TrainingCurve.loss` / `.metric`
  are already `{series: values}` dicts, so no dataclass change.

## B17 storage scope — settled

**Copy _all_ artifact types into the phase folder, banks included** (Daniel, 2026-07-28). The
authoritative layout is **Phase-1.5 design §8** — cite that, not
`cross_artifact_linkage_design.md` §6, whose local-first text is now carried under a
⚠-Superseded-for-1.5 banner pointing at §8.

**Git policy — HDF5 is never committed.** `*.h5` / `*.hdf5` are gitignored repo-wide in
`intracardiac-platform` (`.gitignore:62–63`). So a phase folder is self-contained **on disk**, not in
git: what's committed is the manifest (small JSON) plus provenance — the `generation_params` θ-spec,
seeds, and code — which regenerate the banks; tagged releases attach them as assets.

Two consequences for S5c / S5d:

- **Copying must leave the platform repo git-clean.** A copy that lands a tracked file would defeat
  the policy, so the verification includes `git status` in `intracardiac-platform` showing nothing
  new tracked after an index.
- **A missing in-phase bank is recoverable, not fatal.** Since banks are regenerable from provenance
  or pullable from a Release, a manifest entry whose HDF5 is absent on a fresh clone should read as
  *unresolved* (the existing amber ADR-026 state) rather than erroring — the phase tree already has
  that vocabulary.

**What the decision cost.** Copying HDF5 rather than pointing at it is a different job from copying
JSON — hundreds of MB per artifact — so the copy moves off the UI thread with progress + cancel,
gains a free-space pre-check, cleans up partial files, carries sibling records along, and skips
artifacts already resident. That is **S5d** (+3–6 h; B17 · B19 7–14 h → 10–20 h).

## T4 signal source — settled (Daniel, 2026-07-28)

**Default = the ClassifierBank's traces; the operator can swap to the `synthetic_bank`'s traces.**
A selectable `signal_source` threaded through the T4 path, defaulting to what the model and the
IAFDB side actually see, with the generation-output signals available when wanted.

Why this is the right default: §12 records that the parallel banks store each signal **twice** and
that *"the copies aren't byte-identical (generation-output + noise provenance vs the post-processing
ML input)"*. T4's goal is making the synthetic feature space match IAFDB **as the pipeline delivers
it** — calibrating on pre-post-processing signals would optimise a distribution nothing downstream
consumes. Defaulting to the ClassifierBank also makes STU5's sim↔IAFDB comparison like-for-like by
construction (both sides post-processed), so the caveat I flagged last turn disappears in the default
configuration and applies only when the operator deliberately swaps.

**Threaded through five steps:** S4 (the view-model supplies signals from either bank against one θ
frame), S14b (source selector on the comparison panel), S22 (`BankBackedGenerator` honours it), S26
(`signal_source:` config key), S28 (the GUI toggle). Roughly +1 h at the top of each range; no
complexity band moves.

**A free diagnostic falls out.** With both sources selectable over the *same* θ, the delta between
them is a measurable quantity — how much the post-processing stage shifts the synthetic feature
distribution. That isolates post-processing from generation as a contributor to the sim-to-real gap,
which is a cheap observation for the paper and needs no extra code beyond the toggle. Noted, not
scoped.

### Consequence for DAT1 — the `simulation_id` join is load-bearing in 1.5

The default path needs features from the **ClassifierBank** joined to θ from the **`synthetic_bank`**
by `simulation_id`. That is the cross-artifact join §12 assigns to **egm-data** — *"egm-data owns the
cross-artifact read/join (reads both banks → a typed joined view)"* — and defers alongside the
FN-vs-θ view. But T4 now needs it this phase.

It is a strictly smaller ask than FN-vs-θ: **bank ⋈ bank, no predictions involved**. Two ways to
close it, project-lead's call:

1. **DAT1 ships the joined view in 1.5** (consistent with the stated ownership) — T4 consumes it; the
   FN-vs-θ view later adds the predictions leg on top.
2. **egm-studio does the T4 join locally** (a merge on `simulation_id` across the two read paths S4
   already opens) and egm-data still owns the FN-vs-θ one — faster, but it splits ownership of the
   same join across two repos, which is the kind of thing the charter exists to prevent.

I'd take (1). Flagging because it changes DAT1's scope, and S4/S22 are written assuming the join is
available from egm-data.

## Also — answering O1 from the investigation

§10 lists **O1** as the pivot and addresses it to egm-studio: *does STU4's bank-backed generator need
the full per-sim typed config, or only θ + signal?* From `parameter_estimator_design.md` §2 / §4.2:
the emulator maps **θ → distance** and `BankBackedGenerator` filters to a cell and featurises, so the
optimiser proper needs **θ + signal only**. The typed config earns its place elsewhere — faceting a
calibration by a *categorical* variant (per activation type, per substrate model) rather than by a
continuous knob, and provenance display (S3). Since the settled shape has T4 reading the
`SyntheticBank` anyway, both come for free; O1 no longer forces anything.

## Follow-up for §7

**A thin slice of STU4 precedes STU7.** STU4-depends-on-STU7 is right for the bulk, but
`screening.py` can't be written without `ports.py` (S16) and the shared `FeatureExtractor` (S20),
both scored under STU4. Real order: **S16 + S17 + S20 → STU7 (S18–S19) → STU4 · C remainder → · D →
· E**. Either §7 schedules STU4 · A (plus S20) as its own early slot, or those steps get re-badged
onto STU7 — which would move STU7 from 3 pts to ~6 and drop STU4 correspondingly. This plan assumes
the first: scores stay with STU4, steps scheduled early, marked **Blocks STU7**.

## Escalations — closed 2026-07-28

Sources for all four: design §3 (DAT1 / STU6 / STU1 / STU4 / STU7), §6 (studio row + composite
note), §7 Wave 1 (B17), §8.2, and `estimate_vs_actual_tracking.md` §8.

| # | Raised | Ruling | Applied |
|---|---|---|---|
| 1 | Who joins per-sim config → per-trace θ? | ~~(a) egm-data's converter; θ in `trace_metadata`~~ → **reversed 2026-07-28 to (b)**: θ stays off the ClassifierBank; egm-data exposes a typed `SyntheticBank` and T4 views read θ from it (investigation §12) | **S4 reinstated** as the SyntheticBank read path; S3 / S15 / S22 source θ from it; STU6 M (3) → L (5) |
| 2 | Screening dependency circular | **STU7** — own issue (`FEA1·SEP11·STU6`); STU4 ← `…·STU7`. SEP11 stays single (sweep *code*, run twice as §8 data-gen) | STU4 · B → STU7 (S18–S19), own scope / estimate / effort rows |
| 3 | B17 wave placement | Pinned to **Wave 1** | S5a–S5c annotated |
| 4 | STU4 complexity anchor | XL anchor → **STU4's estimation core**; STU4 carries a **≈13-pt** non-anchor composite; this plan's five-part breakdown is the record | Estimates table re-pointed: core = XL (8) incl. · A + · C, · E = L (5) → **13** |

**On the 16-vs-13 I flagged: mine was the error, now fixed.** I had labelled STU4 · D "*the XL
anchor*" while scoring it **L (5)** — internally inconsistent, since the rubric's XL is 8. Applying
the re-pointed anchor properly (core = XL 8, absorbing the · A foundations and · C adapters it rests
on, plus · E at L 5) gives exactly the **13** the project-lead quoted. Closed, not carried forward.

**B17 / B19 tagging.** The project-lead corrected a mis-tag in design §4 — **B17** is the
phase-storage work (this repo), **B19** is the egm-contracts `produced_by`-optional change. This plan
already split them that way: **S5a** is B19's studio-side consumption (drop the `"unknown"` / `"0"`
sentinel), **S5b–S5d** are B17. No change needed; noted so the two records agree.

## Effort tracking

> **Not tracked for Phase 1.5** (Daniel, 2026-07-29). Flow-down tracking, organization, and effort
> tracking were missed **phase-wide** — not just in this repo — and a methodology for future phases
> will be worked out by Daniel + the project-lead rather than retrofitted onto 1.5. **No `Actual`
> figures will be produced here for this phase, and none should be invented.**
>
> The marker mechanism in
> `intracardiac-platform/project/investigations/estimate_vs_actual_tracking.md` §7 was never started —
> no `start` / `break` / `stop` markers were spoken — so there is no measured span to roll up.
> Reconstructing one from file timestamps would produce a *felt* number wearing a measured number's
> clothes, which is the exact failure mode the method exists to prevent; it would also become the
> ledger's **first** egm-studio data point and bias every rate later derived from it.
>
> **Consequences to carry forward:**
>
> - **§6's `Actual` column stays empty for egm-studio** and `estimation_ledger.csv` gets no rows from
>   this repo for 1.5 — so the phase yields **no velocity data**. The estimates below remain
>   cold-start-by-analogy forecasts that cannot be calibrated against outturn.
> - **The cleanup gate is satisfied vacuously.** `phase_process.md` Stage 4 deletes this plan *"only
>   after its Effort section is rolled up"* — there is nothing to roll up, so don't block the deletion
>   waiting for it.
> - **Keep the estimates anyway.** They record what was predicted; if effort is ever captured
>   retrospectively for some issues, they become a partial comparison.

### Estimates by issue — no actuals, see above

| Issue | Task-type | Estimate | Active | Elapsed | Sessions |
|---|---|---|---|---|---|
| STU6 | schema-migration | 10–21 h | | | |
| B17 · B19 | feature | 10–20 h | | | |
| B20 | schema-migration | 1–3 h | | | |
| STU2 | feature | 7–15 h | | | |
| STU3 | GUI | 11–25 h | | | |
| STU5 | feature | 6–15 h | | | |
| STU1 | GUI | 2–5 h | | | |
| STU7 | feature | 5–13 h | | | |
| STU4 · A · C · D · E | feature / GUI | 43–97 h | | | |
| STU8 | feature | 5–11 h | | | |
| Docs | docs | 3–7 h | | | |
| **Repo total** | | **103–232 h** | | | |

## Coordination-log items applied

Read from `intracardiac-platform/phases/phase_1_5/coordination_log.md` on 2026-07-29 (the log grew
from 6 entries to 38 while this plan was being written).

| Entry | Ruling | Applied here |
|---|---|---|
| CL-024 §1 | Pin CI `ruff==0.15.17` fleet-wide; **don't** run the 0.16 reformat | `.github/workflows/ci.yml` pinned (matches `.pre-commit-config.yaml` rev) — a standalone `[Chore]`, not a plan step |
| CL-024 §2 | T4 join → **egm-data, option 1b**: typed per-sim `SimulationConfig` paired on `simulation_id`; **no `TunedParam.path` grammar in v0.6.0** | **S4 re-scoped** — no θ-spec resolver, no studio-side join; STU6 **L (5) → M (3)**, 9–20 h → 8–17 h |
| CL-024 §3 | Producer renames `sim_id` → `simulation_id` at SEP12; egm-studio flips fixtures | Folded into S2 |
| CL-024 §4 | `T` ≡ 0 (mod 64 samples) → **192 ms at 1 kHz**; synthetic + IAFDB share a sample rate | Noted below; the rate constraint became a **guard** in S13 |
| CL-024 §5b | A repo chat's flow-down/planning session counts toward its issues' `Actual` | **Not applied — effort tracking was missed phase-wide for 1.5** (Daniel, 2026-07-29). See [Effort tracking](#effort-tracking). |
| CL-015 | catch22 lag features are sample-indexed; a rate mismatch fails **silently** | S13 asserts a shared rate rather than trusting it |
| CL-037 §4 | P3's egm-data half already ships (`split` / `prediction` round-trip) | **S11c shrunk** to a regression test — verified `split` is already in the frame |
| CL-038 | Converter `label_fn` demotes to an optional override; omit it on re-pin | **No-op here** — egm-studio never calls the converter; noted in S2 for fixtures. Replied as CL-039 |
| CL-053 · CL-062 | Per-trace `activation_position` on `iafdb_bank` 1.3 + `synthetic_bank` 2.0; read off the typed banks, **never** via the ClassifierBank | S14b reads both; symmetric fallback retained for the Wave-1 window where synthetic is absent |
| **CL-068** | `activation_position` is an **augmentation axis, not a realism axis** → **out of the STU5 realism distance *and* the STU4 objective**, not just the optimiser | **Supersedes CL-058's "keep it and track it."** S14a excludes it by default and re-purposes the leave-one-out as confirmation; S14b reframes the position comparison as an optional detector-consistency panel; S26's `feature_set` excludes it; S18 unchanged (belt-and-suspenders) |

**`T` = 192 ms at 1 kHz** is now a fixed input to this repo, not an open variable: it sets the trace
length the T4 comparison and the estimator's feature extraction operate on.

## Notes / decisions log

- 2026-08-07 — **S1's re-pin broke 13 tests, not the 3 egm-data pre-swept.** Three classes, all
  mine to have caught: (a) six banks whose id role contradicted their content — `_feature_bank`
  builds unlabeled/unpredicted banks, which are **`ptbank_`**, but they carried `tbank_` / `upred_`
  ids used as readability hints; (b) four `TrainingRunRecord` fixtures still at `schema_version`
  1.1, which CON3 bumped to an exact-enum 1.2 — the bump is named in this plan's own dependency
  table; (c) three legacy id prefixes (`lbank_`, `noise_`) that predate the role vocabulary and the
  tightened `ArtifactId` pattern now rejects. **Why the pre-check missed them:** I grepped a narrow
  `id="..."` literal pattern, checked three of ~40 write sites, and generalised to "all other ids
  match their content". Banks built through helpers taking an id *parameter* were invisible to that
  grep. The fix that works is enumerating **every** id literal in the tests and reasoning about each
  one's content, which is what the second pass did.

- 2026-07-28 — Plan written. Read `parameter_estimator_design.md` in full first; STU4 to
  commit-sized steps, other issues at issue level.
- 2026-07-28 — Confirmed no `gui/field_config.py` and no curated per-bank-type field allowlist: the
  filter UI derives columns generically via `filter_columns(df)`. A memory entry claimed otherwise;
  corrected.
- 2026-07-28 — Re-synced to the project-lead's four rulings. Step ids not renumbered; S4 marked ⊘.
- 2026-07-28 — **Second pass.** All issues to commit granularity against the code; S5 / S11 / S14
  split to sub-ids; estimate and points movement recorded above; B17 storage-scope question raised.
- 2026-07-29 — **Effort tracking dropped for 1.5** (Daniel): missed phase-wide; methodology for future
  phases to be worked out by Daniel + project-lead, not retrofitted. Corrected the applied-items table,
  which had claimed this session was logged when it wasn't, and recorded the consequences (no velocity
  data from 1.5; the cleanup roll-up gate is vacuous).
- 2026-07-28 — **T4 signal source settled (Daniel): ClassifierBank traces by default, operator can
  swap to the `synthetic_bank`'s.** Threaded a `signal_source` selector through S4 / S14b / S22 / S26
  / S28 (+1 h at the top of each range → 84–191 h; no band moves). Resolves the like-for-like caveat
  on STU5 in the default configuration, and makes the source delta a free post-processing-vs-
  generation diagnostic. **Consequence flagged:** the default needs the `simulation_id` bank ⋈ bank
  join in 1.5, which §12 assigns to egm-data and defers — DAT1 scope call raised.
- 2026-07-28 — **θ reversed off the ClassifierBank** (investigation §12, artifact-purpose reframe).
  The ClassifierBank is a source-agnostic ML compression carrying only signal + label + `LabelPolicy`
  id + the `simulation_id` join key; θ + per-sim config live on the parallel `synthetic_bank`. **S4
  reinstated** as the typed-`SyntheticBank` read path (the parked id paid off across two reversals);
  S3 / S15 / S22 re-sourced; STU6 M (3) → L (5), 6–13 h → 9–19 h; repo 84–186 h / 41 pts. Answered O1
  and raised the T4-feature-provenance question. FN-vs-θ view logged to `roadmap.md`.
- 2026-07-28 — **§6 corrected + HDF5 git policy landed.** `cross_artifact_linkage_design.md` §6 now
  carries a ⚠-Superseded-for-1.5 banner pointing at design §8 as the authoritative layout, so the
  standing guard-note here was removed. Banks are never committed (`*.h5` / `*.hdf5` gitignored at
  `intracardiac-platform/.gitignore:62–63`); phase-stored locally, Released at ship, regenerable from
  provenance. Added the git-clean assertion to S5d and the unresolved-not-error note for a missing
  in-phase bank.
- 2026-07-28 — **All four escalations closed by the project-lead.** Rulings 1–3 were already applied;
  ruling 4 corrected a scoring error of mine — STU4 · D was labelled the XL anchor but scored L (5).
  Core now XL (8) absorbing · A + · C, · E L (5) → STU4 composite **13**, repo total **39 pts**
  (hours unchanged at 81–180). Confirmed the B17/B19 field split matches S5a-vs-S5b–d.
- 2026-07-28 — **B17 scope settled (Daniel): copy all artifact types, banks included.** Added S5d
  (off-thread copy + progress/cancel + free-space guard); S5c gained sibling-file and idempotency
  mechanics. `cross_artifact_linkage_design.md` §6 still states the old local-first rule and is
  being corrected by the project-lead — the plan follows the decision, not the doc.
