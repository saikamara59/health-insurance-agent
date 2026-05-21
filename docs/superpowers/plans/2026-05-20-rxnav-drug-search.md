# RxNav Drug Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an async RxNav HTTP client (`RxNavClient`) with 24-hour disk caching plus one auth-gated endpoint `GET /drugs/search?q=...&limit=...` that returns drug autocomplete suggestions from the NLM RxNorm REST API.

**Architecture:** A single new client module in `healthflow/tools/`, one new router file in `healthflow/api/`, and three new Pydantic schemas. No SQLAlchemy changes, no agent changes, no PHI flows. Silent-fail on RxNav errors (autocomplete returns `[]`, never a 500).

**Tech Stack:** Python 3.11, FastAPI, httpx (async, already a dep), Pydantic 2, RxNav REST API (`https://rxnav.nlm.nih.gov/REST/`). Tests use `httpx.MockTransport` for offline unit tests.

**Spec:** `docs/superpowers/specs/2026-05-20-rxnav-drug-search-design.md`

---

## File Structure

**New files:**
- `healthflow/tools/rxnav_client.py` — `RxNavClient` async class, `DrugMatch` dataclass, disk cache helpers.
- `healthflow/api/drug_router.py` — `drug_router = APIRouter(prefix="/drugs", tags=["drugs"])` + `GET /drugs/search`.
- `healthflow/tests/tools/test_rxnav_client.py` — 5 client unit tests using `httpx.MockTransport`.
- `healthflow/tests/api/test_drug_router.py` — 4 endpoint tests using the existing `client` fixture.
- `healthflow/tests/integration/test_rxnav_live.py` — 1 opt-in live test, `skipif`-gated.

**Modified files:**
- `healthflow/models/schemas.py` — add `DrugMatchModel` and `DrugSearchResponse`.
- `healthflow/main.py` — `from healthflow.api.drug_router import drug_router` + `app.include_router(drug_router)`.
- `README.md` — add `GET /drugs/search` to the endpoints section; add RxNorm/RxNav to the "Real Health Data" table; bump test counts.
- `.claude/skills/healthflow-security/SKILL.md` — one rule on the no-PHI / no-query-logging posture for RxNav.

**Untouched:** `cost_estimator.py`, `formulary_checker.py`, `drug_database.py`, any agent, models.py, dependencies.py. ACA-related files don't exist and aren't created.

---

## Task 0: Baseline + branch

**Files:** none (operations only).

- [ ] **Step 1: Confirm clean baseline**

Run: `git status`
Expected: `nothing to commit, working tree clean` on branch `main`.

- [ ] **Step 2: Capture baseline test count**

Run: `make test 2>&1 | tail -3`
Expected: `601 passed` (record the exact number; previous sub-projects landed at 601).

- [ ] **Step 3: Create the feature branch**

Run: `git checkout -b rxnav-drug-search`
Expected: switched to a new branch.

---

## Task 1: `RxNavClient` (async client + disk cache + 5 unit tests)

**Files:**
- Create: `healthflow/tools/rxnav_client.py`
- Test: `healthflow/tests/tools/test_rxnav_client.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/tools/test_rxnav_client.py`:

```python
"""RxNavClient unit tests — all HTTP stubbed via httpx.MockTransport,
no live network calls in CI.
"""
import json
import os
import pytest
import httpx

from healthflow.tools.rxnav_client import RxNavClient, DrugMatch


_METFORMIN_EXACT_PAYLOAD = {
    "drugGroup": {
        "name": "metformin",
        "conceptGroup": [
            {
                "tty": "SCD",
                "conceptProperties": [
                    {
                        "rxcui": "860975",
                        "name": "Metformin hydrochloride 500 MG Oral Tablet",
                        "synonym": "",
                        "tty": "SCD",
                    }
                ],
            },
            {
                "tty": "SBD",
                "conceptProperties": [
                    {
                        "rxcui": "861007",
                        "name": "Glucophage 500 MG Oral Tablet",
                        "synonym": "",
                        "tty": "SBD",
                    }
                ],
            },
        ],
    }
}


_EMPTY_EXACT_PAYLOAD = {"drugGroup": {"name": "metfromn", "conceptGroup": []}}


_APPROXIMATE_PAYLOAD = {
    "approximateGroup": {
        "candidate": [
            {
                "rxcui": "860975",
                "name": "Metformin hydrochloride 500 MG Oral Tablet",
                "score": "100",
                "rank": "1",
                "tty": "SCD",
            }
        ]
    }
}


def _mock_transport(responses):
    """Build an httpx.MockTransport from a list of (status, json) tuples,
    in the order they should be served."""
    iterator = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        status, payload = next(iterator)
        return httpx.Response(status_code=status, json=payload)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_search_returns_matches_for_known_drug(tmp_path):
    transport = _mock_transport([(200, _METFORMIN_EXACT_PAYLOAD)])
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    matches = await client.search("metformin", limit=10)

    assert len(matches) == 2
    assert matches[0].rxcui == "860975"
    assert matches[0].term_type == "SCD"
    assert matches[0].is_brand is False
    assert matches[1].rxcui == "861007"
    assert matches[1].term_type == "SBD"
    assert matches[1].is_brand is True
    await http_client.aclose()


@pytest.mark.asyncio
async def test_search_falls_back_to_approximate_when_empty(tmp_path):
    transport = _mock_transport([
        (200, _EMPTY_EXACT_PAYLOAD),
        (200, _APPROXIMATE_PAYLOAD),
    ])
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    matches = await client.search("metfromn", limit=10)

    assert len(matches) == 1
    assert matches[0].rxcui == "860975"
    assert matches[0].term_type == "SCD"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_search_returns_empty_on_timeout(tmp_path, caplog):
    def raise_timeout(request):
        raise httpx.ConnectTimeout("simulated timeout")

    transport = httpx.MockTransport(raise_timeout)
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    import logging
    with caplog.at_level(logging.WARNING, logger="healthflow.tools.rxnav_client"):
        matches = await client.search("metformin", limit=10)

    assert matches == []
    assert any("rxnav.search_exact failed" in r.getMessage() for r in caplog.records)
    await http_client.aclose()


@pytest.mark.asyncio
async def test_cache_hit_skips_http(tmp_path):
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, json=_METFORMIN_EXACT_PAYLOAD)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    first = await client.search("metformin", limit=10)
    second = await client.search("metformin", limit=10)

    assert call_count["n"] == 1
    assert len(first) == 2
    assert first == second
    await http_client.aclose()


@pytest.mark.asyncio
async def test_cache_miss_after_ttl(tmp_path):
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, json=_METFORMIN_EXACT_PAYLOAD)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    await client.search("metformin", limit=10)
    assert call_count["n"] == 1

    # Backdate every cache file by 25 hours so it counts as expired.
    backdated = (
        os.path.getmtime(tmp_path.iterdir().__next__())  # any cache file
        - 25 * 3600
    )
    for f in tmp_path.iterdir():
        if f.suffix == ".json":
            os.utime(f, (backdated, backdated))

    await client.search("metformin", limit=10)
    assert call_count["n"] == 2
    await http_client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/tools/test_rxnav_client.py -v`
Expected: 5 errors, all `ModuleNotFoundError: No module named 'healthflow.tools.rxnav_client'`.

- [ ] **Step 3: Implement `RxNavClient`**

Create `healthflow/tools/rxnav_client.py`:

```python
"""Async client for the NLM RxNav REST API.

Single responsibility: ask RxNav for drug matches, cache the answer on disk,
return them. Silent-fail on any network error or upstream 4xx/5xx — returns []
rather than raising. Autocomplete must never crash a request.
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrugMatch:
    rxcui: str
    name: str
    term_type: str            # RxNorm TTY: "SBD", "SCD", "IN", "PIN", "BN", etc.
    is_brand: bool            # True if term_type in {"SBD", "BN"}


class RxNavClient:
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"
    DEFAULT_TIMEOUT_SECONDS = 5.0
    CACHE_TTL_SECONDS = 86_400  # 24h
    _BRAND_TTYS = frozenset({"SBD", "BN"})

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        cache_dir: Path | None = None,
    ):
        self._http = http_client
        self._owns_http = http_client is None
        self._cache_dir = cache_dir or (
            Path.home() / ".cache" / "healthflow" / "rxnav"
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> "RxNavClient":
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS)
        return self

    async def __aexit__(self, *_):
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def search(self, query: str, *, limit: int = 10) -> list[DrugMatch]:
        cache_key = self._cache_key("search", query, limit)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [DrugMatch(**m) for m in cached]

        matches = await self._search_exact(query, limit)
        if not matches:
            matches = await self._search_approximate(query, limit)

        self._cache_put(cache_key, [m.__dict__ for m in matches])
        return matches

    async def _search_exact(self, query: str, limit: int) -> list[DrugMatch]:
        try:
            resp = await self._http.get(
                f"{self.BASE_URL}/drugs.json", params={"name": query}
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("rxnav.search_exact failed: %s", e)
            return []

        out: list[DrugMatch] = []
        for group in (data.get("drugGroup") or {}).get("conceptGroup") or []:
            tty = group.get("tty", "")
            for cp in group.get("conceptProperties") or []:
                rxcui = cp.get("rxcui")
                name = cp.get("name") or cp.get("synonym")
                if not rxcui or not name:
                    continue
                out.append(DrugMatch(
                    rxcui=str(rxcui),
                    name=name,
                    term_type=tty,
                    is_brand=tty in self._BRAND_TTYS,
                ))
                if len(out) >= limit:
                    return out
        return out

    async def _search_approximate(self, query: str, limit: int) -> list[DrugMatch]:
        try:
            resp = await self._http.get(
                f"{self.BASE_URL}/approximateTerm.json",
                params={"term": query, "maxEntries": limit},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("rxnav.search_approximate failed: %s", e)
            return []

        candidates = (data.get("approximateGroup") or {}).get("candidate") or []
        out: list[DrugMatch] = []
        for c in candidates[:limit]:
            rxcui = c.get("rxcui")
            name = c.get("name")
            if not rxcui or not name:
                continue
            tty = c.get("tty", "")
            out.append(DrugMatch(
                rxcui=str(rxcui),
                name=name,
                term_type=tty,
                is_brand=tty in self._BRAND_TTYS,
            ))
        return out

    def _cache_key(self, *parts: object) -> str:
        h = hashlib.sha256(":".join(str(p).lower() for p in parts).encode())
        return h.hexdigest()[:32]

    def _cache_get(self, key: str) -> list[dict] | None:
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.CACHE_TTL_SECONDS:
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    def _cache_put(self, key: str, value: list[dict]) -> None:
        path = self._cache_dir / f"{key}.json"
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(value))
            tmp.replace(path)
        except OSError as e:
            logger.warning("rxnav.cache_put failed: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/tools/test_rxnav_client.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 5 new tests = 606 passed.

- [ ] **Step 6: Commit**

```bash
git add healthflow/tools/rxnav_client.py healthflow/tests/tools/test_rxnav_client.py
git commit -m "RxNavClient: async NLM RxNav client with disk cache + silent-fail"
```

---

## Task 2: Pydantic response schemas

**Files:**
- Modify: `healthflow/models/schemas.py` (append after the existing auth schemas)

- [ ] **Step 1: Add schemas**

Open `healthflow/models/schemas.py`. Find the existing `ResetPasswordRequest` class (added in the account-management PR). At the END of the file, append:

```python


class DrugMatchModel(BaseModel):
    rxcui: str = Field(..., description="RxNorm canonical drug identifier")
    name: str = Field(..., description="Human-readable drug name")
    term_type: str = Field(..., description="RxNorm Term Type (TTY): SBD, SCD, IN, PIN, BN, etc.")
    is_brand: bool = Field(..., description="True for branded drugs (TTY in {SBD, BN})")


class DrugSearchResponse(BaseModel):
    query: str
    matches: list[DrugMatchModel]
```

- [ ] **Step 2: Smoke-test the import**

Run: `.venv/bin/python -c "from healthflow.models.schemas import DrugMatchModel, DrugSearchResponse; print('ok')"`
Expected: `ok` printed; no ImportError, no Pydantic complaint.

- [ ] **Step 3: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: 606 passed (no new tests yet for these schemas — they're exercised in Task 3).

- [ ] **Step 4: Commit**

```bash
git add healthflow/models/schemas.py
git commit -m "Add DrugMatchModel + DrugSearchResponse Pydantic schemas"
```

---

## Task 3: `drug_router.py` + `GET /drugs/search` + mount + 4 endpoint tests

**Files:**
- Create: `healthflow/api/drug_router.py`
- Modify: `healthflow/main.py` (mount the router)
- Test: `healthflow/tests/api/test_drug_router.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/tests/api/test_drug_router.py`:

```python
"""Endpoint tests for GET /drugs/search.

Uses the existing `client` fixture + monkeypatches RxNavClient in the router
module to a fake that returns predetermined matches. No live RxNav calls.
"""
import pytest

from healthflow.tools.rxnav_client import DrugMatch


# Two known matches the fake returns when search() is called.
_FAKE_MATCHES = [
    DrugMatch(
        rxcui="860975",
        name="Metformin hydrochloride 500 MG Oral Tablet",
        term_type="SCD",
        is_brand=False,
    ),
    DrugMatch(
        rxcui="861007",
        name="Glucophage 500 MG Oral Tablet",
        term_type="SBD",
        is_brand=True,
    ),
]


class _FakeRxNavClient:
    """Drop-in for RxNavClient that records the last query + returns fixed matches."""
    def __init__(self, matches=None, raises=None):
        self._matches = matches if matches is not None else _FAKE_MATCHES
        self._raises = raises
        self.last_query: tuple[str, int] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def search(self, query, *, limit=10):
        if self._raises is not None:
            raise self._raises
        self.last_query = (query, limit)
        return self._matches


async def _register_and_login(client, email="drugs@example.com", password="Cromulent42!"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Drug Tester"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_search_happy_path(client, monkeypatch):
    """Bearer + ?q=metformin → 200; schema correct; fake client saw (query, limit)."""
    from healthflow.api import drug_router as drug_router_mod

    fake = _FakeRxNavClient()
    monkeypatch.setattr(drug_router_mod, "RxNavClient", lambda: fake)

    access = await _register_and_login(client)
    resp = await client.get(
        "/drugs/search?q=metformin&limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "metformin"
    assert len(body["matches"]) == 2
    assert body["matches"][0]["rxcui"] == "860975"
    assert body["matches"][0]["is_brand"] is False
    assert body["matches"][1]["is_brand"] is True
    assert fake.last_query == ("metformin", 10)


@pytest.mark.asyncio
async def test_search_requires_bearer(client):
    """No Authorization header → 401."""
    resp = await client.get("/drugs/search?q=metformin")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_rejects_empty_query(client):
    """?q= (empty) → 422 from Pydantic min_length=1."""
    access = await _register_and_login(client, email="empty@example.com")
    resp = await client.get(
        "/drugs/search?q=",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_returns_empty_when_rxnav_client_raises(client, monkeypatch):
    """Fake client raises → endpoint catches at boundary; 200 with empty matches."""
    from healthflow.api import drug_router as drug_router_mod

    fake = _FakeRxNavClient(raises=RuntimeError("simulated boom"))
    monkeypatch.setattr(drug_router_mod, "RxNavClient", lambda: fake)

    access = await _register_and_login(client, email="boom@example.com")
    resp = await client.get(
        "/drugs/search?q=metformin",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"query": "metformin", "matches": []}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/api/test_drug_router.py -v`
Expected: all 4 FAIL — `/drugs/search` returns 404 (the router doesn't exist yet).

- [ ] **Step 3: Create `drug_router.py`**

Create `healthflow/api/drug_router.py`:

```python
"""GET /drugs/search — authenticated drug autocomplete backed by RxNav.

Silent-fail at the boundary: any exception from RxNavClient becomes an empty
matches list, not a 500. Autocomplete shouldn't crash on a flaky upstream.
"""
import logging

from fastapi import APIRouter, Depends, Query

from healthflow.auth.dependencies import get_current_broker
from healthflow.database.models import Broker
from healthflow.models.schemas import DrugMatchModel, DrugSearchResponse
from healthflow.tools.rxnav_client import RxNavClient

logger = logging.getLogger(__name__)

drug_router = APIRouter(prefix="/drugs", tags=["drugs"])


@drug_router.get("/search", response_model=DrugSearchResponse)
async def search_drugs(
    q: str = Query(..., min_length=1, max_length=100, description="Drug name to search for"),
    limit: int = Query(10, ge=1, le=50, description="Max matches to return"),
    broker: Broker = Depends(get_current_broker),
) -> DrugSearchResponse:
    """Autocomplete drug search backed by RxNav (NLM RxNorm REST API).

    Returns up to `limit` matches ordered by RxNorm's own concept-group ordering.
    Silent-fail: a RxNav outage returns an empty list, not a 500.
    """
    query = q.strip()
    try:
        async with RxNavClient() as rxnav:
            matches = await rxnav.search(query, limit=limit)
    except Exception as e:
        logger.warning("drugs.search rxnav client raised: %s", e)
        matches = []

    logger.info(
        "drugs.search broker_id=%s query_length=%d result_count=%d",
        broker.id, len(query), len(matches),
    )

    return DrugSearchResponse(
        query=query,
        matches=[
            DrugMatchModel(
                rxcui=m.rxcui,
                name=m.name,
                term_type=m.term_type,
                is_brand=m.is_brand,
            )
            for m in matches
        ],
    )
```

- [ ] **Step 4: Mount the router in `main.py`**

Open `healthflow/main.py`. After the existing `from healthflow.auth.admin_router import admin_router` line, add:

```python
from healthflow.api.drug_router import drug_router
```

After the existing `app.include_router(admin_router)` line, add:

```python
app.include_router(drug_router)
```

- [ ] **Step 5: Run endpoint tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/api/test_drug_router.py -v`
Expected: 4 passed.

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: 610 passed (606 from Task 1 + 4 new endpoint tests).

- [ ] **Step 7: Commit**

```bash
git add healthflow/api/drug_router.py healthflow/main.py healthflow/tests/api/test_drug_router.py
git commit -m "GET /drugs/search: auth-gated RxNav-backed drug autocomplete"
```

---

## Task 4: Opt-in live integration test

**Files:**
- Create: `healthflow/tests/integration/__init__.py` (only if `healthflow/tests/integration/` doesn't already exist)
- Create: `healthflow/tests/integration/test_rxnav_live.py`

- [ ] **Step 1: Check whether the integration test dir exists**

Run: `ls healthflow/tests/integration/ 2>&1 | head -2`
Expected: either an existing list of files OR `ls: ... No such file or directory`.

- [ ] **Step 2: Create `__init__.py` if needed**

If the previous step said `No such file or directory`, run:

```bash
mkdir -p healthflow/tests/integration
touch healthflow/tests/integration/__init__.py
```

Otherwise skip this step.

- [ ] **Step 3: Add the live integration test**

Create `healthflow/tests/integration/test_rxnav_live.py`:

```python
"""Opt-in live RxNav integration test. Skipped unless RXNAV_LIVE_TESTS=1.

Run with:
    RXNAV_LIVE_TESTS=1 .venv/bin/python -m pytest healthflow/tests/integration/test_rxnav_live.py -v

Detects RxNav response-shape drift on demand without burdening CI with a
network dependency.
"""
import os

import pytest

from healthflow.tools.rxnav_client import RxNavClient


_LIVE_TESTS_ENABLED = os.getenv("RXNAV_LIVE_TESTS") == "1"


@pytest.mark.skipif(
    not _LIVE_TESTS_ENABLED,
    reason="Live RxNav test; set RXNAV_LIVE_TESTS=1 to enable",
)
@pytest.mark.asyncio
async def test_live_search_returns_metformin(tmp_path):
    """Hit the real RxNav for 'metformin' and assert at least one Metformin
    match is returned with a valid RxCUI."""
    async with RxNavClient(cache_dir=tmp_path) as client:
        matches = await client.search("metformin", limit=10)

    assert len(matches) > 0, "expected at least one match from live RxNav"
    assert all(m.rxcui.isdigit() for m in matches), \
        f"every RxCUI should be numeric; got {[m.rxcui for m in matches]}"
    assert any("metformin" in m.name.lower() for m in matches), \
        f"expected Metformin in the results; got {[m.name for m in matches]}"
```

- [ ] **Step 4: Verify the test is skipped by default**

Run: `.venv/bin/python -m pytest healthflow/tests/integration/test_rxnav_live.py -v`
Expected: 1 skipped (reason: `Live RxNav test; set RXNAV_LIVE_TESTS=1 to enable`).

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: 610 passed, 1 skipped (the live test is skipped; collected but not run).

- [ ] **Step 6: Commit**

```bash
git add healthflow/tests/integration/
git commit -m "Opt-in live RxNav integration test (RXNAV_LIVE_TESTS=1)"
```

---

## Task 5: README updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `/drugs/search` to the Authentication-adjacent endpoints**

Open `README.md`. Find the table that starts with `| `POST /auth/register` |`. After the entire Authentication section (after the last `| POST /auth/reset-password | ...` row), and after the Admin section, add a new section:

Find this existing block (the Admin section):

```markdown
### Admin (RBAC-gated)

| Endpoint | Description |
|----------|-------------|
| `POST /admin/brokers/{broker_id}/unlock` | Force-unlock a locked broker (clears `failed_login_count` + `locked_until`); audit-logged |

Admins are created via `python scripts/promote_admin.py --email <broker-email>` — no API path flips role.
```

Immediately after this block, insert:

```markdown

### Drug Search (RxNav)

| Endpoint | Description |
|----------|-------------|
| `GET /drugs/search?q=...&limit=...` | Authenticated drug autocomplete backed by NLM's RxNav REST API. Returns up to 50 matches with RxCUI, name, RxNorm Term Type, and a brand/generic flag. Silent-fail: a RxNav outage returns an empty list, not a 500. |
```

- [ ] **Step 2: Add RxNorm/RxNav to the "Real Health Data" table**

In `README.md`, find the existing table that starts at "## Real Health Data". The current rows are CMS, FDA OpenFDA, NPPES Registry, Zip Mapping. After the last row (Zip Mapping), add:

```markdown
| **NLM RxNorm / RxNav** | Canonical US drug terminology — RxCUI, brand/generic mapping, ingredients (live REST API, no auth) | ~150k drug concepts |
```

- [ ] **Step 3: Bump test counts**

In `README.md`, replace every `601` with `610` (610 passing tests; the 1 opt-in live test is collected-then-skipped and not counted in the headline number).

Run to confirm there are exactly 4 occurrences to update:

```bash
grep -n "601" README.md
```

Expected: 4 lines (in the "make all" example, the "make test" example, the testing intro, and the project-structure tree). Edit each line in place — same prose, just bump the number.

- [ ] **Step 4: Run the full suite one more time as a sanity check**

Run: `make test 2>&1 | tail -3`
Expected: 610 passed, 1 skipped (no doc-only commit changes this).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "README: document /drugs/search + RxNorm; refresh test counts"
```

---

## Task 6: `healthflow-security` skill update

**Files:**
- Modify: `.claude/skills/healthflow-security/SKILL.md`

- [ ] **Step 1: Add a new section for external-API PHI posture**

Open `.claude/skills/healthflow-security/SKILL.md`. The existing structure has sections like `## Auth hardening rules (enforced)`, `## Account management (PR #14)`, `## Encryption at rest (enforced)`. After the `## Account management (PR #14)` section and before `## Encryption at rest (enforced)`, insert:

```markdown
## External-API PHI posture: RxNav

- **RxNav (`rxnav.nlm.nih.gov`) is a public, non-PHI terminology service.** Drug
  names are not PHI on their own, but a *broker's* search history could hint
  at a client's conditions (e.g. searching "Truvada" suggests HIV PrEP, "Sovaldi"
  suggests Hep C). Treat search queries as sensitive even though the upstream
  service is public.

- **Never send broker_id, client_id, or any patient identifier to RxNav.** The
  URL only contains the drug query string. The cache key is a SHA-256 hash of
  the query, never the plaintext.

- **Never log RxNav query text.** The `drugs.search` access log records
  `broker_id`, `query_length`, and `result_count` — never the query itself.
  Any code path that adds logging in this area MUST follow the same rule.

- **Silent-fail on errors.** A RxNav timeout or 5xx returns an empty matches
  list with HTTP 200, not a 5xx to the broker. Autocomplete must never crash
  a request.
```

- [ ] **Step 2: Verify the section sits in the right place**

Run:

```bash
grep -n "^##" .claude/skills/healthflow-security/SKILL.md
```

Expected: the new `## External-API PHI posture: RxNav` heading appears between `## Account management (PR #14)` and `## Encryption at rest (enforced)`.

- [ ] **Step 3: Run the full suite one more time as a sanity check**

Run: `make test 2>&1 | tail -3`
Expected: 610 passed, 1 skipped.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/healthflow-security/SKILL.md
git commit -m "Skill: document RxNav PHI posture (no broker ids in URLs, no query logging)"
```

---

## Task 7: Final verification + push + PR

**Files:** none (operations only).

- [ ] **Step 1: Run lint**

Run: `make lint 2>&1 | tail -5`
Expected: same baseline as `main` (~11 pre-existing E402 findings in `main.py`/test files; zero new findings introduced by this branch).

- [ ] **Step 2: Run dead-code scan**

Run: `make dead-code 2>&1 | tail -5`
Expected: clean (no findings).

- [ ] **Step 3: Final test run**

Run: `make test 2>&1 | tail -3`
Expected: `610 passed, 1 skipped`.

- [ ] **Step 4: Inspect commit history**

Run: `git log --oneline main..HEAD`
Expected: 6 commits in order:
1. `RxNavClient: async NLM RxNav client with disk cache + silent-fail`
2. `Add DrugMatchModel + DrugSearchResponse Pydantic schemas`
3. `GET /drugs/search: auth-gated RxNav-backed drug autocomplete`
4. `Opt-in live RxNav integration test (RXNAV_LIVE_TESTS=1)`
5. `README: document /drugs/search + RxNorm; refresh test counts`
6. `Skill: document RxNav PHI posture (no broker ids in URLs, no query logging)`

- [ ] **Step 5: Push the branch**

Run: `git push -u origin rxnav-drug-search`
Expected: branch pushed, tracking set.

- [ ] **Step 6: Open the PR**

Run:

```bash
gh pr create --title "RxNav drug search: live NLM data + /drugs/search endpoint" --body "$(cat <<'EOF'
## Summary

- New `healthflow/tools/rxnav_client.py`: async client for NLM RxNav with 24h disk cache + silent-fail.
- New `GET /drugs/search?q=...&limit=...` endpoint, auth-gated via `get_current_broker`.
- 9 new tests (5 client unit + 4 endpoint) + 1 opt-in live integration test (skipped by default).
- Real, live external data — replaces "type a drug name and hope" with autocomplete from the ~150k-concept RxNorm universe.

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-05-20-rxnav-drug-search-design.md`
- Plan: `docs/superpowers/plans/2026-05-20-rxnav-drug-search.md`

## Why RxNav
After the CMS Socrata retirement we considered the ACA Marketplace API, but `api.healthcare.gov` has been deprecated and the live Plan-Compare JSON is undocumented. RxNav is NLM-maintained, indestructible, and slots directly into HealthFlow's existing drug surface. See the spec's Problem section for the full reasoning.

## Test plan
- [ ] CI green (610 passed, 1 skipped).
- [ ] Manual: hit `GET /drugs/search?q=metformin` with a valid bearer; expect ≥1 Metformin RxCUI.
- [ ] Manual: `RXNAV_LIVE_TESTS=1 .venv/bin/python -m pytest healthflow/tests/integration/test_rxnav_live.py -v` — exercises the real RxNav.

## Deploy notes
- No new env vars.
- Disk cache at `~/.cache/healthflow/rxnav/` (matches existing CMS/FDA pattern). Auto-created on first request.
- HIPAA: RxNav is a public terminology service. The client never sends broker_id / client_id / patient data; the access log never records query text. Documented in the `healthflow-security` skill.

## Out of scope (next sub-projects)
- Brand↔generic substitution suggestions in `cost_estimator.py`.
- Replacing `drug_database.py` with RxNorm as source of truth.
- Frontend autocomplete UI.
- Hooking RxCUI into `formulary_checker.py`.
EOF
)"
```

Expected: PR URL printed; CI begins.

---

## Notes for the implementer

- **`async with RxNavClient()`** is the intended call shape — handles its own lifecycle. Tests that want to inject a specific `http_client` pass it to the constructor directly (`RxNavClient(http_client=mock, cache_dir=tmp_path)`).
- **No new env vars.** The opt-in live test reads `RXNAV_LIVE_TESTS` but it's a test-time toggle, not a production config.
- **The `~/.cache/healthflow/rxnav/` directory** is auto-created by `RxNavClient.__init__` on first instantiation. Unit tests should ALWAYS pass `cache_dir=tmp_path` to keep test artifacts out of the developer's home directory.
- **Silent-fail discipline:** every error path in `rxnav_client.py` returns `[]` rather than raising. The router has a single try/except at the boundary as a belt-and-suspenders measure. Don't surface RxNav errors to the broker.
- **No PHI:** the only string sent to RxNav is the search query. Don't add `broker_id`, `client_id`, or anything else to the URL or the cache key.
- **Order matters:** Task 1 (client) → Task 2 (schemas) → Task 3 (router) is a real dependency chain — the schemas import nothing from the client, but the router imports both. Don't reorder.
- **`make dead-code` ignores list:** the existing `--ignore-names` covers `cls`, `__context`, etc. RxNav code shouldn't add any framework-callback false positives.
