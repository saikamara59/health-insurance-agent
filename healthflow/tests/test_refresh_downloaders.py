"""Unit tests for scripts.refresh_data downloaders and cache wrapper."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import refresh_data
from scripts.refresh_data import _load_or_fetch


@pytest.fixture
def fake_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh_data, "CACHE_DIR", tmp_path)
    return tmp_path


def test_cache_miss_calls_fetcher_and_writes(fake_cache_dir):
    calls = []

    def fetcher():
        calls.append(1)
        return {"a": 1}

    result = _load_or_fetch("test_key", ttl_days=7, fetch_fn=fetcher)
    assert result == {"a": 1}
    assert calls == [1]
    cached = json.loads((fake_cache_dir / "test_key.json").read_text())
    assert cached == {"a": 1}


def test_cache_hit_skips_fetcher(fake_cache_dir):
    (fake_cache_dir / "test_key.json").write_text(json.dumps({"cached": True}))

    def fetcher():
        raise AssertionError("fetcher should not be called")

    result = _load_or_fetch("test_key", ttl_days=7, fetch_fn=fetcher)
    assert result == {"cached": True}


def test_cache_expired_calls_fetcher(fake_cache_dir):
    cache_path = fake_cache_dir / "test_key.json"
    cache_path.write_text(json.dumps({"old": True}))
    # Backdate the file by 10 days; TTL is 7
    old = time.time() - (10 * 86400)
    import os as _os
    _os.utime(cache_path, (old, old))

    def fetcher():
        return {"fresh": True}

    result = _load_or_fetch("test_key", ttl_days=7, fetch_fn=fetcher)
    assert result == {"fresh": True}


def test_cache_corrupt_is_treated_as_miss(fake_cache_dir):
    (fake_cache_dir / "test_key.json").write_text("{not valid json")

    def fetcher():
        return {"recovered": True}

    result = _load_or_fetch("test_key", ttl_days=7, fetch_fn=fetcher)
    assert result == {"recovered": True}
    # Cache should now contain the fresh result
    assert json.loads((fake_cache_dir / "test_key.json").read_text()) == {"recovered": True}


def test_cache_force_bypasses_hit(fake_cache_dir):
    (fake_cache_dir / "test_key.json").write_text(json.dumps({"cached": True}))

    def fetcher():
        return {"fresh": True}

    result = _load_or_fetch("test_key", ttl_days=7, fetch_fn=fetcher, force=True)
    assert result == {"fresh": True}


def test_cache_serializes_sets_as_sorted_lists(fake_cache_dir):
    def fetcher():
        return {"plan_a": {"36061", "36047"}}

    _load_or_fetch("sets", ttl_days=7, fetch_fn=fetcher)
    cached = json.loads((fake_cache_dir / "sets.json").read_text())
    assert cached == {"plan_a": ["36047", "36061"]}


def test_cache_does_not_write_when_fetcher_returns_none(fake_cache_dir):
    def fetcher():
        return None

    result = _load_or_fetch("none_key", ttl_days=7, fetch_fn=fetcher)
    assert result is None
    assert not (fake_cache_dir / "none_key.json").exists()


def test_cache_handles_tuple_in_payload(fake_cache_dir):
    """download_cms_data returns (plans, plan_county_map) — a tuple. Verify it round-trips."""
    def fetcher():
        return ([("P1", "Foo")], {"P1": {"36061"}})

    result = _load_or_fetch("tuple_key", ttl_days=7, fetch_fn=fetcher)
    assert result == ([("P1", "Foo")], {"P1": {"36061"}})
    # Reload from cache
    result2 = _load_or_fetch("tuple_key", ttl_days=7, fetch_fn=lambda: pytest.fail("should be cached"))
    # JSON round-trip turns tuples into lists. The orchestrator handles this
    # by re-coercing the plans list back to tuples; this test just documents.
    assert result2 == [[["P1", "Foo"]], {"P1": ["36061"]}]


# -- download_hud_zip_county ---------------------------------------------------

class _MockHudResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):
        return self._payload


def test_hud_returns_none_when_token_missing(monkeypatch):
    monkeypatch.delenv("HUD_API_TOKEN", raising=False)
    assert refresh_data.download_hud_zip_county() is None


def test_hud_parses_response(monkeypatch):
    monkeypatch.setenv("HUD_API_TOKEN", "fake-token")
    payload = {
        "data": {
            "results": [
                {"zip": "10001", "geoid": "36061"},
                {"zip": "10001", "geoid": "36047"},  # multi-county ZIP
                {"zip": "11201", "geoid": "36047"},
            ]
        }
    }

    class _Client:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None, headers=None):
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer fake-token"
            return _MockHudResponse(payload)

    monkeypatch.setattr(refresh_data, "httpx", type("M", (), {"Client": _Client}))
    result = refresh_data.download_hud_zip_county()
    assert result == {
        "10001": {"36061", "36047"},
        "11201": {"36047"},
    }


def test_hud_handles_network_error(monkeypatch):
    monkeypatch.setenv("HUD_API_TOKEN", "fake-token")

    class _Client:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **kw):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(refresh_data, "httpx", type("M", (), {"Client": _Client}))
    assert refresh_data.download_hud_zip_county() is None


def test_hud_handles_empty_results(monkeypatch):
    monkeypatch.setenv("HUD_API_TOKEN", "fake-token")

    class _Client:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **kw):
            return _MockHudResponse({"data": {"results": []}})

    monkeypatch.setattr(refresh_data, "httpx", type("M", (), {"Client": _Client}))
    assert refresh_data.download_hud_zip_county() == {}
