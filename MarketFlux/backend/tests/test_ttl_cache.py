import time

from ttl_cache import TTLCache


def test_ttl_cache_expires():
    cache = TTLCache()
    cache.set("k", "v", expire=1)
    assert cache.get("k") == "v"
    time.sleep(1.05)
    assert cache.get("k") is None
    assert cache.get("k", 0) == 0
