"""Size-bounded cache of computed view-model frames — the Block 11 tiered store (in-memory tier).

Re-opening or re-adding a bank re-runs the O(T^2) feature extraction
(:func:`build_view_model`) — minutes on an IAFDB-scale bank (profiling, 2026-07-06).
This store memoizes the per-bank frame so a revisit is instant.

**Key.** A frame is keyed by :func:`view_model_key` = the bank's stable id + the
extraction params (``source`` / ``with_features`` / ``positive_label``) + the *feature
math* version. The math version is **egm-features' package version** (which owns the
sample-entropy / spectral / complexity math) plus a small egm-studio :data:`CACHE_FORMAT`
constant for our own view-model derivation — deliberately **not** egm-studio's release
version, so unrelated releases don't needlessly flush the cache, while any change to the
feature math (an egm-features bump under the coordinated-bump discipline) *does* change the
key and so never reuses stale results.

**Policy.** A size-aware LRU keeps the hot working set in RAM under a byte ceiling; a
write-through :class:`DiskCache` is the persistent cold tier, so a computed frame survives
a restart and a memory miss falls through to disk before recomputing. The ceilings are
injected by the consumer (the GUI, from a user preference / a cache dir) — this module
ships no defaults, per the "defaults live in the executable-level consumer" convention.

Qt-free and single-threaded (the app drives it from the GUI thread); no locking.
"""

from __future__ import annotations

import hashlib
import os
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import myocard_egm_features
import pandas as pd

#: Bump when egm-studio's *own* view-model derivation changes shape such that older cached
#: frames must not be reused — independent of the egm-features math version in the key.
CACHE_FORMAT = 1

#: A view-model cache key: (bank id, source, with_features, positive_label,
#: egm-features version, cache-format). Everything that changes the computed frame.
CacheKey = tuple[str, str | None, bool, int, str, int]


def view_model_key(
    *,
    bank_id: str,
    source: str | None,
    with_features: bool = True,
    positive_label: int = 1,
) -> CacheKey:
    """The cache key for a :func:`build_view_model` result.

    ``bank_id`` must be the bank's stable artifact id — the caller skips caching for a bank
    without one (an unidentified bank would collide with others under a shared key).
    """
    features_version = str(getattr(myocard_egm_features, "__version__", "unknown"))
    return (bank_id, source, with_features, positive_label, features_version, CACHE_FORMAT)


def _frame_bytes(frame: pd.DataFrame) -> int:
    """Deep in-memory size of ``frame`` (object columns counted, not just the pointers)."""
    return int(frame.memory_usage(deep=True).sum())


@dataclass
class _Entry:
    frame: pd.DataFrame
    nbytes: int


class DiskCache:
    """A content-addressed, size-capped on-disk cache of view-model frames (cold tier).

    The **write-through** backing for :class:`FrameStore`: every computed frame is pickled
    here at compute time, keyed by a hash of its :data:`CacheKey`, so it survives a restart
    (persistence happens at compute time, not at exit — no shutdown hook to lose on a crash).
    The version + cache-format live in the key → in the filename, so a feature-math change
    simply addresses different files (old ones linger until evicted / flushed, never reused).

    Reads are defensive: an unreadable / incompatible pickle is treated as a miss and the
    file removed (→ recompute + rewrite). A byte cap bounds the directory — on write, the
    least-recently-used files (by mtime; a read touches mtime) are deleted until it fits.
    Qt-free; the GUI supplies the cache directory (a platform cache location).
    """

    def __init__(self, cache_dir: Path, ceiling_bytes: int) -> None:
        self._dir = cache_dir
        self._ceiling = max(0, int(ceiling_bytes))

    def load(self, key: CacheKey) -> pd.DataFrame | None:
        """Return the cached frame for ``key`` from disk, or None (miss / unreadable)."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            frame: pd.DataFrame = pd.read_pickle(path)
        except Exception:  # a corrupt / incompatible pickle is just a miss — drop + recompute
            path.unlink(missing_ok=True)
            return None
        os.utime(path, None)  # mark most-recently-used for the disk LRU
        return frame

    def save(self, key: CacheKey, frame: pd.DataFrame) -> None:
        """Write ``frame`` for ``key`` (write-through), then evict LRU files over the cap."""
        if self._ceiling == 0:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        try:
            frame.to_pickle(path)
        except Exception:  # a failed write must not break the load path — skip caching
            path.unlink(missing_ok=True)
            return
        self._enforce_ceiling()

    def clear(self) -> None:
        """Delete every cached file (the Flush action clears this tier too)."""
        for path in self._files():
            path.unlink(missing_ok=True)

    def _path(self, key: CacheKey) -> Path:
        digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.pkl"

    def _files(self) -> list[Path]:
        return [p for p in self._dir.glob("*.pkl") if p.is_file()] if self._dir.exists() else []

    def _enforce_ceiling(self) -> None:
        files = self._files()
        total = sum(p.stat().st_size for p in files)
        for path in sorted(files, key=lambda p: p.stat().st_mtime):  # oldest first
            if total <= self._ceiling:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)


class FrameStore:
    """An LRU cache of view-model frames bounded by a total byte ceiling.

    Insertion order is recency (most-recently-used last); eviction drops the
    least-recently-used entries until the total fits the ceiling. A frame larger than the
    whole ceiling is returned to the caller but **not** cached (caching it would evict
    everything and immediately overflow — pure thrash).

    An optional :class:`DiskCache` ``disk`` makes this a two-tier store: the memory LRU is
    the hot front, the disk cache the persistent (write-through) cold tier. A memory miss
    falls through to disk before recomputing; eviction from memory only frees RAM (the disk
    copy stays), so the disk survives a restart.
    """

    def __init__(self, ceiling_bytes: int, *, disk: DiskCache | None = None) -> None:
        self._ceiling = max(0, int(ceiling_bytes))
        self._entries: OrderedDict[CacheKey, _Entry] = OrderedDict()
        self._bytes = 0
        self._disk = disk

    def get_or_compute(self, key: CacheKey, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        """Return the cached frame for ``key``, else run ``compute`` and cache its result.

        Lookup order: memory → disk (if backed) → ``compute``. A computed frame is written
        through to disk before it goes in memory, so it persists even if it's too big for
        the memory ceiling. The returned frame is treated as immutable by callers (the
        combine step copies it), so the same object may back several loads of one bank.
        ``compute`` runs *before* any store mutation, so a raising / cancelled compute
        leaves the cache untouched.
        """
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)  # now most-recently-used
            return entry.frame
        if self._disk is not None:
            on_disk = self._disk.load(key)
            if on_disk is not None:
                self._store(key, on_disk)  # promote the disk hit into memory
                return on_disk
        frame = compute()
        if self._disk is not None:
            self._disk.save(key, frame)  # write-through before the memory ceiling can reject it
        self._store(key, frame)
        return frame

    def __contains__(self, key: CacheKey) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def total_bytes(self) -> int:
        """Current resident size of the cache (sum of entry sizes)."""
        return self._bytes

    def set_ceiling(self, ceiling_bytes: int) -> None:
        """Change the byte ceiling, evicting down to it immediately if lowered."""
        self._ceiling = max(0, int(ceiling_bytes))
        self._evict()

    def flush(self) -> None:
        """Drop every entry — memory *and* the disk cold tier (the Settings ▸ Flush action)."""
        self._entries.clear()
        self._bytes = 0
        if self._disk is not None:
            self._disk.clear()

    def _store(self, key: CacheKey, frame: pd.DataFrame) -> None:
        nbytes = _frame_bytes(frame)
        if self._ceiling and nbytes > self._ceiling:
            return  # a single frame bigger than the whole ceiling — don't thrash on it
        self._entries[key] = _Entry(frame, nbytes)
        self._entries.move_to_end(key)
        self._bytes += nbytes
        self._evict()

    def _evict(self) -> None:
        while self._bytes > self._ceiling and self._entries:
            _, evicted = self._entries.popitem(last=False)  # least-recently-used
            self._bytes -= evicted.nbytes
