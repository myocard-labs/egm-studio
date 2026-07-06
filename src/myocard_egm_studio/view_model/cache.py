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

**Policy.** A size-aware LRU keeps the hot working set in RAM under a byte ceiling; the
cold tier spills to disk in a later step (roadmap Block 11). The ceiling is injected by the
consumer (the GUI, from a user preference) — this module ships no default, per the
"defaults live in the executable-level consumer" convention.

Qt-free and single-threaded (the app drives it from the GUI thread); no locking.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

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


class FrameStore:
    """An LRU cache of view-model frames bounded by a total byte ceiling.

    Insertion order is recency (most-recently-used last); eviction drops the
    least-recently-used entries until the total fits the ceiling. A frame larger than the
    whole ceiling is returned to the caller but **not** cached (caching it would evict
    everything and immediately overflow — pure thrash).
    """

    def __init__(self, ceiling_bytes: int) -> None:
        self._ceiling = max(0, int(ceiling_bytes))
        self._entries: OrderedDict[CacheKey, _Entry] = OrderedDict()
        self._bytes = 0

    def get_or_compute(self, key: CacheKey, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        """Return the cached frame for ``key``, else run ``compute`` and cache its result.

        The returned frame is treated as immutable by callers (the combine step copies it),
        so the same object may back several loads of one bank. ``compute`` runs *before* any
        store mutation, so a raising / cancelled compute leaves the cache untouched.
        """
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)  # now most-recently-used
            return entry.frame
        frame = compute()
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
        """Drop every entry (the Settings ▸ Flush cache action)."""
        self._entries.clear()
        self._bytes = 0

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
