"""Tests for the in-memory view-model frame store (view_model/cache) — Block 11 tiered store."""

from __future__ import annotations

import pandas as pd

from myocard_egm_studio.view_model.cache import (
    CACHE_FORMAT,
    CacheKey,
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
