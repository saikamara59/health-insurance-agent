import time

from healthflow.tools.provider_cache import InMemoryProviderCache


def test_set_and_get_within_ttl():
    cache = InMemoryProviderCache(ttl_seconds=60)
    cache.set("npi:1234567890", {"npi": "1234567890", "name": "Dr. Chen"})
    result = cache.get("npi:1234567890")
    assert result is not None
    assert result["npi"] == "1234567890"
    assert result["name"] == "Dr. Chen"


def test_expired_entry_returns_none():
    cache = InMemoryProviderCache(ttl_seconds=1)
    cache.set("npi:1234567890", {"npi": "1234567890", "name": "Dr. Chen"})
    time.sleep(1.1)
    result = cache.get("npi:1234567890")
    assert result is None


def test_nonexistent_key_returns_none():
    cache = InMemoryProviderCache(ttl_seconds=60)
    result = cache.get("npi:9999999999")
    assert result is None


def test_multiple_entries_independent():
    cache = InMemoryProviderCache(ttl_seconds=60)
    cache.set("npi:1111111111", {"npi": "1111111111", "name": "Dr. A"})
    cache.set("npi:2222222222", {"npi": "2222222222", "name": "Dr. B"})
    result_a = cache.get("npi:1111111111")
    result_b = cache.get("npi:2222222222")
    assert result_a is not None
    assert result_b is not None
    assert result_a["name"] == "Dr. A"
    assert result_b["name"] == "Dr. B"


def test_overwrite_existing_key():
    cache = InMemoryProviderCache(ttl_seconds=60)
    cache.set("npi:1234567890", {"name": "Dr. Old"})
    cache.set("npi:1234567890", {"name": "Dr. New"})
    result = cache.get("npi:1234567890")
    assert result is not None
    assert result["name"] == "Dr. New"


def test_default_ttl_is_86400():
    cache = InMemoryProviderCache()
    assert cache.ttl_seconds == 86400
