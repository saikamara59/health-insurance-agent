# RxNav Drug Search

**Date:** 2026-05-20
**Status:** Approved (design)
**Part of:** Live-data follow-up to the HIPAA-readiness foundation. Started as an ACA Marketplace pivot after the CMS Socrata retirement; redirected to RxNav once it became clear the live ACA APIs are either deprecated (`api.healthcare.gov`) or undocumented (the Plan Compare JSON), while RxNav is genuinely live, official, and far higher-leverage for HealthFlow's existing drug surface.

## Problem

HealthFlow's drug data is 90 hardcoded medications shipped in `healthflow_data.db` from a one-time FDA OpenFDA pull. That covers the seed-client demo but breaks for any real-world client whose prescription isn't in the list:

- The `Add Client` flow asks for medications as a free-text list. There's no autocomplete, no validation, no canonical identifier. A broker typing "Ozempic" gets a string stored verbatim. A typo ("Ozepic") silently persists.
- `cost_estimator.py` and `formulary_checker.py` match by exact lowercased name. Brand-vs-generic confusion (Glucophage / Metformin) is not handled.
- The cost-comparison story is structurally capped at 90 drugs — adding a 91st means a schema migration or a fixture edit.

After the CMS Socrata API retirement (2026-05) we re-evaluated which external data sources are actually live and durable for this project:

- **RxNorm / RxNav (National Library of Medicine)** is the canonical US drug terminology service. NLM-maintained, free, JSON REST, no auth, used by every EHR. The full drug universe (~150k concepts) including brand↔generic mapping, ingredients, and dosage forms. Essentially indestructible — NLM has run RxNav continuously since 2004.
- It slots into HealthFlow's existing drug surface without rewriting any of the agent pipeline.

## Goal

A new `RxNavClient` + one auth-gated endpoint `GET /drugs/search?q=...` that returns drug autocomplete suggestions from RxNav. Pure additive: no existing file loses behavior, no agent or schema changes. The first wave of real, externally-sourced drug data into HealthFlow.

## Non-Goals

Each is a deliberate deferral with a clear next home:

- **Brand↔generic substitution suggestions in cost flows.** Pairs naturally with this work but multiplies the surface area — `cost_estimator.py` and the comparison agent both gain new behavior. Next sub-project.
- **Replacing `drug_database.py` outright.** Higher-leverage but rewrites every drug-touching tool. Out of scope; the 90-drug DB stays the source of truth for cost lookups today.
- **Drug-drug interaction warnings.** RxNav's interaction API was retired by NLM in 2024; would need a different data source (e.g., DrugBank with a license). Not started.
- **Formulary integration.** Hooking RxCUI into `formulary_checker.py` requires a per-plan drug list keyed by RxCUI; the current formulary data is name-keyed. Cleanup is a sub-project of its own.
- **Frontend autocomplete UI.** Backend endpoint ships here; the React `Add Client` form gains the autocomplete in a separate frontend PR.
- **Redis-backed cache.** Disk cache is enough for one-process dev/CI; Redis is the right move once we have multiple backend replicas. Not now.
- **Background prefetch of common drugs.** "Warm the cache for the top 200 drugs at startup" is a nice latency win but premature without measurements.
- **Rate limiting per broker.** RxNav has no advertised cap; if abuse becomes visible the disk cache absorbs it for free. Add limits when there's data, not before.

## Design

### Architecture

A new async RxNav HTTP client + one auth-gated FastAPI endpoint. No DB writes, no SQLAlchemy, no PHI flows.

**Files touched:**

- `healthflow/tools/rxnav_client.py` *(new)* — `RxNavClient` async class, `DrugMatch` dataclass, disk cache at `~/.cache/healthflow/rxnav/`.
- `healthflow/api/drug_router.py` *(new)* — `drug_router = APIRouter(prefix="/drugs", tags=["drugs"])` with one endpoint.
- `healthflow/models/schemas.py` *(modify)* — `DrugMatchModel` and `DrugSearchResponse`.
- `healthflow/main.py` *(modify)* — mount the router.
- `healthflow/tests/tools/test_rxnav_client.py` *(new)* — 5 client unit tests using `httpx.MockTransport`.
- `healthflow/tests/api/test_drug_router.py` *(new)* — 4 endpoint tests using the existing `client` fixture + monkeypatched client.
- `README.md` *(modify)* — document `GET /drugs/search`; add RxNorm to the "Real Health Data" table.
- `.claude/skills/healthflow-security/SKILL.md` *(modify)* — one rule on the no-PHI-to-RxNav posture and query non-logging.

**Key separations:**

- The RxNav client knows nothing about FastAPI, auth, or HealthFlow's DB. Single responsibility: ask RxNav for drug matches, cache the answer, return them. Plain async Python.
- The router does the HTTP-to-Python translation (Pydantic) and the auth gating. Nothing else.
- Caching lives on the client. Future consumers (a brand-generic helper in `cost_estimator.py`, a follow-up `/drugs/{rxcui}/related` endpoint) reuse the same cached instance and the same TTL semantics for free.

### RxNav endpoints used

- `GET https://rxnav.nlm.nih.gov/REST/drugs.json?name={q}` — primary search. Returns a `drugGroup` structure with `conceptGroup` entries by RxNorm Term Type (TTY): `SBD` (semantic branded drug), `SCD` (semantic clinical drug), `BN` (brand name), `IN` (ingredient), `PIN` (precise ingredient). Each `conceptGroup` has a list of `conceptProperties`.
- `GET https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={q}&maxEntries={n}` — fallback when `drugs.json` returns empty. Typo-tolerant; returns `candidate` entries with `rxcui`, `score`, `rank`.

No other RxNav endpoints in this sub-project.

### `RxNavClient`

```python
# healthflow/tools/rxnav_client.py
import asyncio
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
    """Async client for the RxNav REST API.

    Caches successful responses on disk for 24h. Silent-fail on any network
    error or upstream 4xx/5xx — returns []. Never raises to the caller.
    Autocomplete should never crash a request.
    """

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
            out.append(DrugMatch(
                rxcui=str(rxcui),
                name=name,
                term_type=c.get("tty", ""),
                is_brand=c.get("tty", "") in self._BRAND_TTYS,
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

**Notable choices:**

- `DrugMatch` is a frozen dataclass — same idiom as the auth `PromptInput` types. Immutable, hashable, no surprise mutations.
- `is_brand` is precomputed from the TTY at construction. Frontend doesn't need to know RxNorm vocabulary.
- The disk cache key is a SHA-256 prefix of the query + limit, lowercased. Plaintext queries NEVER hit the filesystem (defense against future "what was the broker searching for?" forensics).
- Cache writes are atomic via `.tmp` → `replace` rename, matching the pattern in `scripts/refresh_data.py`.
- The class supports both `async with RxNavClient() as c:` for one-shot use and "pass me an httpx client" for shared-client scenarios. The endpoint uses the context-manager form.

### `GET /drugs/search` endpoint

**Request:** `GET /drugs/search?q=metformin&limit=10`

**Auth:** `get_current_broker` dependency — same as every other authenticated endpoint.

**Response 200:**
```json
{
  "query": "metformin",
  "matches": [
    {"rxcui": "860975", "name": "Metformin hydrochloride 500 MG Oral Tablet", "term_type": "SCD", "is_brand": false},
    {"rxcui": "861007", "name": "Glucophage 500 MG Oral Tablet", "term_type": "SBD", "is_brand": true}
  ]
}
```

**Implementation** (`healthflow/api/drug_router.py`):

```python
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
    limit: int = Query(10, ge=1, le=50, description="Max number of matches to return"),
    broker: Broker = Depends(get_current_broker),
) -> DrugSearchResponse:
    """Autocomplete drug search backed by RxNav (NLM RxNorm REST API).

    Returns up to `limit` drug matches ordered by RxNorm's own concept-group
    ordering (semantic clinical drugs first, brand drugs next). Silent-fail:
    a RxNav outage returns an empty list, not a 500.
    """
    query = q.strip()
    async with RxNavClient() as client:
        matches = await client.search(query, limit=limit)

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

**Validation:**
- `q`: required string, 1-100 chars (Pydantic `Query`). Whitespace-trimmed in the handler.
- `limit`: optional int, 1-50, default 10.
- Validation failure → 422 (Pydantic).
- No bearer → 401 (from `get_current_broker`).
- RxNav down / 5xx / timeout → 200 with `matches: []`. Client gets degraded autocomplete; no error toast.

**Logging:**
- One INFO log per request with `broker_id`, `query_length` (NOT the query text), `result_count`. Search queries can reveal client conditions; even though RxNav is public, HealthFlow's logs are not.
- WARN log inside the client on any RxNav failure with the exception class and message. Useful for "why are autocomplete results suddenly empty?" debugging.

### `schemas.py` additions

```python
class DrugMatchModel(BaseModel):
    rxcui: str
    name: str
    term_type: str
    is_brand: bool


class DrugSearchResponse(BaseModel):
    query: str
    matches: list[DrugMatchModel]
```

Appended after the existing auth schemas (alongside `ChangePasswordRequest` etc).

### `main.py` mount

```python
from healthflow.api.drug_router import drug_router
...
app.include_router(drug_router)
```

Mounted after the other routers; order doesn't matter for matching.

### Error handling matrix

| Endpoint | Failure mode | Response |
|---|---|---|
| `GET /drugs/search` | Missing/invalid bearer | `401` from `get_current_broker` |
| `GET /drugs/search` | Empty `q` (after Pydantic `min_length=1`) | `422` |
| `GET /drugs/search` | `limit` out of range | `422` |
| `GET /drugs/search` | RxNav 5xx / network timeout | `200 {"query": "...", "matches": []}` |
| `GET /drugs/search` | RxNav returns no matches (exact or approximate) | `200 {"query": "...", "matches": []}` |

### Test plan (10 tests total)

**`test_rxnav_client.py` (5 tests)** — `httpx.MockTransport` for all HTTP, no live network.

1. **`test_search_returns_matches_for_known_drug`** — mock RxNav `drugs.json` with a realistic two-conceptGroup payload (one SCD, one SBD); assert client returns 2 `DrugMatch` with the right rxcui/name/term_type and `is_brand` correctly derived from TTY.
2. **`test_search_falls_back_to_approximate_when_empty`** — mock returns `{"drugGroup": {"conceptGroup": []}}` for `drugs.json`; then mock `approximateTerm.json` to return candidates; assert two HTTP calls were made and the approximate matches returned.
3. **`test_search_returns_empty_on_timeout`** — `MockTransport` raises `httpx.ConnectTimeout`; assert client returns `[]` and a WARN log fired. Critical: no exception propagates.
4. **`test_cache_hit_skips_http`** — pass a `tmp_path` as `cache_dir`; first `search("metformin")` hits the mock once; second identical call returns the same result without any new HTTP call (assert the mock's request count is 1).
5. **`test_cache_miss_after_ttl`** — after first call, backdate the cache file's mtime by 25 hours via `os.utime`; second call goes back to the mock.

**`test_drug_router.py` (4 tests)** — uses the existing `client` fixture (httpx + FastAPI test transport). Monkeypatches `RxNavClient` in the router module to a fake that returns predetermined matches.

1. **`test_search_happy_path`** — register + login; `GET /drugs/search?q=metformin` with bearer; assert 200, response schema matches, the fake client received `("metformin", limit=10)`.
2. **`test_search_requires_bearer`** — no Authorization header; assert 401.
3. **`test_search_rejects_empty_query`** — `?q=` with bearer; assert 422.
4. **`test_search_returns_empty_when_rxnav_down`** — fake client raises `RuntimeError`; endpoint catches at the boundary; response is `{"query": "metformin", "matches": []}` with status 200.

**One opt-in live test** (`@pytest.mark.live_network`, skipped by default unless `RXNAV_LIVE_TESTS=1`) — hits the real RxNav for "metformin" and asserts a Metformin RxCUI is present. For drift detection on demand:

```bash
RXNAV_LIVE_TESTS=1 pytest -m live_network -v
```

Document the marker in `pyproject.toml`'s `[tool.pytest.ini_options].markers`.

### Rollout (per-task, each commit green)

1. **Baseline + branch.** Confirm `make test` is 601 green. Create `rxnav-drug-search` branch.
2. **`RxNavClient` + 5 unit tests** — pure offline TDD.
3. **`DrugMatchModel` / `DrugSearchResponse` schemas + `drug_router.py` + mount in `main.py` + 4 endpoint tests.**
4. **README** — add `/drugs/search` to the endpoints section; add RxNorm to the "Real Health Data" table; bump test counts.
5. **`healthflow-security` skill** — new rule documenting the no-PHI / no-query-logging posture for RxNav.
6. **Final verification** — `make test` should be ~611. `make lint` baseline unchanged. `make dead-code` clean.
7. **Push + PR.**

### Risks

| Risk | Mitigation |
|---|---|
| RxNav goes down or rate-limits us | Silent-fail returns `[]`; cache absorbs repeat queries; UX degrades to "no autocomplete suggestions" rather than 500s. |
| Cache directory unwritable (permissions, full disk) | `_cache_put` catches `OSError` and logs WARN; live results still serve. Cold-cache hits go straight through. |
| Query strings hint at client conditions (a search for "Truvada", "Sovaldi", etc.) | Never log query text. Cache filenames are SHA-256 hex, not plaintext. Documented in `healthflow-security`. |
| RxNav response shape drift | Mock payloads in tests are copy-pasted from real RxNav responses. The opt-in live test detects drift on demand. |
| First load is slow (cold cache, multiple bounces hit upstream serially) | Acceptable for v1. The follow-up sub-project will add request-debouncing on the frontend; backend prefetch is YAGNI. |
| `~/.cache/healthflow/rxnav/` accumulates files forever | Each file is a few KB; 24h TTL means stale files are eventually overwritten when re-queried. A cleanup job is YAGNI at this scale. |
| Concurrent first-callers race on `_cache_put` | Worst case: two requests both write the same file; `tmp.replace(path)` is atomic on POSIX; the second write wins and the content is identical. Benign. |
| RxNav response includes unicode oddities (e.g. trademark symbols in brand names) | Pydantic handles JSON unicode natively. Logged INFO message uses `%d`/`%s` formatters which never raise on encoding. |
| Spec drift with `formulary_checker.py` / `cost_estimator.py` (they still use name-keyed lookups) | Out of scope. The next sub-project introduces RxCUI as a join key. This PR doesn't change either. |

## Acceptance

This sub-project is done when:

1. `RxNavClient.search(query, limit)` returns drug matches from RxNav, with 24h disk caching and silent-fail on errors.
2. `GET /drugs/search?q=...&limit=...` returns autocomplete results to an authenticated broker; 401 without bearer; 422 on validation; 200 with empty matches when RxNav is down.
3. 10 new tests passing (5 client + 4 endpoint + 1 opt-in live, marker-gated).
4. README documents `GET /drugs/search` and adds RxNorm/RxNav to the "Real Health Data" table.
5. The `healthflow-security` skill documents the no-PHI / no-query-logging posture for RxNav.

## Out of Scope

Each is a deliberate deferral with a clear next home:

- Brand↔generic substitution suggestions in `cost_estimator.py` (next sub-project).
- Replacing `drug_database.py` with RxNorm as the source of truth.
- Drug-drug interaction warnings (would need a different data source after NLM retired the interaction API in 2024).
- Hooking RxCUI into `formulary_checker.py` (requires a per-plan formulary keyed by RxCUI).
- Frontend autocomplete UI (separate frontend PR).
- Redis-backed cache (Disk cache works for single-process; Redis is the right move for multi-replica deployments).
- Background prefetch of common drugs at startup.
- Per-broker rate limiting on `/drugs/search`.
- Endpoints beyond `/drugs/search` (`/drugs/{rxcui}/related`, `/drugs/{rxcui}/properties`) — straightforward follow-ups using the same client.
