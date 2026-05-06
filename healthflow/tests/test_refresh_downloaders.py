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


# -- download_cms_data --------------------------------------------------------

class _MockCmsClient:
    """Returns canned paged responses; tracks calls."""
    def __init__(self, pages):
        self._pages = list(pages)  # list of list[dict]
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get(self, url, params=None):
        self.calls.append(params)
        if not self._pages:
            return _MockHudResponse([])
        return _MockHudResponse(self._pages.pop(0))


def _install_cms_mock(monkeypatch, client):
    monkeypatch.setattr(refresh_data, "httpx", type("M", (), {"Client": lambda *a, **kw: client}))


def test_cms_paginates_and_dedupes(monkeypatch):
    _row_61 = {"contract_id": "H1", "plan_id": "001", "plan_name": "Foo", "organization_name": "Aetna",
               "plan_type": "HMO", "monthly_consolidated_premium": "0", "annual_drug_deductible": "0",
               "out_of_pocket_maximum": "5000", "overall_star_rating": "4", "drug_coverage": "Yes",
               "state": "NY", "county_code": "36061"}
    _row_47 = {**_row_61, "county_code": "36047"}  # same plan, different county
    # page1 must be exactly $limit (5000) so the loop continues to page2
    page1 = ([_row_61, _row_47] * 2500)  # 5000 rows, alternating counties; plan dedupes to 1
    page2 = [
        {"contract_id": "H2", "plan_id": "002", "plan_name": "Bar", "organization_name": "Humana",
         "plan_type": "PPO", "monthly_consolidated_premium": "45", "annual_drug_deductible": "100",
         "out_of_pocket_maximum": "6000", "overall_star_rating": "3.5", "drug_coverage": "No",
         "state": "FL", "county_code": "12086"},
    ]  # short page (1 row) → loop stops after page2
    client = _MockCmsClient([page1, page2])
    _install_cms_mock(monkeypatch, client)

    result = refresh_data.download_cms_data()
    assert result is not None
    plans, plan_county_map = result
    assert len(plans) == 2
    plan_ids = {p[0] for p in plans}
    assert plan_ids == {"H1-001", "H2-002"}
    assert plan_county_map == {"H1-001": {"36061", "36047"}, "H2-002": {"12086"}}


def test_cms_stops_on_short_page(monkeypatch):
    """A page shorter than $limit terminates pagination without a follow-up call."""
    short_page = [
        {"contract_id": "H1", "plan_id": "001", "plan_name": "Foo", "organization_name": "X",
         "plan_type": "HMO", "monthly_consolidated_premium": "0", "annual_drug_deductible": "0",
         "out_of_pocket_maximum": "5000", "overall_star_rating": "4", "drug_coverage": "Yes",
         "state": "NY", "county_code": "36061"},
    ]
    client = _MockCmsClient([short_page])
    _install_cms_mock(monkeypatch, client)

    result = refresh_data.download_cms_data()
    assert result is not None
    assert len(client.calls) == 1  # no second call


def test_cms_skips_malformed_rows(monkeypatch):
    page = [
        {"contract_id": "H1", "plan_id": "001", "plan_name": "Good", "organization_name": "X",
         "plan_type": "HMO", "monthly_consolidated_premium": "0", "annual_drug_deductible": "0",
         "out_of_pocket_maximum": "5000", "overall_star_rating": "4", "drug_coverage": "Yes",
         "state": "NY", "county_code": "36061"},
        {"contract_id": "H2", "plan_id": "BAD", "plan_name": "Bad", "organization_name": "X",
         "plan_type": "HMO", "monthly_consolidated_premium": "not-a-number",
         "annual_drug_deductible": "0", "out_of_pocket_maximum": "5000",
         "overall_star_rating": "Not enough data", "drug_coverage": "Yes",
         "state": "NY", "county_code": "36061"},
    ]
    client = _MockCmsClient([page])
    _install_cms_mock(monkeypatch, client)

    result = refresh_data.download_cms_data()
    assert result is not None
    plans, _ = result
    plan_ids = {p[0] for p in plans}
    # The "Bad" row has a non-numeric premium → skipped. The "Not enough data"
    # rating is handled with a 3.0 default in the existing code.
    assert plan_ids == {"H1-001"}


def test_cms_returns_none_on_first_page_error(monkeypatch):
    class _Failing:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **kw): raise RuntimeError("network is hard")
    monkeypatch.setattr(refresh_data, "httpx", type("M", (), {"Client": lambda *a, **kw: _Failing()}))
    assert refresh_data.download_cms_data() is None


def test_cms_partial_success_returns_what_we_have(monkeypatch):
    """Page 1 succeeds, page 2 fails — return collected plans, don't crash."""
    page1 = [
        {"contract_id": "H1", "plan_id": "001", "plan_name": "Foo", "organization_name": "X",
         "plan_type": "HMO", "monthly_consolidated_premium": "0", "annual_drug_deductible": "0",
         "out_of_pocket_maximum": "5000", "overall_star_rating": "4", "drug_coverage": "Yes",
         "state": "NY", "county_code": "36061"},
    ] * 5000  # exactly $limit so the loop will try again

    class _PartialClient:
        def __init__(self): self.n = 0
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **kw):
            self.n += 1
            if self.n == 1:
                return _MockHudResponse(page1)
            raise RuntimeError("page 2 failed")

    client = _PartialClient()
    monkeypatch.setattr(refresh_data, "httpx", type("M", (), {"Client": lambda *a, **kw: client}))

    result = refresh_data.download_cms_data()
    assert result is not None
    plans, plan_county_map = result
    assert len(plans) == 1  # deduped
    assert "H1-001" in plan_county_map


def test_cms_returns_none_when_httpx_missing(monkeypatch):
    monkeypatch.setattr(refresh_data, "httpx", None)
    assert refresh_data.download_cms_data() is None


# -- build_database (atomic write + plan_counties) ----------------------------

import sqlite3 as _sqlite3


def test_build_database_writes_plan_counties_and_is_atomic(tmp_path):
    db_path = tmp_path / "test.db"
    plans = [
        ("H1-001", "Foo", "Aetna", "HMO", 0.0, 0.0, 5000.0, 4.0, 1, "NY"),
        ("H2-002", "Bar", "Humana", "PPO", 45.0, 100.0, 6000.0, 3.5, 0, "FL"),
    ]
    plan_county_map = {"H1-001": {"36061", "36047"}, "H2-002": {"12086"}}
    zip_mappings = {"10001": ["H1-001"], "33101": ["H2-002"]}
    drugs = []  # empty drugs list is fine

    refresh_data.build_database(
        plans=plans,
        zip_mappings=zip_mappings,
        drugs=drugs,
        db_path=db_path,
        plan_county_map=plan_county_map,
    )

    assert db_path.exists()
    assert not (db_path.parent / (db_path.name + ".tmp")).exists()

    conn = _sqlite3.connect(str(db_path))
    try:
        plan_count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        zip_count = conn.execute("SELECT COUNT(*) FROM plan_zips").fetchone()[0]
        county_count = conn.execute("SELECT COUNT(*) FROM plan_counties").fetchone()[0]
        # Two plans, two ZIPs each mapped to one plan = 2 zip rows
        assert plan_count == 2
        assert zip_count == 2
        # H1-001 has 2 counties + H2-002 has 1 county = 3 county rows
        assert county_count == 3

        # Verify the atomic-write path didn't leave the .tmp file
        rows = conn.execute(
            "SELECT plan_id, state, fips_code FROM plan_counties ORDER BY plan_id, fips_code"
        ).fetchall()
        assert rows == [
            ("H1-001", "NY", "36047"),
            ("H1-001", "NY", "36061"),
            ("H2-002", "FL", "12086"),
        ]
    finally:
        conn.close()


def test_build_database_atomic_preserves_old_db_on_crash(tmp_path, monkeypatch):
    """If sqlite write fails mid-stream, the existing DB is untouched."""
    db_path = tmp_path / "test.db"
    # Seed an existing DB
    refresh_data.build_database(
        plans=[("OLD-001", "Old", "X", "HMO", 0.0, 0.0, 5000.0, 4.0, 1, "NY")],
        zip_mappings={"10001": ["OLD-001"]},
        drugs=[],
        db_path=db_path,
        plan_county_map={"OLD-001": {"36061"}},
    )

    # Now force a crash inside build_database after the temp file is written
    # but before the rename. Patch os.replace to raise.
    real_replace = refresh_data.os.replace

    def boom(*a, **kw):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(refresh_data.os, "replace", boom)
    with pytest.raises(RuntimeError):
        refresh_data.build_database(
            plans=[("NEW-001", "New", "X", "HMO", 0.0, 0.0, 5000.0, 4.0, 1, "NY")],
            zip_mappings={"10001": ["NEW-001"]},
            drugs=[],
            db_path=db_path,
            plan_county_map={"NEW-001": {"36061"}},
        )

    # The old DB should still be intact
    monkeypatch.setattr(refresh_data.os, "replace", real_replace)
    conn = _sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT plan_id FROM plans").fetchall()
        assert rows == [("OLD-001",)]
    finally:
        conn.close()
