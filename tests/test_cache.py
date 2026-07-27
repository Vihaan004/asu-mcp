import time

from asu_mcp.core import TTLCache, cache_key


def test_returns_value_within_ttl():
    cache = TTLCache()
    cache.set("k", {"v": 1}, ttl=60)
    assert cache.get("k") == {"v": 1}


def test_expires_after_ttl():
    cache = TTLCache()
    cache.set("k", "v", ttl=0.01)
    time.sleep(0.02)
    assert cache.get("k") is None


def test_miss_returns_none():
    assert TTLCache().get("nope") is None


def test_evicts_when_full():
    cache = TTLCache(max_entries=2)
    cache.set("a", 1, ttl=60)
    cache.set("b", 2, ttl=120)
    cache.set("c", 3, ttl=180)
    assert len(cache._data) == 2
    # "a" expires soonest, so it is the one dropped.
    assert cache.get("a") is None
    assert cache.get("c") == 3


def test_cache_key_is_order_independent():
    assert cache_key("/classes", {"a": 1, "b": 2}) == cache_key("/classes", {"b": 2, "a": 1})


def test_cache_key_separates_paths_and_params():
    assert cache_key("/classes", {"a": 1}) != cache_key("/terms", {"a": 1})
    assert cache_key("/classes", {"a": 1}) != cache_key("/classes", {"a": 2})
    assert cache_key("/terms", None) == cache_key("/terms", {})
