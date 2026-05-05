# Real CMS Plan Catalog with Nationwide ZIP Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the seeded ~50-plan / 25-ZIP catalog with ~3,000 real CMS Medicare Advantage plans mapped to ~33,000 US ZIPs via the HUD ZIP↔county crosswalk, with a clean fallback ladder so the script still works offline.

**Architecture:** All work in `scripts/refresh_data.py`. Two new HTTP downloaders (`download_cms_data` is refactored for pagination and county codes; `download_hud_zip_county` is new), one pure join function (`build_zip_mappings`), one cache wrapper (`_load_or_fetch`), and an atomic-write helper for SQLite. Orchestration in `main()` degrades gracefully: HUD missing → seed ZIPs; CMS down → seed plans + seed ZIPs.

**Tech Stack:** Python 3.11+, `httpx`, `python-dotenv`, `sqlite3` (stdlib), `pytest`.

**Spec:** `docs/superpowers/specs/2026-05-04-cms-plan-catalog-design.md`

---

## File Map

**Modify:**
- `scripts/refresh_data.py` — add 4 new functions, refactor `download_cms_data` and `main`, change `build_database` to atomic write that also populates `plan_counties`
- `.env.example` — add `HUD_API_TOKEN=` with signup URL
- `README.md` — add a "Data refresh" subsection

**Create:**
- `scripts/__init__.py` — empty file, makes `scripts` an importable package so tests can `from scripts.refresh_data import ...`
- `healthflow/tests/test_zip_mappings.py` — pure-function tests for `build_zip_mappings`
- `healthflow/tests/test_refresh_downloaders.py` — mock-based tests for `_load_or_fetch`, `download_cms_data`, `download_hud_zip_county`

**Read-only references:**
- `healthflow/main.py:1-15` — load_dotenv pattern to mirror
- `scripts/refresh_data.py:31-80` — existing schema, no changes needed
- `scripts/refresh_data.py:441-496` — existing `build_database`, will be refactored

**Note on existing flag:** the script already has `--seed-only` (not `--use-seed` as the spec referenced). We keep `--seed-only` and add the two new flags (`--force-refresh`, `--verbose`) alongside it.

---

## Task 1: Make `scripts/` an importable package

**Files:**
- Create: `scripts/__init__.py`

The test files in Tasks 3–6 will need `from scripts.refresh_data import ...`. Without `__init__.py`, `scripts` isn't a Python package and the import fails when pytest runs from the project root.

- [ ] **Step 1: Create the empty package file**

```bash
touch scripts/__init__.py
```

- [ ] **Step 2: Verify the import works**

Run:
```bash
cd /Users/saidukamara/code/projects/health-insurance-agent
python -c "from scripts.refresh_data import SEED_PLANS; print(len(SEED_PLANS))"
```
Expected: a number around `50` printed, no error.

- [ ] **Step 3: Commit**

```bash
git add scripts/__init__.py
git commit -m "$(cat <<'EOF'
Make scripts/ a package so tests can import refresh_data

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire `.env` autoload and document `HUD_API_TOKEN`

**Files:**
- Modify: `scripts/refresh_data.py:13-22` (add `load_dotenv` import + call)
- Modify: `.env.example` (add HUD entry)

The script currently only reads env vars from the shell. Mirroring `healthflow/main.py:5-9`, we autoload `.env` so users can put `HUD_API_TOKEN` there and `make refresh-data` picks it up.

- [ ] **Step 1: Update `.env.example`**

Replace the current content of `.env.example` with:

```
# Required
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Optional — defaults shown
JWT_SECRET=healthflow-dev-secret-change-in-production
DATABASE_URL=sqlite+aiosqlite:///healthflow.db
REDIS_URL=redis://localhost:6379

# Optional — enables nationwide ZIP coverage in `make refresh-data`.
# Free signup: https://www.huduser.gov/portal/dataset/uspszip-api.html
# Without this, refresh-data falls back to ~25 hand-curated demo ZIPs.
HUD_API_TOKEN=
```

- [ ] **Step 2: Add `load_dotenv` to `scripts/refresh_data.py`**

Replace lines 13-22 of `scripts/refresh_data.py`:

```python
import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

# Load .env so HUD_API_TOKEN (and any other vars) are visible. Existing process
# env wins — useful when CI passes secrets explicitly.
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
```

(`os`, `defaultdict`, and `load_dotenv` are needed by later tasks; adding them now keeps the import block tidy.)

- [ ] **Step 3: Verify the script still runs**

Run:
```bash
python scripts/refresh_data.py --help
```
Expected: argparse help text printed, no import errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/refresh_data.py .env.example
git commit -m "$(cat <<'EOF'
Autoload .env in refresh_data and document HUD_API_TOKEN

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: TDD `build_zip_mappings` — pure join function

**Files:**
- Create: `healthflow/tests/test_zip_mappings.py`
- Modify: `scripts/refresh_data.py` (add the function near the other helpers, e.g. after `download_fda_drugs`)

`build_zip_mappings` is the heart of the new pipeline: given `plan_county_map: dict[plan_id, Iterable[county_fips]]` and `zip_county_map: dict[zip, Iterable[county_fips]]`, it returns `dict[zip, list[plan_id]]`.

It accepts **iterables** (not strictly sets) because the cache layer round-trips through JSON and may return lists.

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/test_zip_mappings.py`:

```python
"""Unit tests for scripts.refresh_data.build_zip_mappings."""

from scripts.refresh_data import build_zip_mappings


def test_build_zip_mappings_basic():
    plan_county_map = {
        "P1": {"36061"},          # Manhattan
        "P2": {"36061", "36047"}, # Manhattan + Brooklyn
        "P3": {"06001"},          # Connecticut, no NYC ZIPs
    }
    zip_county_map = {
        "10001": {"36061"},                    # Manhattan only
        "11201": {"36047"},                    # Brooklyn only
        "10004": {"36061", "36047"},           # straddles boroughs
    }
    result = build_zip_mappings(plan_county_map, zip_county_map)
    assert result == {
        "10001": ["P1", "P2"],
        "11201": ["P2"],
        "10004": ["P1", "P2"],
    }


def test_build_zip_mappings_empty_inputs():
    assert build_zip_mappings({}, {}) == {}
    assert build_zip_mappings({"P1": {"36061"}}, {}) == {}
    assert build_zip_mappings({}, {"10001": {"36061"}}) == {}


def test_build_zip_mappings_zip_with_no_plans_is_omitted():
    plan_county_map = {"P1": {"36061"}}
    zip_county_map = {
        "10001": {"36061"},   # has plan
        "99999": {"99999"},   # county not served by any plan
    }
    result = build_zip_mappings(plan_county_map, zip_county_map)
    assert "99999" not in result
    assert result == {"10001": ["P1"]}


def test_build_zip_mappings_accepts_lists_not_just_sets():
    """After a cache round-trip via JSON, sets become lists. Function must still work."""
    plan_county_map = {"P1": ["36061", "36047"]}
    zip_county_map = {"10001": ["36061"]}
    assert build_zip_mappings(plan_county_map, zip_county_map) == {"10001": ["P1"]}


def test_build_zip_mappings_dedupes_plans():
    """A ZIP touching two counties both served by the same plan should list it once."""
    plan_county_map = {"P1": {"A", "B"}}
    zip_county_map = {"10001": {"A", "B"}}
    assert build_zip_mappings(plan_county_map, zip_county_map) == {"10001": ["P1"]}


def test_build_zip_mappings_output_is_sorted():
    plan_county_map = {"P_z": {"X"}, "P_a": {"X"}, "P_m": {"X"}}
    zip_county_map = {"10001": {"X"}}
    assert build_zip_mappings(plan_county_map, zip_county_map) == {
        "10001": ["P_a", "P_m", "P_z"],
    }
```

- [ ] **Step 2: Run the tests, verify they fail**

Run:
```bash
pytest healthflow/tests/test_zip_mappings.py -v
```
Expected: all six tests fail with `ImportError: cannot import name 'build_zip_mappings'`.

- [ ] **Step 3: Implement `build_zip_mappings` in `scripts/refresh_data.py`**

Add this function after the existing `download_fda_drugs` function (around line 435, after the `# FDA Drug Data Downloader` block, before `# Database Builder`):

```python
# ---------------------------------------------------------------------------
# ZIP ↔ Plan Mapping Join
# ---------------------------------------------------------------------------

def build_zip_mappings(
    plan_county_map: dict,
    zip_county_map: dict,
) -> dict[str, list[str]]:
    """Join plan→counties and zip→counties into zip→plans.

    Accepts any iterable (set or list) as the inner collection — the cache
    layer may rehydrate sets as lists after a JSON round-trip.

    A ZIP that maps to no served counties is omitted from the output rather
    than mapping to an empty list.
    """
    county_to_plans: dict[str, set[str]] = defaultdict(set)
    for plan_id, counties in plan_county_map.items():
        for county in counties:
            county_to_plans[county].add(plan_id)

    zip_to_plans: dict[str, list[str]] = {}
    for zip_code, counties in zip_county_map.items():
        plan_ids: set[str] = set()
        for county in counties:
            plan_ids.update(county_to_plans.get(county, ()))
        if plan_ids:
            zip_to_plans[zip_code] = sorted(plan_ids)
    return zip_to_plans
```

- [ ] **Step 4: Run the tests, verify they pass**

Run:
```bash
pytest healthflow/tests/test_zip_mappings.py -v
```
Expected: all six tests pass.

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/test_zip_mappings.py scripts/refresh_data.py
git commit -m "$(cat <<'EOF'
Add build_zip_mappings: pure ZIP↔plan join

Joins a plan→counties index with a ZIP→counties crosswalk to produce the
ZIP→plans mapping that drives plan_zips. Accepts iterables (not just sets)
so it survives JSON cache round-trips.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: TDD `_load_or_fetch` cache wrapper

**Files:**
- Create: `healthflow/tests/test_refresh_downloaders.py`
- Modify: `scripts/refresh_data.py` (add cache helper near top, after imports)

`_load_or_fetch(key, ttl_days, fetch_fn, *, force=False)` reads `~/.cache/healthflow/<key>.json` if fresh, otherwise calls `fetch_fn()` and writes through.

`set` values returned by `fetch_fn` are converted to sorted lists at write time. Consumers (i.e. `build_zip_mappings`) accept either, so we don't need to rehydrate.

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/test_refresh_downloaders.py`:

```python
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
```

- [ ] **Step 2: Run the tests, verify they fail**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v
```
Expected: all eight tests fail with `ImportError: cannot import name '_load_or_fetch'`.

- [ ] **Step 3: Implement `_load_or_fetch` in `scripts/refresh_data.py`**

Add this block after `load_dotenv(override=False)` and before the schema (around line 30):

```python
# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "healthflow"


def _serialize_for_cache(obj):
    """Convert sets to sorted lists, recursively, so the result is JSON-safe."""
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, dict):
        return {k: _serialize_for_cache(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_cache(v) for v in obj]
    return obj


def _load_or_fetch(key: str, ttl_days: int, fetch_fn, *, force: bool = False):
    """Read ~/.cache/healthflow/<key>.json if present and within TTL; else call fetch_fn().

    On a fetcher hit, the result is JSON-serialized (sets → sorted lists) and written through.
    Returns whatever fetch_fn returned, or — on a cache hit — the JSON-rehydrated equivalent.
    Sets in the original return value come back as lists; consumers must accept iterables.
    Returns None (and does not cache) if fetch_fn returns None.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{key}.json"

    if not force and cache_path.exists():
        age_seconds = time.time() - cache_path.stat().st_mtime
        if age_seconds < ttl_days * 86400:
            try:
                with cache_path.open() as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"Cache file {cache_path} unreadable ({e}); refetching.")
                cache_path.unlink(missing_ok=True)

    result = fetch_fn()
    if result is not None:
        try:
            with cache_path.open("w") as fh:
                json.dump(_serialize_for_cache(result), fh)
        except OSError as e:
            logger.warning(f"Failed to write cache {cache_path}: {e}")
    return result
```

- [ ] **Step 4: Run the tests, verify they pass**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v
```
Expected: all eight tests pass.

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/test_refresh_downloaders.py scripts/refresh_data.py
git commit -m "$(cat <<'EOF'
Add _load_or_fetch cache wrapper for refresh data

Caches downloader results to ~/.cache/healthflow/<key>.json with TTL.
Sets are serialized as sorted lists; corrupt or stale cache files are
treated as misses. Bypassed via force=True.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: TDD `download_hud_zip_county`

**Files:**
- Modify: `healthflow/tests/test_refresh_downloaders.py` (append HUD tests)
- Modify: `scripts/refresh_data.py` (add the function near the existing downloaders)

HUD's USPS Crosswalk API returns a JSON envelope shaped roughly:

```json
{
  "data": {
    "year": "2024",
    "quarter": "1",
    "results": [
      {"zip": "10001", "geoid": "36061", "res_ratio": "1", "city": "NEW YORK", "state": "NY"},
      ...
    ]
  }
}
```

We extract `zip` and `geoid` (county FIPS) and ignore everything else.

- [ ] **Step 1: Append the failing tests**

Add at the end of `healthflow/tests/test_refresh_downloaders.py`:

```python
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
```

- [ ] **Step 2: Run the tests, verify they fail**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v -k hud
```
Expected: 4 tests fail. Most likely with `AttributeError: module 'scripts.refresh_data' has no attribute 'download_hud_zip_county'` or `httpx`.

- [ ] **Step 3: Add `httpx` to module-level imports if not already imported**

Check the top of `scripts/refresh_data.py` for `import httpx`. The existing `download_cms_data` does `import httpx` lazily inside the function. We want to keep that lazy import there (so seed-only paths don't require httpx) but ALSO expose the symbol at module level for the new HUD function and for tests to monkeypatch. The cleanest pattern:

After the other top-level imports, add:

```python
try:
    import httpx
except ImportError:
    httpx = None  # downloaders return None gracefully when httpx isn't installed
```

Then update the existing `download_cms_data` to remove its inner `import httpx` (use the module-level one) and check `if httpx is None: return None` at the top instead. We'll touch this in Task 6 — for now, just add the module-level import.

- [ ] **Step 4: Implement `download_hud_zip_county`**

Add this function in `scripts/refresh_data.py` right after the FDA downloader (just before `build_zip_mappings`):

```python
# ---------------------------------------------------------------------------
# HUD ZIP ↔ County Crosswalk Downloader
# ---------------------------------------------------------------------------

HUD_API_URL = "https://www.huduser.gov/hudapi/public/usps"


def download_hud_zip_county() -> dict[str, set[str]] | None:
    """Download the HUD USPS ZIP↔county crosswalk for all US ZIPs.

    Returns dict[zip_code, set[county_fips]] or None on failure.
    Falls back silently (returns None) if HUD_API_TOKEN is not set or if
    httpx isn't available — the orchestrator then uses SEED_ZIP_MAPPINGS.
    """
    token = os.environ.get("HUD_API_TOKEN")
    if not token:
        logger.warning(
            "HUD_API_TOKEN not set; using seed ZIP mappings (~25 ZIPs covered). "
            "Set the token in .env to enable nationwide ZIPs."
        )
        return None
    if httpx is None:
        logger.warning("httpx not installed — skipping HUD download. Using seed ZIP mappings.")
        return None

    logger.info("Downloading HUD ZIP↔county crosswalk (national)...")
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(
                HUD_API_URL,
                params={"type": 2, "query": "All"},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:
        logger.warning(f"HUD download failed: {e}. Falling back to seed ZIP mappings.")
        return None

    results = (payload or {}).get("data", {}).get("results", []) or []
    zip_county_map: dict[str, set[str]] = defaultdict(set)
    for row in results:
        zip_code = (row.get("zip") or "").strip()
        county = (row.get("geoid") or "").strip()
        if zip_code and county:
            zip_county_map[zip_code].add(county)

    logger.info(f"HUD: {len(zip_county_map)} ZIPs mapped across {sum(len(v) for v in zip_county_map.values())} ZIP-county pairs.")
    return dict(zip_county_map)
```

- [ ] **Step 5: Run the tests, verify they pass**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v -k hud
```
Expected: all 4 HUD tests pass. The earlier 8 cache tests should still pass too:

```bash
pytest healthflow/tests/test_refresh_downloaders.py -v
```
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add healthflow/tests/test_refresh_downloaders.py scripts/refresh_data.py
git commit -m "$(cat <<'EOF'
Add download_hud_zip_county for nationwide ZIP↔county crosswalk

Uses HUD User API (type=2 query=All) with bearer token from
HUD_API_TOKEN. Returns None gracefully if the token is unset or the
network fails, so refresh-data can degrade to seed mappings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: TDD paged refactor of `download_cms_data`

**Files:**
- Modify: `healthflow/tests/test_refresh_downloaders.py` (append CMS tests)
- Modify: `scripts/refresh_data.py:311-368` (replace existing `download_cms_data`)

The current implementation makes one capped 5,000-row request and doesn't request `county_code`. We refactor to:
1. Add `county_code` to `$select`.
2. Page via `$offset`.
3. Return `(plans: list[tuple], plan_county_map: dict[plan_id, set[county_fips]])`.
4. Dedupe plans by `plan_id` (each plan appears once per service county in the dataset).

Return contract change: previously `list[tuple] | None`, now `tuple[list[tuple], dict[str, set[str]]] | None`. Callers in `main()` will be updated in Task 8.

- [ ] **Step 1: Append the failing tests**

Add at the end of `healthflow/tests/test_refresh_downloaders.py`:

```python
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
    page1 = [
        {"contract_id": "H1", "plan_id": "001", "plan_name": "Foo", "organization_name": "Aetna",
         "plan_type": "HMO", "monthly_consolidated_premium": "0", "annual_drug_deductible": "0",
         "out_of_pocket_maximum": "5000", "overall_star_rating": "4", "drug_coverage": "Yes",
         "state": "NY", "county_code": "36061"},
        {"contract_id": "H1", "plan_id": "001", "plan_name": "Foo", "organization_name": "Aetna",
         "plan_type": "HMO", "monthly_consolidated_premium": "0", "annual_drug_deductible": "0",
         "out_of_pocket_maximum": "5000", "overall_star_rating": "4", "drug_coverage": "Yes",
         "state": "NY", "county_code": "36047"},  # same plan, different county
    ]
    page2 = [
        {"contract_id": "H2", "plan_id": "002", "plan_name": "Bar", "organization_name": "Humana",
         "plan_type": "PPO", "monthly_consolidated_premium": "45", "annual_drug_deductible": "100",
         "out_of_pocket_maximum": "6000", "overall_star_rating": "3.5", "drug_coverage": "No",
         "state": "FL", "county_code": "12086"},
    ]
    client = _MockCmsClient([page1, page2, []])  # third call returns empty → loop stops
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
```

- [ ] **Step 2: Run the tests, verify they fail**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v -k cms
```
Expected: 6 CMS tests fail. Existing `download_cms_data` returns `list[tuple]` not a tuple, and doesn't request `county_code`, so most tests will fail on shape mismatch.

- [ ] **Step 3: Replace `download_cms_data` in `scripts/refresh_data.py`**

Find the existing `download_cms_data` function (lines 311-368) and replace the entire function with:

```python
def download_cms_data() -> tuple[list[tuple], dict[str, set[str]]] | None:
    """Download CMS Medicare Advantage Plan Landscape, paged.

    Returns (plans, plan_county_map) where plans is a list of tuples in the
    column order build_database expects, and plan_county_map maps plan_id to
    the set of county FIPS codes that plan serves. Returns None on first-page
    failure; on later-page failure, returns what was collected.
    """
    if httpx is None:
        logger.warning("httpx not installed — skipping CMS download. Using seed data.")
        return None

    logger.info("Downloading CMS Medicare Advantage plan landscape (paged)...")
    url = "https://data.cms.gov/resource/jfhb-kvhx.json"
    select = (
        "contract_id,plan_id,plan_name,organization_name,plan_type,"
        "monthly_consolidated_premium,annual_drug_deductible,out_of_pocket_maximum,"
        "overall_star_rating,drug_coverage,state,county_code"
    )

    plans_by_id: dict[str, tuple] = {}
    plan_county_map: dict[str, set[str]] = defaultdict(set)
    page_size = 5000
    offset = 0

    while True:
        params = {"$limit": page_size, "$offset": offset, "$select": select}
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            if not plans_by_id:
                logger.warning(f"CMS download failed on first page ({e}). Using seed data.")
                return None
            logger.warning(
                f"CMS download failed at offset {offset} ({e}). "
                f"Using {len(plans_by_id)} plans collected so far."
            )
            break

        if not data:
            break

        for row in data:
            try:
                plan_id = f"{row.get('contract_id', '')}-{row.get('plan_id', '')}"
                if plan_id == "-":
                    continue
                county_code = (row.get("county_code") or "").strip()
                if county_code:
                    plan_county_map[plan_id].add(county_code)
                if plan_id in plans_by_id:
                    continue  # plan already captured; only county is new
                premium = float(row.get("monthly_consolidated_premium", 0) or 0)
                deductible = float(row.get("annual_drug_deductible", 0) or 0)
                oop = float(row.get("out_of_pocket_maximum", 6700) or 6700)
                star_str = (row.get("overall_star_rating") or "").strip()
                star = float(star_str) if star_str and star_str != "Not enough data" else 3.0
                drug = 1 if str(row.get("drug_coverage", "")).lower() in ("yes", "true", "1") else 0
                plans_by_id[plan_id] = (
                    plan_id,
                    row.get("plan_name", "Unknown Plan"),
                    row.get("organization_name", "Unknown"),
                    row.get("plan_type", "HMO"),
                    premium,
                    deductible,
                    oop,
                    star,
                    drug,
                    row.get("state", ""),
                )
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping malformed row: {e}")
                continue

        if len(data) < page_size:
            break
        offset += page_size

    logger.info(
        f"CMS: {len(plans_by_id)} plans across "
        f"{sum(len(v) for v in plan_county_map.values())} plan-county pairs."
    )
    return list(plans_by_id.values()), dict(plan_county_map)
```

- [ ] **Step 4: Run the tests, verify they pass**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v
```
Expected: all tests pass (12 from earlier + 6 new CMS = 18).

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/test_refresh_downloaders.py scripts/refresh_data.py
git commit -m "$(cat <<'EOF'
Refactor download_cms_data: paged + county service areas

Pages through Socrata via $offset, requests county_code, dedupes plans by
plan_id, and accumulates a plan→counties map for the ZIP join. Returns
None on first-page failure; partial results on later-page failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Atomic SQLite write + populate `plan_counties`

**Files:**
- Modify: `scripts/refresh_data.py:441-496` (refactor `build_database`)

`build_database` currently writes to `db_path` directly. We change it to write to `<db_path>.tmp` and `os.replace()` at the end so a mid-run crash leaves the previous DB intact. We also populate the `plan_counties` table from the new `plan_county_map`. The table's columns are `(plan_id, state, county, fips_code)`; we have `plan_id`, the plan's `state` (from the plans tuple), and the county FIPS — `county` (the human name) is unavailable from CMS Socrata, so we leave it as an empty string. `plan_counties` is currently unused by the FastAPI surface, so this is forward-compatible groundwork, not a contract change.

This task changes the signature of `build_database` (adds `plan_county_map` arg). Callers (`main()`) are updated in Task 8.

- [ ] **Step 1: Write a test for atomic write + plan_counties population**

Append to `healthflow/tests/test_refresh_downloaders.py`:

```python
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
```

- [ ] **Step 2: Run the tests, verify they fail**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v -k build_database
```
Expected: both tests fail. The current `build_database` doesn't accept `plan_county_map` and doesn't write atomically.

- [ ] **Step 3: Refactor `build_database`**

Replace the existing `build_database` function (around lines 441-496) with:

```python
def build_database(
    plans: list[tuple],
    zip_mappings: dict[str, list[str]],
    drugs: list[tuple],
    db_path: Path = DB_PATH,
    plan_county_map: dict[str, set[str]] | None = None,
) -> None:
    """Build the SQLite database atomically.

    Writes to <db_path>.tmp, then os.replace()s to db_path so a mid-run
    crash leaves any previous DB intact.
    """
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(str(tmp_path))
    try:
        conn.executescript(SCHEMA_SQL)

        conn.executemany(
            """
            INSERT OR IGNORE INTO plans
                (plan_id, plan_name, organization, plan_type, monthly_premium,
                 annual_deductible, out_of_pocket_max, star_rating, drug_coverage, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            plans,
        )

        # plan_zips
        zip_rows = [
            (plan_id, zip_code)
            for zip_code, plan_ids in zip_mappings.items()
            for plan_id in plan_ids
        ]
        conn.executemany(
            "INSERT INTO plan_zips (plan_id, zip_code) VALUES (?, ?)",
            zip_rows,
        )

        # plan_counties
        if plan_county_map:
            plan_state = {p[0]: p[9] for p in plans}  # plan_id -> state
            county_rows = [
                (plan_id, plan_state.get(plan_id, ""), "", fips)
                for plan_id, counties in plan_county_map.items()
                for fips in counties
            ]
            conn.executemany(
                "INSERT INTO plan_counties (plan_id, state, county, fips_code) VALUES (?, ?, ?, ?)",
                county_rows,
            )

        # drugs
        conn.executemany(
            """
            INSERT INTO drugs
                (name, generic_name, brand_name, ndc, dosage_form,
                 tier_generic, copay_hmo, copay_ppo, prior_auth, quantity_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            drugs,
        )

        conn.commit()

        plan_count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        drug_count = conn.execute("SELECT COUNT(*) FROM drugs").fetchone()[0]
        zip_count = conn.execute("SELECT COUNT(DISTINCT zip_code) FROM plan_zips").fetchone()[0]
        county_count = conn.execute("SELECT COUNT(*) FROM plan_counties").fetchone()[0]
    finally:
        conn.close()

    os.replace(str(tmp_path), str(db_path))

    print(
        f"Loaded {plan_count} plans, {drug_count} drugs, "
        f"{zip_count} zips, {county_count} plan-county rows"
    )
    logger.info(
        f"Database built: {plan_count} plans, {drug_count} drugs, "
        f"{zip_count} zips, {county_count} plan-county rows"
    )
    logger.info(f"Saved to: {db_path}")
```

- [ ] **Step 4: Run the tests, verify they pass**

Run:
```bash
pytest healthflow/tests/test_refresh_downloaders.py -v
```
Expected: all tests pass (the previous 18 + 2 new = 20).

Also run the existing plan-database tests to confirm we haven't broken downstream consumers:

```bash
pytest healthflow/tests/test_plan_database.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/test_refresh_downloaders.py scripts/refresh_data.py
git commit -m "$(cat <<'EOF'
Atomic SQLite write + populate plan_counties

build_database now writes to <db_path>.tmp and os.replace()s on success,
so a mid-run crash leaves the previous DB intact. Also populates the
previously-empty plan_counties table from the new plan_county_map.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Wire `main()` orchestrator with full fallback ladder

**Files:**
- Modify: `scripts/refresh_data.py:503-541` (rewrite `main`)

Now the orchestrator stitches everything together: cache-wrapped CMS download, cache-wrapped HUD download, build_zip_mappings, build_database. New CLI flags: `--force-refresh` and `--verbose` alongside the existing `--seed-only`.

- [ ] **Step 1: Replace `main`**

Replace lines 503-541 of `scripts/refresh_data.py`:

```python
def main():
    parser = argparse.ArgumentParser(description="Refresh healthflow_data.db")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Use curated seed data only (no downloads). Good for CI/testing.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass the local cache for both CMS and HUD downloads.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (pagination, cache hits, row counts).",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help=f"Output database path (default: {DB_PATH})",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    if args.seed_only:
        logger.info("Using seed data only (--seed-only).")
        plans = SEED_PLANS
        drugs = SEED_DRUGS
        zip_mappings = SEED_ZIP_MAPPINGS
        plan_county_map: dict[str, set[str]] | None = None
        build_database(plans, zip_mappings, drugs, db_path=args.db_path, plan_county_map=plan_county_map)
        return

    logger.info("Attempting to download real data from CMS, HUD, and FDA...")

    cms_result = _load_or_fetch(
        "cms_landscape", ttl_days=7,
        fetch_fn=download_cms_data, force=args.force_refresh,
    )
    drugs = _load_or_fetch(
        "fda_drugs", ttl_days=30,
        fetch_fn=download_fda_drugs, force=args.force_refresh,
    )
    zip_county_map = _load_or_fetch(
        "hud_zip_county", ttl_days=30,
        fetch_fn=download_hud_zip_county, force=args.force_refresh,
    )

    if cms_result is None:
        logger.info("Falling back to seed plan data (CMS download failed).")
        plans = SEED_PLANS
        plan_county_map = None
        zip_mappings = SEED_ZIP_MAPPINGS
    else:
        plans, plan_county_map = cms_result
        # Cache may have rehydrated tuples as lists; coerce back.
        plans = [tuple(p) for p in plans]
        # Cache may have rehydrated set values as lists; build_zip_mappings accepts both.
        if zip_county_map:
            zip_mappings = build_zip_mappings(plan_county_map, zip_county_map)
            if not zip_mappings:
                logger.warning(
                    "build_zip_mappings produced empty result; "
                    "falling back to seed ZIP mappings."
                )
                zip_mappings = SEED_ZIP_MAPPINGS
        else:
            logger.info("Falling back to seed ZIP mappings (HUD unavailable).")
            zip_mappings = SEED_ZIP_MAPPINGS

    if drugs is None:
        logger.info("Falling back to seed drug data.")
        drugs = SEED_DRUGS
    else:
        drugs = [tuple(d) for d in drugs]  # cache JSON round-trip

    build_database(
        plans, zip_mappings, drugs,
        db_path=args.db_path,
        plan_county_map=plan_county_map,
    )
```

- [ ] **Step 2: Run all tests to make sure nothing regressed**

```bash
pytest healthflow/tests/test_refresh_downloaders.py healthflow/tests/test_zip_mappings.py healthflow/tests/test_plan_database.py -v
```
Expected: all pass.

- [ ] **Step 3: Verify `--seed-only` still works end-to-end**

```bash
rm -f healthflow_data.db
python scripts/refresh_data.py --seed-only --db-path /tmp/healthflow_seed.db
sqlite3 /tmp/healthflow_seed.db "SELECT COUNT(*) FROM plans;"
```
Expected: a number around `50`.

- [ ] **Step 4: Verify `--help` shows all new flags**

```bash
python scripts/refresh_data.py --help
```
Expected output includes `--seed-only`, `--force-refresh`, `--verbose`, `--db-path`.

- [ ] **Step 5: Commit**

```bash
git add scripts/refresh_data.py
git commit -m "$(cat <<'EOF'
Wire main() orchestrator with cache and fallback ladder

Routes CMS, HUD, and FDA downloads through _load_or_fetch with TTLs
(7 days for CMS/FDA, 30 days for HUD). On any download failure the
script degrades gracefully: missing CMS → seed plans + seed ZIPs;
missing HUD → CMS plans + seed ZIPs. Adds --force-refresh and --verbose
flags alongside the existing --seed-only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Update README with data-refresh section

**Files:**
- Modify: `README.md` (add a Data refresh subsection)

- [ ] **Step 1: Find the right insertion point**

Run:
```bash
grep -n "^##\|^###" README.md | head -30
```
Pick a section heading that looks like the right place — typically after a "Setup" or "Getting started" section, before "Architecture" or "Testing." If unclear, append to the end of the file under a new top-level `## Data` heading.

- [ ] **Step 2: Add the section**

Insert this content at the chosen location:

```markdown
## Data refresh

`make refresh-data` rebuilds `healthflow_data.db` from real public sources:

- **CMS Medicare Advantage Plan Landscape** (no auth) — every active MA plan
  in the country, ~3,000 plans across all carriers and states.
- **HUD USPS ZIP↔county crosswalk** (free token; sign up at
  https://www.huduser.gov/portal/dataset/uspszip-api.html) — joins CMS county
  service areas to ~33,000 US ZIPs.
- **FDA NDC directory** — drug catalog used by cost calculations.

Set `HUD_API_TOKEN=<token>` in `.env` to enable nationwide ZIP coverage.
Without it, the refresh still works but falls back to ~25 hand-curated demo
ZIPs.

CLI flags:

```sh
python scripts/refresh_data.py                  # default — try real data, fall back to seed
python scripts/refresh_data.py --force-refresh  # ignore the local cache
python scripts/refresh_data.py --seed-only      # skip network entirely
python scripts/refresh_data.py --verbose        # debug logging
```

Cache lives in `~/.cache/healthflow/`. CMS and FDA TTL is 7/30 days; HUD is
30 days (HUD updates quarterly).

### Manual smoke check after a refresh

```sh
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plans;"           # ~3,000 with HUD token
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_counties;"   # ~30,000
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_zips;"       # ~400,000

sqlite3 healthflow_data.db <<SQL
SELECT p.plan_name, p.organization
FROM plans p JOIN plan_zips z ON p.plan_id = z.plan_id
WHERE z.zip_code = '10001'
LIMIT 20;
SQL
```
```

- [ ] **Step 3: Verify the README still renders**

Run:
```bash
head -100 README.md | tail -60
```
Eyeball the section — make sure the markdown headings nest correctly and the code blocks aren't mangled.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
README: document data refresh, HUD token, and manual smoke check

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: End-to-end verification (manual)

**Files:** none changed — this is a smoke check.

This task isn't code; it's the moment of truth. Run the full pipeline once with a real HUD token and confirm the DB looks right.

- [ ] **Step 1: Confirm `HUD_API_TOKEN` is in `.env`**

```bash
grep -c "^HUD_API_TOKEN=" .env
```
Expected: `1`. If not, add the token to `.env` (don't paste it in a chat).

- [ ] **Step 2: Run a full refresh**

```bash
python scripts/refresh_data.py --force-refresh --verbose 2>&1 | tail -40
```
Expected (rough order of log lines):
- "Downloading CMS Medicare Advantage plan landscape (paged)..."
- One or more pagination INFO lines
- "CMS: ~3000 plans across ~30000 plan-county pairs."
- "Downloading HUD ZIP↔county crosswalk (national)..."
- "HUD: ~33000 ZIPs mapped across ~40000 ZIP-county pairs."
- "Database built: ~3000 plans, ~XXX drugs, ~33000 zips, ~30000 plan-county rows"

- [ ] **Step 3: Run the SQL smoke checks**

```bash
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plans;"
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_counties;"
sqlite3 healthflow_data.db "SELECT COUNT(*) FROM plan_zips;"
sqlite3 healthflow_data.db "SELECT plan_name FROM plans p JOIN plan_zips z ON p.plan_id=z.plan_id WHERE z.zip_code='10001' LIMIT 20;"
sqlite3 healthflow_data.db "SELECT plan_name FROM plans p JOIN plan_zips z ON p.plan_id=z.plan_id WHERE z.zip_code='90210' LIMIT 20;"
sqlite3 healthflow_data.db "SELECT plan_name FROM plans p JOIN plan_zips z ON p.plan_id=z.plan_id WHERE z.zip_code='59718' LIMIT 20;"  -- Bozeman MT, not in seed
```
Expected:
- `plans` count in the low thousands
- `plan_counties` and `plan_zips` counts well above the seed equivalents
- ZIP 10001 returns more than the ~6 hand-seeded NYC plans
- ZIP 90210 returns several CA plans
- ZIP 59718 (Bozeman, Montana — not in `SEED_ZIP_MAPPINGS`) returns plans, proving nationwide coverage works

- [ ] **Step 4: Smoke-test the compare page in the browser**

```bash
make dev
```
Navigate to the Plan comparison page, enter a non-seed ZIP (e.g. 59718), confirm the comparison runs and returns plans.

- [ ] **Step 5: If everything looks good, no commit needed.**

This is a verification task. If something failed, file the bug and pick up the relevant earlier task.

---

## Self-review notes

- **Spec coverage:** all sections of the spec have a task. Architecture → Tasks 3-7. Data flow / CMS pagination → Task 6. Data flow / HUD → Task 5. Caching → Task 4. Build join → Task 3. Atomic write + plan_counties → Task 7. Error handling fallback ladder → Task 8. CLI flags → Task 8. Configuration / .env → Task 2. Testing → Tasks 3-7 (unit + mock); Task 10 (manual smoke). README → Task 9.
- **Existing test suite:** Task 8 step 2 reruns the existing `test_plan_database.py` to confirm no regression.
- **Type/signature consistency:** `download_cms_data` returns `tuple[list[tuple], dict[str, set[str]]] | None` (Task 6). Cache may rehydrate the tuple as a list and the inner sets as lists; Task 8 main() coerces tuples back and `build_zip_mappings` (Task 3) accepts iterables. `build_database` adds `plan_county_map` keyword arg (Task 7); Task 8 main() passes it.
- **Out-of-scope reminders:** no UI changes, no FastAPI surface changes, no new schema fields. The plan stays inside `scripts/refresh_data.py` plus its tests.
