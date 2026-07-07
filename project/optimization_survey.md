# egm-studio — performance optimization survey (Block 11 spike)

**What this is:** a survey of how single-application tools optimize the processing of
large scientific data, run at the start of **Block 11 (Performance / optimization)** to
(1) check our candidate optimizations against common practice and (2) surface techniques
we had missed. It defines the menu the profiling spike chooses from, and records which
ideas we're building now vs. deferring (with the trigger that would revive each).

**Who it's for:** anyone picking up Block 11 implementation. Read this — especially the
[Profiling results](#profiling-results-2026-07-06), which set the build order.

**Status:** survey + profiling spike complete 2026-07-06 (see
[Profiling results](#profiling-results-2026-07-06), which corrected the freeze root cause
and reordered the plan); **Block 11 shipped** the resulting work — a virtualized result
table, a tiered view-model cache (ADR-028), a cooperative-pumped rebuild, and opt-in
scatter decimation. Retained as the investigation record behind those choices; an
*internal* investigation, not user-facing docs.

---

## The problem we're optimizing

The observed pain (roadmap Block 11; surfaced again in the B10g review):

- **Feature extraction is the slow step on load.** The per-trace view-model runs an
  O(T²) sample-entropy pass (`egm-features.bundle.extract_all`) over every trace. On a
  large bank (IAFDB) this is seconds-to-minutes.
- **Every bank switch recomputes from scratch.** Re-selecting or adding a bank re-derives
  its features; nothing is remembered.
- **The whole-view rebuild froze the window.** Loading a *small* bank while a *large* one
  is already loaded froze the UI, because after the progress-covered extraction
  `combine_view_models` re-derives over **all** loaded banks on the main thread (B10g
  review; tracked here).

Note the shape of the problem: performance scales with **result-set size**, not raw bank
size. The pre-profiling reading was that "nothing renders all rows, so the pain is compute
+ the whole-view rebuild, not rendering" — but **profiling (below) corrected this**: the
result *table* eagerly builds one `QTableWidgetItem` per cell over every result row, so it
*does* render all rows, and that eager build — not the `combine` rebuild — is the freeze.
The work is therefore **virtualize the table + thread the rebuild** (freeze), with
**caching** for revisit latency and decimation as a large-N scatter guard.

---

## Method

A web survey of out-of-core / large-data patterns used in scientific Python and desktop
data tools (numpy/joblib, Polars/DuckDB, HDF5/zarr/Arrow, Qt model/view, time-series
downsampling, streaming statistics). Sources at the end.

---

## Finding 1 — our candidates are all standard practice

Every optimization we had already listed is a well-trodden pattern with a battle-tested
library or algorithm behind it:

| Our idea | Standard name / precedent |
|---|---|
| In-memory result cache keyed by bank id (LRU) | Memoization. `functools.lru_cache` — but it can't key on numpy arrays / DataFrames, which is why the next row exists. |
| Disk cache keyed by content/version hash | **`joblib.Memory`**: hashes the args (numpy / DataFrame included) + the function code, serializes results to disk with compression + memory-mapping, survives restarts. The reference implementation of exactly this idea. |
| Background-thread feature extraction | Standard Qt worker-thread pattern (we already thread the load progress dialog). |
| Virtualized result table | Qt model/view is built for it (`canFetchMore` / `fetchMore`, ~256-row batches). **Caveat that bites us:** `match` / `selectRow` / filtering only see *already-fetched* rows — and our filter drives both flows, so a virtualized table changes filter semantics and must be designed around that. |
| Scatter decimation for overplotting | Named algorithms: **LTTB** (largest-triangle-three-buckets — preserves shape + outliers, only returns real points) and **min/max** decimation. |
| User-set memory ceiling → spill to temp files | Exactly how **Polars' streaming engine** and **DuckDB** do out-of-core: a memory manager watches a threshold; when crossed, it hands the largest partition to a spiller that writes a temp file. |

The consistent caveat across sources: **disk-backed operations are dramatically slower
than in-memory.** Spilling is a safety valve, not a default — the design must keep the
working set in RAM and treat disk as the cold fallback.

---

## Finding 2 — the key insight: one tiered store, not three mechanisms

Our three memory ideas — the in-memory cache, the memory ceiling, and the disk cache — are
not three systems to build and keep in sync. They are **one tiered store**:

- A cache keyed by **(bank id + feature-pipeline version + extraction params)**, each entry
  carrying a **size estimate**. The *version* is the version of the code that computes the
  features — primarily **egm-features** (which owns the sample-entropy / spectral /
  complexity math), plus a small egm-studio **cache-format version** constant bumped if
  egm-studio's own view-model derivation changes. It is **not** egm-studio's overall release
  version (that would needlessly flush the cache on unrelated releases). Because egm-features
  is versioned + pinned under the coordinated-bump discipline, a math change *is* a version
  bump → the cache never reuses results computed by older math.
- A **size-aware LRU** eviction policy keeps the hot working set in RAM under the ceiling.
- Eviction **spills the cold tier to a disk cache** (content-hash keyed, joblib-style)
  rather than dropping it, so a re-select reloads from disk instead of recomputing.
- The user can **flush the disk cache** manually (Settings / a menu action) for a clean
  slate — belt-and-suspenders alongside the automatic version-key invalidation.

> **Shipped refinement (ADR-028).** Implementation changed the disk tier from *write-on-
> eviction* (above) to **write-through**: every computed frame is persisted at compute time,
> not when it's evicted from RAM. That is crash-safe and needs no shutdown hook — a
> write-on-exit scheme loses the resident cache on a crash / kill, and extraction (~3 min)
> dwarfs the pickle write (~0.1 %), so writing every frame is free in practice. The rest of
> this section (one keyed store, version-keyed on the feature math, LRU under a ceiling,
> Flush) shipped as described. See ADR-028 for the as-built design.

This is the joblib.Memory model (transparent, hash-keyed, disk-backed persistence for
large array/DataFrame results) unified with the Polars/DuckDB spilling model (size-aware
threshold eviction). It directly answers the "what's held in memory vs on disk" schema
question we flagged: **one keyed store, one eviction policy, disk is just the cold tier.**
It is the **revisit-latency** centerpiece of Block 11 — but note that profiling (below)
showed the *freeze* is fixed by the table + threading, not by this store; the store's job
is to avoid recomputing the ~3-min extraction on a re-select, not to unfreeze the window.

---

## Block 11 focus (decided 2026-07-06)

Build the **consumer-side** optimizations we already had. The **profiling spike has now
run** ([results below](#profiling-results-2026-07-06)) and reordered these: the
**virtualized table + threading the rebuild** are the freeze fix (top priority), and the
**tiered store** is revisit latency (still built, no longer the freeze centerpiece). The
order below reflects that.

- **Virtualized result table — via model/view (the freeze headline).** Profiling justified
  this decisively: the eager `QTableWidget` populate is ~11 s + ~900 MB at 66k rows, the
  dominant freeze cost. Correctness beats the GUI optimization: filter / select / match must
  operate over **all** rows, never just the visible ones. The full frame already lives in
  memory (ADR-011, ~31 MB), so full-set semantics are preserved *for free* if the table is
  backed by a `QAbstractTableModel` over that frame — the model exposes every row (filter /
  select / match intact) while the `QTableView` renders only visible rows on demand. That
  replaces today's eager `QTableWidget` population and removes both the freeze *and* the
  ~900 MB (the frame is ~31 MB; the widget was the hog). The `canFetchMore` / `fetchMore`
  *streaming* approach is **rejected** (its match / selectRow / filter see only fetched
  rows). No longer conditional.
- **Progress-cover the `set_results` rebuild (cooperative pump) — ✓ shipped 2026-07-06.**
  Even virtualized, the KDE grid is ~4 s. Rather than introduce the app's first worker
  thread, the rebuild stays on the UI thread but *pumps* the progress dialog between the 11
  KDE panels (`feature_grid.set_groups(progress=…)`), consistent with the app's cooperative
  model. This unfreezes the large→small add + the filter-recalc — worst-case gap between
  repaints ~390 ms (one panel) vs the old ~4 s frozen block; the load path stays cancellable.
  `combine` was never the cost (3 ms) — the un-progress-covered GUI rebuild was. Decided (with
  Daniel, 2026-07-06) over a true worker thread to keep one concurrency model + low risk; the
  worker-thread escalation is deferred with a trigger (below).
- **Tiered result store (revisit latency).** In-memory cache keyed by (bank id +
  egm-features version + extraction params), size-aware LRU, spilling the cold tier to a
  temp/cache dir under a **user-settable memory ceiling** (Settings). Re-selecting a loaded
  bank is instant; a bank switch never recomputes the ~3-min extraction. An egm-features
  (math) change invalidates automatically via the version key; the user can also **flush the
  disk cache** manually. Profiling sizes the ceiling generously — frames are ~31 MB, so many
  IAFDB-scale banks fit in RAM and disk-spill is a rare safety valve.
- **Filter-change cost — measure, likely skip.** Re-filtering only the rows that already
  passed when a filter *narrows* ("incremental filtering") is a real technique, but the
  row-masking is already fast (a vectorized pandas mask over 66k rows ≈ milliseconds). The
  real cost of a filter change is the **downstream rebuilds** it triggers — the
  distribution-grid KDEs, the scatter, the result table (B7-filter-A). So the win, *if*
  profiling flags filtering at all, is recomputing only the *changed* downstream views, not
  the masking. Demoted from a build item to a profiling-pass check.
- **Scatter decimation** for the two-large-banks overplot case that bring-to-front can't fix
  (roadmap B7-scatter-front note). Overplotting is a *visual* problem, not a timing one (the
  data prep is ~18 ms). **Shipped 2026-07-06** as an *opt-in* per-source uniform subsample (a
  Decimate toggle + a pts/source level). Correction: the LTTB / min-max named above apply to
  **1-D trace-line** downsampling, not a 2-D feature scatter — a uniform random subsample is
  the right decimation for a point cloud.

---

## Profiling results (2026-07-06)

Instrumented the load pipeline at IAFDB scale (66k rows) with `scripts/profile_load.py`
(`--bank PATH` runs the true read+extract path on a real bank; the default synthesizes a
66k-row frame to exercise the downstream rebuild without waiting minutes for extraction).
Measured on an offscreen Qt build in the sandbox.

| Stage | Time | Peak RSS | Progress-covered? |
|---|---|---|---|
| `load_classifier_bank` (HDF5 read) | ~33 ms / 4k traces | — | yes |
| `build_view_model` (feature extract) | ~2.9 ms/trace → **~190 s @ 66k** | — | **yes** (progress dialog) |
| `combine_view_models` | **3 ms** | — | n/a |
| `feature_groups_by_source` (KDE prep) | 20 ms | — | — |
| `scatter_series_by_source` | 18 ms | — | — |
| **`ResultList.set_frame`** (table populate) | **~11,000 ms** | **+~900 MB** | **NO ← freeze** |
| **`FeatureDistributionGrid.set_groups`** (KDE render) | **~4,000 ms** | | **NO ← freeze** |

**What it settled:**

1. **The freeze is the eager result table, not `combine`.** `combine_view_models` is 3 ms —
   exonerated. The large→small freeze is the un-progress-covered `set_results` GUI rebuild:
   `ResultList.set_frame` allocates one `QTableWidgetItem` per cell (~1.2M items at 66k×18 →
   ~11 s + ~900 MB), plus the 11-panel KDE grid (~4 s). Confirmed in code at
   `result_list.py:115-119` (`setRowCount` then a nested per-cell `setItem`).
2. **"Nothing renders all rows" was wrong** (the ADR-011 premise applied to the plots, not
   the table). The table *does* eagerly render every row — which is why the virtualized
   table jumps from "maybe, if justified" to the headline fix.
3. **Extraction is the slow load step, not a freeze.** ~2.9 ms/trace at T=1000 → ~3 min at
   66k, matching the "couple of minutes" field estimate — but progress-covered. It scales
   linearly in trace *count*; at these lengths it is sub-quadratic in trace length (the
   other 10 features dominate, not sampen's O(T²)), so the real per-trace rate scales with
   the actual trace length. This is exactly what the tiered store avoids recomputing.
4. **The frame is cheap; the widget was the hog.** 66k rows ≈ 31 MB in memory; the 900 MB
   was the table widget. So virtualizing the table also removes the memory blowup, and the
   cache memory-ceiling default can be generous (many IAFDB-scale frames fit in RAM).
5. **Read + `combine` + data-prep are all negligible** (tens of ms) — no work needed there.

**Reprioritization (folded into `roadmap.md` Block 11):** (1) virtualized result table,
(2) thread / progress-cover the `set_results` rebuild, (3) tiered store (revisit latency),
(4) scatter decimation. The survey's original "tiered store is *the* centerpiece" was about
compute latency; the *freeze* centerpiece is the table + threading.

**Caveat:** `--bank` against the on-disk sample banks hit a schema-version gap (they are
`schema_version 0.1`; current egm-data wants `0.2`), so exact real-IAFDB numbers need a
freshly-written bank. The synthetic numbers above are what drive the conclusions, and the
extraction rate matches the field estimate.

---

## Deferred techniques + their triggers (decided 2026-07-06)

These are real, standard techniques that we are **not** building now — each adds complexity
for a scale we're not near. Recorded with the trigger that would revive it:

- **Memory-map the source instead of loading whole banks** (`numpy.memmap` / HDF5 / zarr /
  Arrow read only the traces + columns touched; an **egm-data** change) **+ approximate
  stats** (t-digest / reservoir sampling for quantiles + KDE on the summary grid / scatter
  instead of every row).
  **Trigger:** we start needing to process *truly huge* banks. Not anticipated soon —
  IAFDB is the largest bank in the foreseeable future and it fits in memory.
- **Accelerate the O(T²) sample-entropy kernel** (vectorize → Numba → Cython; an
  **egm-features** change).
  **Trigger:** the feature calculation grows in complexity, **or** we regularly work with
  multiple banks the size of IAFDB. Today IAFDB extraction takes a couple of minutes —
  acceptable.
- **Shrink the in-memory frame** (downcast metadata dtypes, `categorical` for repeated
  strings like source / label) **+ copy-on-write** (avoid defensive copies in the combine
  path).
  **Trigger:** we regularly overflow the memory ceiling and the constant disk read/write
  causes significant slowdown.
- **Escalate to a true worker thread (generalized).** Move heavy compute off the UI thread
  entirely — the proper async — instead of the cooperative pump we shipped. Applies to **any**
  prohibitive compute, not just the KDE grid. Requires separating compute from render (pull
  the scipy KDE math out of the pyqtgraph draw), which also feeds the tiered store (cache
  computed curves) and pairs naturally with it. Introduces the app's first worker thread + a
  second concurrency model, so it's deliberately deferred.
  **Trigger:** a compute cost grows past what a pumped dialog can hide (the per-unit pump gap
  gets annoyingly long), **or** full mid-rebuild interactivity becomes a requirement.

---

## Cross-repo scope note

The largest *raw* wins live **upstream**, not in egm-studio: memory-mapping in **egm-data**,
the entropy kernel in **egm-features**, and "precompute features when the producer writes
the bank" in **iafdb-pipeline / egm-classifier** (so egm-studio loads precomputed features
instead of extracting on every open). Block 11 is deliberately the **egm-studio
consumer-side half** (cache + responsive rebuild + virtualize + decimate). The deferred upstream items
above are cross-cutting; coordinate them through the architecture chat if/when their
triggers fire.

---

## Sources

- [Mastering out-of-core algorithms](https://www.numberanalytics.com/blog/mastering-out-of-core-algorithms)
- [joblib.Memory — on-demand recomputing](https://joblib.readthedocs.io/en/stable/memory.html)
- [Inside Polars' streaming engine: spillable sinks](https://python-news.com/inside-polars-streaming-engine-how-spillable-sinks-handle-larger-than-ram-joins)
- [DuckDB vs Polars vs pandas benchmark (out-of-core + spill)](https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-dataframe-libraries)
- [Loading numpy arrays from disk: mmap vs Zarr/HDF5](https://pythonspeed.com/articles/mmap-vs-zarr-hdf5/)
- [Largest-Triangle-Three-Buckets downsampling](https://rajnandan.com/posts/largest-triangle-three-buckets-downsampling/)
- [Qt canFetchMore / fetchMore lazy loading](https://www.pythonguis.com/faq/qsqltable-canfetchmore-advice/)
- [Numba vs Cython vs vectorization playbook](https://medium.com/@2nick2patel2/python-cython-numba-playbook-when-to-compile-when-to-vectorize-1253498c987a)
- [t-digest (streaming quantiles)](https://github.com/tdunning/t-digest)
</content>
</invoke>
