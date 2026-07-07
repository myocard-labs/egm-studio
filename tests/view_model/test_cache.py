"""Tests for the in-memory view-model frame store (view_model/cache) — Block 11 tiered store."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from myocard_egm_studio.view_model.cache import (
    CACHE_FORMAT,
    CacheKey,
    DiskCache,
    FrameStore,
    view_model_key,
)


def _frame() -> pd.DataFrame:
    """A small view-model-ish frame (object column makes deep sizing non-trivial)."""
    return pd.DataFrame({"a": range(100), "b": [f"row-{i}" for i in range(100)]})


def _bytes(frame: pd.DataFrame) -> int:
    return int(frame.memory_usage(deep=True).sum())


def _key(bank_id: str) -> CacheKey:
    return view_model_key(bank_id=bank_id, source="S")


def test_view_model_key_carries_id_params_math_version_and_format() -> None:
    key = view_model_key(bank_id="tbank_x_2026-07-06", source="IAFDB", positive_label=1)
    assert key[0] == "tbank_x_2026-07-06"
    assert key[1] == "IAFDB"
    assert key[-1] == CACHE_FORMAT
    assert isinstance(key[-2], str) and key[-2]  # the egm-features math version is in the key


def test_view_model_key_distinguishes_extraction_params() -> None:
    key = view_model_key(bank_id="b_2026-07-06", source="S", with_features=True, positive_label=1)
    assert view_model_key(bank_id="b_2026-07-06", source="T") != key  # source
    assert view_model_key(bank_id="b_2026-07-06", source="S", with_features=False) != key
    assert view_model_key(bank_id="b_2026-07-06", source="S", positive_label=0) != key


def test_get_or_compute_caches_and_computes_once() -> None:
    store = FrameStore(ceiling_bytes=10_000_000)
    key = _key("b_2026-07-06")
    calls: list[int] = []

    def compute() -> pd.DataFrame:
        calls.append(1)
        return _frame()

    first = store.get_or_compute(key, compute)
    second = store.get_or_compute(key, compute)
    assert len(calls) == 1  # the second call is served from the cache
    assert second is first  # same object — callers treat the frame as immutable
    assert key in store


def test_lru_evicts_least_recently_used_over_ceiling() -> None:
    store = FrameStore(ceiling_bytes=_bytes(_frame()) * 2 + 1)  # room for exactly two
    keys = [_key(f"b{i}_2026-07-06") for i in range(3)]
    for key in keys:
        store.get_or_compute(key, _frame)
    assert keys[0] not in store  # the oldest is evicted
    assert keys[1] in store and keys[2] in store
    assert len(store) == 2


def test_recent_access_survives_eviction() -> None:
    store = FrameStore(ceiling_bytes=_bytes(_frame()) * 2 + 1)
    a, b, c = (_key(f"b{i}_2026-07-06") for i in range(3))
    store.get_or_compute(a, _frame)
    store.get_or_compute(b, _frame)
    store.get_or_compute(a, _frame)  # touch a -> now most-recently-used
    store.get_or_compute(c, _frame)  # overflow evicts the LRU, which is now b
    assert a in store and c in store
    assert b not in store


def test_oversized_frame_is_not_cached() -> None:
    store = FrameStore(ceiling_bytes=10)  # smaller than any real frame
    key = _key("b_2026-07-06")
    store.get_or_compute(key, _frame)  # returned to the caller but not stored (no thrash)
    assert key not in store
    assert len(store) == 0
    assert store.total_bytes() == 0


def test_flush_clears_everything() -> None:
    store = FrameStore(ceiling_bytes=10_000_000)
    store.get_or_compute(_key("b_2026-07-06"), _frame)
    assert len(store) == 1
    store.flush()
    assert len(store) == 0
    assert store.total_bytes() == 0


def test_set_ceiling_evicts_down_immediately() -> None:
    store = FrameStore(ceiling_bytes=_bytes(_frame()) * 3)
    keys = [_key(f"b{i}_2026-07-06") for i in range(3)]
    for key in keys:
        store.get_or_compute(key, _frame)
    assert len(store) == 3
    store.set_ceiling(_bytes(_frame()) + 1)  # room for one
    assert len(store) == 1
    assert keys[2] in store  # the newest survives


# --- DiskCache (the write-through cold tier) --------------------------------


def test_disk_cache_roundtrips_a_frame(tmp_path: Path) -> None:
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=50_000_000)
    key = _key("b_2026-07-06")
    assert disk.load(key) is None  # a miss before anything is written
    disk.save(key, _frame())
    loaded = disk.load(key)
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, _frame())


def test_disk_cache_corrupt_file_is_a_miss_and_removed(tmp_path: Path) -> None:
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=50_000_000)
    key = _key("b_2026-07-06")
    disk.save(key, _frame())
    disk._path(key).write_bytes(b"not a pickle")  # clobber the file
    assert disk.load(key) is None  # treated as a miss…
    assert not disk._path(key).exists()  # …and dropped so the next compute rewrites it


def test_disk_cache_clear_removes_files(tmp_path: Path) -> None:
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=50_000_000)
    key = _key("b_2026-07-06")
    disk.save(key, _frame())
    disk.clear()
    assert disk.load(key) is None


def test_disk_cache_evicts_lru_over_ceiling(tmp_path: Path) -> None:
    frame = _frame()
    probe = tmp_path / "probe.pkl"
    frame.to_pickle(probe)
    size = probe.stat().st_size
    probe.unlink()
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=2 * size)  # room for two files
    keys = [_key(f"b{i}_2026-07-06") for i in range(3)]
    disk.save(keys[0], frame)
    os.utime(disk._path(keys[0]), (1000, 1000))  # make it clearly the oldest
    disk.save(keys[1], frame)
    os.utime(disk._path(keys[1]), (2000, 2000))
    disk.save(keys[2], frame)  # the third file overflows -> evict the oldest (keys[0])
    assert disk.load(keys[0]) is None
    assert disk.load(keys[1]) is not None
    assert disk.load(keys[2]) is not None


# --- FrameStore over a DiskCache (two-tier, write-through) -------------------


def test_frame_store_writes_through_to_disk(tmp_path: Path) -> None:
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=50_000_000)
    store = FrameStore(ceiling_bytes=50_000_000, disk=disk)
    key = _key("b_2026-07-06")
    store.get_or_compute(key, _frame)
    assert disk.load(key) is not None  # persisted at compute time, not at exit


def test_frame_store_serves_from_disk_after_memory_reset(tmp_path: Path) -> None:
    """A fresh store (a restart) over the same disk serves the frame without recomputing."""
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=50_000_000)
    key = _key("b_2026-07-06")
    FrameStore(ceiling_bytes=50_000_000, disk=disk).get_or_compute(key, _frame)  # warms disk
    store = FrameStore(ceiling_bytes=50_000_000, disk=disk)  # cold memory, warm disk
    calls: list[int] = []

    def compute() -> pd.DataFrame:
        calls.append(1)
        return _frame()

    store.get_or_compute(key, compute)
    assert calls == []  # served from disk — never recomputed
    assert key in store  # …and promoted into memory


def test_frame_store_flush_clears_the_disk_tier(tmp_path: Path) -> None:
    disk = DiskCache(tmp_path / "cache", ceiling_bytes=50_000_000)
    store = FrameStore(ceiling_bytes=50_000_000, disk=disk)
    key = _key("b_2026-07-06")
    store.get_or_compute(key, _frame)
    assert disk.load(key) is not None
    store.flush()
    assert disk.load(key) is None  # flush clears the disk tier too
