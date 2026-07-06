# egm-studio — performance optimization survey (Block 11 spike)

**What this is:** a survey of how single-application tools optimize the processing of
large scientific data, run at the start of **Block 11 (Performance / optimization)** to
(1) check our candidate optimizations against common practice and (2) surface techniques
we had missed. It defines the menu the profiling spike chooses from, and records which
ideas we're building now vs. deferring (with the trigger that would revive each).

**Who it's for:** anyone picking up Block 11. Read this before the profiling spike.

**Status:** literature/tooling survey complete 2026-07-06. Profiling spike + implementation
pending. This is an *internal investigation*, not user-facing docs.

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

Note the shape of the problem: **nothing renders all rows today** — performance scales
with result-set size, not bank size (ADR-011). So the pain is **compute + the whole-view
rebuild**, not rendering. That focuses the work on caching + threading, with virtualization
/ decimation as guards for the pathological large-N cases.

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

This is the joblib.Memory model (transparent, hash-keyed, disk-backed persistence for
large array/DataFrame results) unified with the Polars/DuckDB spilling model (size-aware
threshold eviction). It directly answers the "what's held in memory vs on disk" schema
question we flagged: **one keyed store, one eviction policy, disk is just the cold tier.**
This is the centerpiece of Block 11.

---

## Block 11 focus (decided 2026-07-06)

Build the **consumer-side** optimizations we already had, centered on the tiered store.
The **profiling spike runs first** to confirm where the seconds actually go (extraction vs
the combine-rebuild vs render) and to size the cache + ceiling defaults.

- **Tiered result store.** In-memory cache keyed by (bank id + egm-features version +
  extraction params), size-aware LRU, spilling the cold tier to a temp/cache dir under a
  **user-settable memory ceiling** (Settings). Re-selecting a loaded bank is instant; a
  bank switch never recomputes. An egm-features (math) change invalidates automatically via
  the version key; the user can also **flush the disk cache** manually.
- **Background-thread the extraction + the view build.** Fixes the large→small freeze:
  the `combine_view_models` re-derive runs off the UI thread and/or is served from the
  cache, so it never blocks.
- **Virtualized result table — via model/view, only if profiling justifies it.**
  Correctness beats the GUI optimization: filter / select / match must operate over **all**
  rows, never just the visible ones. The full frame already lives in memory (ADR-011), so
  full-set semantics are preserved *for free* if the table is backed by a
  `QAbstractTableModel` over that frame — the model exposes every row (filter / select /
  match intact) while the `QTableView` renders only visible rows on demand. That replaces
  today's eager `QTableWidget` population. The `canFetchMore` / `fetchMore` *streaming*
  approach is **rejected** (its match / selectRow / filter see only fetched rows). Do the
  model/view swap only if profiling shows the eager table build is a real cost; otherwise
  skip it.
- **Filter-change cost — measure, likely skip.** Re-filtering only the rows that already
  passed when a filter *narrows* ("incremental filtering") is a real technique, but the
  row-masking is already fast (a vectorized pandas mask over 66k rows ≈ milliseconds). The
  real cost of a filter change is the **downstream rebuilds** it triggers — the
  distribution-grid KDEs, the scatter, the result table (B7-filter-A). So the win, *if*
  profiling flags filtering at all, is recomputing only the *changed* downstream views, not
  the masking. Demoted from a build item to a profiling-pass check.
- **Scatter decimation** (LTTB / min-max) for the two-large-banks overplot case that
  bring-to-front can't fix (roadmap B7-scatter-front note).

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

---

## Cross-repo scope note

The largest *raw* wins live **upstream**, not in egm-studio: memory-mapping in **egm-data**,
the entropy kernel in **egm-features**, and "precompute features when the producer writes
the bank" in **iafdb-pipeline / egm-classifier** (so egm-studio loads precomputed features
instead of extracting on every open). Block 11 is deliberately the **egm-studio
consumer-side half** (cache + threads + virtualize + decimate). The deferred upstream items
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
