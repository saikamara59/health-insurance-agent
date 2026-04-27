# Per-Worker DB Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable parallel Playwright workers (target: 4 in CI) by scoping the e2e test reset endpoint to a per-worker `Broker`, so each worker's data is isolated by the multi-tenant boundary that already exists in the schema.

**Architecture:** The `/__test/reset` endpoint is rewritten to require a `worker_id` body param. It lazily provisions a `Broker` (sticky across resets so JWTs stay valid) and only deletes/re-seeds rows owned by that broker. Playwright fixtures derive a stable `worker_id` from `testInfo.parallelIndex`. No new infrastructure; works identically on SQLite or Postgres.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, Playwright, pytest, anyio.

**Spec:** [docs/superpowers/specs/2026-04-27-per-worker-db-isolation-design.md](../specs/2026-04-27-per-worker-db-isolation-design.md)

---

## File Map

**Modify:**
- `healthflow/seed_data.py` — add `worker_email`, `seed_for_worker`; remove now-unused `TEST_BROKER` and `seed_db`
- `healthflow/api/test_router.py` — rewrite `/__test/reset` to require scoped `worker_id`
- `healthflow/tests/test_seed_data.py` — replace `seed_db` tests with `seed_for_worker` tests
- `healthflow/tests/test_test_router.py` — update reset-endpoint tests for the new scoped contract
- `scripts/seed_test_db.py` — drop the data-seed step; just reset schema
- `frontend/tests/fixtures/test-users.js` — replace `broker` constant with `workerBroker(workerIndex)` factory
- `frontend/tests/fixtures/index.js` — add `workerBroker` fixture; resets/login use the worker's identity
- `frontend/playwright.config.js` — set `fullyParallel: true`, `workers: 4` in CI

**Create:**
- `frontend/tests/e2e/isolation.spec.js` — cross-pollution canary

**Audit (read-only, document findings inline; create follow-up tasks if leaks found):**
- `healthflow/api/routes.py`, `healthflow/api/client_router.py`, `healthflow/api/history_router.py`, `healthflow/api/middleware.py`

---

## Task 1: Add `seed_for_worker` to `seed_data.py`

**Goal:** Idempotently provision a worker's broker and canonical client set, scoped by a deterministic email.

**Files:**
- Modify: `healthflow/seed_data.py`
- Test: `healthflow/tests/test_seed_data.py`

- [ ] **Step 1: Replace existing seed_data tests with the new contract**

Open `healthflow/tests/test_seed_data.py` and replace the entire contents with:

```python
"""Tests for per-worker seed provisioning."""
import pytest
from sqlalchemy import select

from healthflow.database.models import Broker, Client
from healthflow.seed_data import (
    TEST_CLIENTS,
    WORKER_PASSWORD,
    seed_for_worker,
    worker_email,
)


def test_worker_email_is_deterministic():
    assert worker_email("e2e-worker-0") == "e2e-worker-0@healthflow.test"
    assert worker_email("e2e-worker-3") == "e2e-worker-3@healthflow.test"


@pytest.mark.anyio
async def test_seed_for_worker_creates_broker_and_clients(db_session):
    broker = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    assert broker.email == "e2e-worker-0@healthflow.test"
    assert broker.full_name == "E2E Worker 0"

    clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker.id))
    ).scalars().all()
    assert len(clients) == len(TEST_CLIENTS)
    assert {c.full_name for c in clients} == {c["full_name"] for c in TEST_CLIENTS}


@pytest.mark.anyio
async def test_seed_for_worker_is_idempotent_on_broker(db_session):
    broker_a = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()
    broker_b = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    assert broker_a.id == broker_b.id

    brokers = (
        await db_session.execute(
            select(Broker).where(Broker.email == "e2e-worker-0@healthflow.test")
        )
    ).scalars().all()
    assert len(brokers) == 1


@pytest.mark.anyio
async def test_seed_for_worker_replaces_existing_clients(db_session):
    broker = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    extra = Client(
        broker_id=broker.id,
        full_name="Stale Client",
        zip_code="00000",
        age=30,
        income_level="low",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(extra)
    await db_session.commit()

    await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker.id))
    ).scalars().all()
    names = {c.full_name for c in clients}
    assert names == {c["full_name"] for c in TEST_CLIENTS}
    assert "Stale Client" not in names


@pytest.mark.anyio
async def test_seed_for_worker_isolates_brokers(db_session):
    broker_a = await seed_for_worker(db_session, "e2e-worker-0")
    broker_b = await seed_for_worker(db_session, "e2e-worker-1")
    await db_session.commit()

    assert broker_a.id != broker_b.id
    a_clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker_a.id))
    ).scalars().all()
    b_clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker_b.id))
    ).scalars().all()
    assert len(a_clients) == len(TEST_CLIENTS)
    assert len(b_clients) == len(TEST_CLIENTS)
    assert {c.id for c in a_clients}.isdisjoint({c.id for c in b_clients})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_seed_data.py -v`
Expected: All tests fail with `ImportError` for `seed_for_worker`, `worker_email`, `WORKER_PASSWORD`.

- [ ] **Step 3: Replace `seed_data.py` with the new implementation**

Open `healthflow/seed_data.py` and replace the entire contents with:

```python
"""Per-worker test seed: idempotently provisions a worker's Broker + canonical clients.

Used by `healthflow/api/test_router.py`'s scoped reset endpoint. The broker is
sticky across resets (we only ever create it, never delete) so JWTs issued to
it stay valid. Clients are wiped and re-inserted on each call.

Distinct from the top-level `seed.py` (an HTTP-based broker tool).
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


WORKER_PASSWORD = "TestWorker123!"

TEST_CLIENTS = [
    {
        "full_name": "Eleanor Rigby",
        "zip_code": "10001",
        "age": 67,
        "income_level": "low",
        "doctors": [{"name": "Dr. Smith"}],
        "prescriptions": ["Metformin"],
        "procedures": ["Annual physical"],
    },
    {
        "full_name": "Julian Miller",
        "zip_code": "10001",
        "age": 42,
        "income_level": "medium",
        "doctors": [{"name": "Dr. Jones"}],
        "prescriptions": ["Ozempic"],
        "procedures": ["MRI"],
    },
    {
        "full_name": "Marcus Chen",
        "zip_code": "94102",
        "age": 58,
        "income_level": "high",
        "doctors": [{"name": "Dr. Patel"}],
        "prescriptions": ["Atorvastatin"],
        "procedures": ["Blood work"],
    },
]


def worker_email(worker_id: str) -> str:
    return f"{worker_id}@healthflow.test"


def _worker_full_name(worker_id: str) -> str:
    suffix = worker_id.removeprefix("e2e-worker-")
    return f"E2E Worker {suffix}"


async def seed_for_worker(session: AsyncSession, worker_id: str) -> Broker:
    """Get-or-create the worker's broker, wipe its clients, re-insert canonical set.

    Caller is responsible for committing.
    """
    email = worker_email(worker_id)
    broker = (
        await session.execute(select(Broker).where(Broker.email == email))
    ).scalar_one_or_none()

    if broker is None:
        broker = Broker(
            email=email,
            hashed_password=hash_password(WORKER_PASSWORD),
            full_name=_worker_full_name(worker_id),
        )
        session.add(broker)
        await session.flush()

    await session.execute(delete(Client).where(Client.broker_id == broker.id))

    for client_data in TEST_CLIENTS:
        session.add(
            Client(
                broker_id=broker.id,
                full_name=client_data["full_name"],
                zip_code=client_data["zip_code"],
                age=client_data["age"],
                income_level=client_data["income_level"],
                doctors=client_data["doctors"],
                prescriptions=client_data["prescriptions"],
                procedures=client_data["procedures"],
            )
        )
    await session.flush()
    return broker
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_seed_data.py -v`
Expected: All 5 tests pass.

- [ ] **Step 5: Verify no other code imports the removed `seed_db` / `TEST_BROKER`**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && grep -rn "from healthflow.seed_data import\|TEST_BROKER\|seed_db" healthflow/ scripts/ --include="*.py" | grep -v __pycache__`
Expected output: only references to the new symbols (`seed_for_worker`, `WORKER_PASSWORD`, `TEST_CLIENTS`, `worker_email`). If anything still references `seed_db` or `TEST_BROKER`, those are addressed in later tasks (`scripts/seed_test_db.py` in Task 3, `test_router.py` in Task 2). Do not commit yet.

- [ ] **Step 6: Commit**

```bash
git add healthflow/seed_data.py healthflow/tests/test_seed_data.py
git commit -m "Add per-worker seed_for_worker; replace global seed_db"
```

---

## Task 2: Rewrite `/__test/reset` to require `worker_id`

**Goal:** The reset endpoint becomes scoped. No body → 400. Bad `worker_id` → 400. Valid call → resets only that worker's broker's data.

**Files:**
- Modify: `healthflow/api/test_router.py`
- Modify: `healthflow/tests/test_test_router.py`

- [ ] **Step 1: Update `test_test_router.py` to assert the new contract**

Open `healthflow/tests/test_test_router.py` and replace the existing two test functions (`test_reset_endpoint_returns_404_when_test_mode_off` and `test_reset_endpoint_works_when_test_mode_on`) with:

```python
@pytest.mark.anyio
async def test_reset_endpoint_returns_404_when_test_mode_off(monkeypatch, db_session_factory):
    monkeypatch.delenv("HEALTHFLOW_TEST_MODE", raising=False)
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset", json={"worker_id": "e2e-worker-0"})
        assert response.status_code == 404
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_returns_200_with_valid_worker_id(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset", json={"worker_id": "e2e-worker-0"})
        assert response.status_code == 200
        assert response.json() == {"status": "reset", "worker_id": "e2e-worker-0"}
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_rejects_missing_body(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset")
        assert response.status_code == 422
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_rejects_malformed_worker_id(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset", json={"worker_id": "not-a-worker"})
        assert response.status_code == 422
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()
```

Leave the module's existing top-of-file docstring, imports, and `_build_client` helper untouched.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_test_router.py -v`
Expected: 4 failures — the response doesn't include `worker_id`, the endpoint accepts empty bodies, and the validator doesn't reject malformed input.

- [ ] **Step 3: Rewrite `test_router.py`**

Open `healthflow/api/test_router.py` and replace the entire contents with:

```python
"""Test-only router. Scoped reset for per-worker e2e isolation.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import delete

from healthflow.database.config import async_session_factory
from healthflow.database.models import (
    ActionHistory,
    Client,
    Feedback,
)
from healthflow.seed_data import seed_for_worker


test_router = APIRouter(prefix="/__test", tags=["test"])

# SQLite is single-writer; serialize the reset transaction to avoid
# `database is locked` errors when many workers reset concurrently.
_reset_lock = asyncio.Lock()


class ResetRequest(BaseModel):
    worker_id: str = Field(..., pattern=r"^e2e-worker-\d+$")


@test_router.post("/reset")
async def reset_db(body: ResetRequest) -> dict:
    """Wipe and re-seed only the requesting worker's broker-scoped data.

    The broker itself is sticky (created once, never deleted) so JWTs stay
    valid across resets. Client/ActionHistory/Feedback rows owned by this
    broker are deleted and the canonical client set is re-inserted.
    """
    async with _reset_lock:
        async with async_session_factory() as session:
            broker = await seed_for_worker(session, body.worker_id)
            # seed_for_worker already wiped + re-inserted Client rows; also
            # wipe ActionHistory and Feedback rows owned by this broker.
            await session.execute(
                delete(ActionHistory).where(ActionHistory.broker_id == broker.id)
            )
            await session.execute(
                delete(Feedback).where(Feedback.broker_id == broker.id)
            )
            await session.commit()
    return {"status": "reset", "worker_id": body.worker_id}
```

Note: `seed_for_worker` already deletes the broker's `Client` rows, and `Client.actions` has `cascade="all, delete-orphan"`, so the explicit `delete(ActionHistory)` is defensive — it also catches stray rows that weren't reachable from a current `Client` (defense-in-depth, cheap). `Feedback` is owned directly by `Broker`, not `Client`, so it must be deleted separately.

- [ ] **Step 4: Run the test_router tests**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_test_router.py -v`
Expected: All 4 tests pass.

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/ -q --tb=short`
Expected: All tests pass (the count was 429 before this work — confirm it's still ≥429).

- [ ] **Step 6: Commit**

```bash
git add healthflow/api/test_router.py healthflow/tests/test_test_router.py
git commit -m "Scope /__test/reset to per-worker broker"
```

---

## Task 3: Simplify `scripts/seed_test_db.py` to schema-only

**Goal:** The seed container no longer needs to know about brokers/clients. It just creates the schema; data lands lazily via `/__test/reset`.

**Files:**
- Modify: `scripts/seed_test_db.py`

- [ ] **Step 1: Replace the script with the schema-only version**

Open `scripts/seed_test_db.py` and replace the entire contents with:

```python
"""Reset the test DB schema. Run inside the backend container by docker-compose.test.yml.

Per-worker data is provisioned lazily via POST /__test/reset (see
healthflow/api/test_router.py). This script only ensures a clean schema
exists at stack startup.
"""
import asyncio

from healthflow.database.config import engine
from healthflow.database.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Confirm the import surface still resolves**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -c "import scripts.seed_test_db; print('ok')"`
Expected: `ok` (no ImportError).

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_test_db.py
git commit -m "Reduce seed_test_db.py to schema-only; data is lazy per worker"
```

---

## Task 4: API audit for cross-broker isolation

**Goal:** Confirm every API route enforces broker-scoping (or is intentionally global). If any route is unscoped, fix it in this task with a regression test. The design depends on this property holding.

**Files:**
- Read: `healthflow/api/routes.py`, `healthflow/api/client_router.py`, `healthflow/api/history_router.py`
- Possibly modify: any router file with an unscoped query
- Create or modify: `healthflow/tests/test_cross_broker_isolation.py`

- [ ] **Step 1: Enumerate every route and check broker scoping**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && grep -rn "@.*\.\(get\|post\|put\|patch\|delete\)" healthflow/api/ --include="*.py" | grep -v __pycache__`

For each route returned, open the file and verify the handler:
1. Resolves a `current_user` (broker) via dependency injection (e.g., `Depends(get_current_broker)`), AND
2. Either filters DB queries by `current_user.id` / `broker_id == current_user.id`, OR is intentionally global (auth login, health check, the test router).

Build a markdown table inline in this step's notes:

```
| Route                          | Scoped? | Notes                                |
|--------------------------------|---------|--------------------------------------|
| POST /auth/login               | n/a     | unauthenticated by design            |
| GET  /clients                  | yes     | filters by current_user.id           |
| GET  /clients/{id}             | ?       | needs check                           |
| ...                            | ...     | ...                                  |
```

- [ ] **Step 2: Write a cross-broker isolation pytest**

Create `healthflow/tests/test_cross_broker_isolation.py`:

```python
"""Broker A must not see/modify/delete broker B's data.

This is the load-bearing property for per-worker e2e isolation. If any route
returns or accepts cross-broker access, it's a real production bug and must
be fixed before parallel e2e workers can be trusted.
"""
import pytest
from httpx import AsyncClient

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


async def _make_broker(session, email: str) -> Broker:
    broker = Broker(
        email=email,
        hashed_password=hash_password("TestWorker123!"),
        full_name=email,
    )
    session.add(broker)
    await session.flush()
    return broker


async def _login(client: AsyncClient, email: str, password: str = "TestWorker123!") -> str:
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.mark.anyio
async def test_broker_cannot_read_other_brokers_clients(client, db_session):
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Only Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.get(
        "/clients", headers={"Authorization": f"Bearer {b_token}"}
    )
    assert res.status_code == 200
    names = [c["full_name"] for c in res.json()]
    assert "A's Only Client" not in names


@pytest.mark.anyio
async def test_broker_cannot_read_other_brokers_client_by_id(client, db_session):
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Only Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.get(
        f"/clients/{a_client.id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    # Either 404 (broker B can't see A's client) or 403 (forbidden) is acceptable.
    # 200 means cross-broker leak — fix the route.
    assert res.status_code in (403, 404), f"Cross-broker read leak: {res.status_code} {res.text}"


@pytest.mark.anyio
async def test_broker_cannot_delete_other_brokers_client(client, db_session):
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Only Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.delete(
        f"/clients/{a_client.id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert res.status_code in (403, 404), f"Cross-broker delete leak: {res.status_code} {res.text}"

    # And A's client should still exist.
    a_token = await _login(client, "iso-a@healthflow.test")
    res = await client.get(
        f"/clients/{a_client.id}",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert res.status_code == 200
```

- [ ] **Step 2a: Run the isolation tests**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_cross_broker_isolation.py -v`
Expected: all 3 tests pass. If any fail, that route has a real cross-broker leak — fix it (the fix is "filter the query by `current_user.id`") before continuing.

- [ ] **Step 3: Run the full backend suite**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/ -q --tb=short`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add healthflow/tests/test_cross_broker_isolation.py
# Plus any router fixes if a leak was found:
# git add healthflow/api/<file_that_was_fixed>.py
git commit -m "Add cross-broker isolation tests; fix any leaks found in audit"
```

---

## Task 5: Worker-aware Playwright fixtures

**Goal:** Each Playwright worker derives a unique broker identity from `testInfo.parallelIndex`. Fixtures use it for resets and login.

**Files:**
- Modify: `frontend/tests/fixtures/test-users.js`
- Modify: `frontend/tests/fixtures/index.js`

- [ ] **Step 1: Replace `test-users.js` with the factory**

Open `frontend/tests/fixtures/test-users.js` and replace the entire contents with:

```js
export function workerBroker(workerIndex) {
  const id = `e2e-worker-${workerIndex}`
  return {
    workerId: id,
    email: `${id}@healthflow.test`,
    password: 'TestWorker123!',
  }
}
```

- [ ] **Step 2: Replace `fixtures/index.js` with the worker-aware version**

Open `frontend/tests/fixtures/index.js` and replace the entire contents with:

```js
import { test as base, expect } from '@playwright/test'
import { workerBroker } from './test-users'

export { expect }

function apiOrigin(baseURL) {
  return baseURL.replace(':5173', ':8000')
}

async function resetForWorker(api, workerId, requester = fetch) {
  const res = await requester(`${api}/__test/reset`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ worker_id: workerId }),
  })
  const ok = typeof res.ok === 'function' ? res.ok() : res.ok
  if (!ok) {
    const text = typeof res.text === 'function' ? await res.text() : await res.text()
    const status = typeof res.status === 'function' ? res.status() : res.status
    throw new Error(`DB reset failed: ${status} ${text}`)
  }
}

export const test = base.extend({
  // Per-worker broker identity (sticky across all tests on this worker).
  workerBroker: [async ({}, use, testInfo) => {
    await use(workerBroker(testInfo.parallelIndex))
  }, { scope: 'test' }],

  // Auto-reset this worker's broker-scoped data before each test.
  page: async ({ page, baseURL, workerBroker }, use) => {
    await resetForWorker(apiOrigin(baseURL), workerBroker.workerId)
    await use(page)
  },

  // Pre-authenticated page using the worker's broker identity.
  authedPage: async ({ context, baseURL, request, workerBroker }, use) => {
    const api = apiOrigin(baseURL)
    await resetForWorker(api, workerBroker.workerId, (url, init) => request.fetch(url, init))

    const loginRes = await request.post(`${api}/auth/login`, {
      data: { email: workerBroker.email, password: workerBroker.password },
    })
    if (!loginRes.ok()) {
      throw new Error(`API login failed: ${loginRes.status()} ${await loginRes.text()}`)
    }
    const { access_token, refresh_token } = await loginRes.json()

    await context.addInitScript(([access, refresh]) => {
      sessionStorage.setItem('hf_token', access)
      sessionStorage.setItem('hf_refresh', refresh)
    }, [access_token, refresh_token])

    const page = await context.newPage()
    await use(page)
  },

  // UI-based login helper, retained for tests that exercise the login form.
  login: async ({ page, workerBroker }, use) => {
    await use(async (creds) => {
      const credsToUse = creds ?? workerBroker
      await page.goto('/login')
      await page.getByLabel(/work email/i).fill(credsToUse.email)
      await page.getByLabel(/credentials/i).fill(credsToUse.password)
      await page.getByRole('button', { name: /authenticate/i }).click()
      await page.waitForURL('/')
    })
  },
})
```

- [ ] **Step 3: Update `auth.spec.js` to use the worker fixture**

`auth.spec.js` imports the removed `broker` constant. Open `frontend/tests/e2e/auth.spec.js` and replace its entire contents with:

```js
import { test, expect } from '../fixtures'

test('broker can log in and reach the dashboard', async ({ page, workerBroker }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(workerBroker.email)
  await page.getByLabel(/credentials/i).fill(workerBroker.password)
  await page.getByRole('button', { name: /authenticate/i }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible()
})

test('invalid credentials show an error', async ({ page, workerBroker }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(workerBroker.email)
  await page.getByLabel(/credentials/i).fill('wrong-password')
  await page.getByRole('button', { name: /authenticate/i }).click()
  // api/client.js throws `Unauthorized` on 401 before reading the detail payload,
  // so that's what surfaces in the login form's error banner.
  await expect(page.getByText(/unauthorized|authentication failed|invalid|incorrect/i)).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test('logged-in broker can sign out', async ({ authedPage }) => {
  await authedPage.goto('/')
  await authedPage.getByRole('button', { name: /sign out/i }).click()
  await expect(authedPage).toHaveURL(/\/login/)
})
```

Note: the `page` fixture's auto-reset (`resetForWorker`) means by the time the first test calls `/login`, the worker's broker exists with the canonical password. So the login test exercises the same broker the `authedPage` fixture would create.

- [ ] **Step 3a: Sanity-check no other spec or src file references the removed export**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent/frontend && grep -rn "import.*\bbroker\b.*from.*test-users\|from '\./test-users'.*\bbroker\b" tests/ src/ 2>/dev/null`
Expected: no output (only `workerBroker` is exported now).

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/fixtures/test-users.js frontend/tests/fixtures/index.js
# Plus any spec files that needed import updates:
# git add frontend/tests/e2e/<spec>.spec.js
git commit -m "Derive Playwright broker identity from per-worker parallelIndex"
```

---

## Task 6: Enable parallelism in `playwright.config.js`

**Goal:** Lift `workers: 1` and let Playwright actually parallelize.

**Files:**
- Modify: `frontend/playwright.config.js`

- [ ] **Step 1: Update the config**

Open `frontend/playwright.config.js` and replace the entire contents with:

```js
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/global-setup.js',
  globalTeardown: './tests/global-teardown.js',
  fullyParallel: true,
  workers: process.env.CI ? 4 : undefined,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit',   use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
```

(Note the deletion of the "Shared backend + single SQLite file" comment block and the `workers: 1` / `fullyParallel: false` lines.)

- [ ] **Step 2: Commit**

```bash
git add frontend/playwright.config.js
git commit -m "Enable Playwright fullyParallel; CI runs 4 workers"
```

---

## Task 7: Add isolation canary spec

**Goal:** A spec deliberately designed to fail if cross-worker data isolation breaks.

**Files:**
- Create: `frontend/tests/e2e/isolation.spec.js`

- [ ] **Step 1: Create the spec**

Create `frontend/tests/e2e/isolation.spec.js`:

```js
import { test, expect } from '../fixtures'

// Canary tests: if these ever run on different workers without isolation,
// the second test sees the first's client and fails.
//
// On the same worker, the per-test reset gives test B a clean slate, so
// they trivially pass. The meaningful case is parallel execution across
// workers — broker scoping is what guarantees B doesn't see A.

async function addClient(page, name) {
  await page.goto('/clients/new')
  await page.getByPlaceholder(/marjorie calloway/i).fill(name)
  await page.getByPlaceholder('10025').fill('10001')
  // Use exact match: '67' is a substring of the insurance-ID placeholder '1356789012'.
  await page.getByPlaceholder('67', { exact: true }).fill('67')
  await page.getByRole('combobox').first().selectOption('low')
  await page.getByRole('button', { name: /create client/i }).click()
}

test('isolation canary A: adds Probe-A and never sees Probe-B', async ({ authedPage }) => {
  await addClient(authedPage, 'Isolation-Probe-A')
  await authedPage.goto('/clients')
  await expect(authedPage.getByText('Isolation-Probe-A')).toBeVisible()
  await expect(authedPage.getByText('Isolation-Probe-B')).toHaveCount(0)
})

test('isolation canary B: adds Probe-B and never sees Probe-A', async ({ authedPage }) => {
  await addClient(authedPage, 'Isolation-Probe-B')
  await authedPage.goto('/clients')
  await expect(authedPage.getByText('Isolation-Probe-B')).toBeVisible()
  await expect(authedPage.getByText('Isolation-Probe-A')).toHaveCount(0)
})
```

Selectors mirror `frontend/tests/e2e/add-client.spec.js` exactly so this spec can't fail for selector reasons that the existing add-client spec wouldn't also fail for.

- [ ] **Step 2: Commit**

```bash
git add frontend/tests/e2e/isolation.spec.js
git commit -m "Add cross-worker isolation canary spec"
```

---

## Task 8: First parallel e2e run (smoke)

**Goal:** Confirm the wired-up parallel suite actually runs end-to-end before doing the full stability sweep.

- [ ] **Step 1: Run the suite with 4 workers, chromium-only (fast smoke)**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent/frontend && npm run test:e2e -- --workers=4 --project=chromium`

Expected: all 4 specs pass (auth, add-client, plan-comparison, isolation).

Failure modes and what they mean:
- **Isolation canary B fails seeing "Isolation-Probe-A"**: cross-broker leak. Re-check Task 2 (reset endpoint scoping) and Task 4 (API audit findings).
- **Reset returns 422**: the fixture's POST body shape doesn't match the Pydantic model. Re-check `resetForWorker` in `fixtures/index.js`.
- **Login fails**: the worker's broker wasn't seeded before login. Confirm `authedPage` calls reset *before* the login POST.
- **Selector errors in the canary**: the canary mirrors `add-client.spec.js`. If both fail the same way, it's a UI change unrelated to this work; open `add-client.spec.js` to see the current selectors and update both.

---

## Task 9: Stability validation

**Goal:** Prove the parallel suite is reliable, not just lucky once.

- [ ] **Step 1: Run the full e2e suite 5 times, all 3 browsers**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent/frontend && for i in 1 2 3 4 5; do echo "=== Run $i ==="; npm run test:e2e -- --workers=4 || { echo "Run $i failed"; break; }; done`

Expected: 5 successful runs in a row. If any flake, open the Playwright HTML report and `playwright-report/` artifacts to diagnose. Don't paper over flakes — they're the signal that isolation is partially broken.

- [ ] **Step 2: Compare wall-clock to the old serial baseline**

Run: `cd /Users/saidukamara/code/projects/health-insurance-agent/frontend && time npm run test:e2e -- --workers=1 --project=chromium` and `time npm run test:e2e -- --workers=4 --project=chromium`. Note the times.

Expected: meaningful speedup (rough target: 2–3× for `workers=4`, not a perfect 4× — there's serial setup/teardown overhead).

- [ ] **Step 3: Update CLAUDE.md / README only if there's a user-visible change to document**

If the parallel-run command differs from what the README documents, update it. Otherwise skip.

- [ ] **Step 4: Final commit (if anything was updated)**

```bash
git add README.md CLAUDE.md
git commit -m "Document parallel e2e run flags"
# (Skip if no docs changed.)
```

---

## Spec Coverage Check

| Spec section                                            | Plan task |
|---------------------------------------------------------|-----------|
| Worker identity (`e2e-worker-{N}`, lazy broker)         | Task 1, Task 5 |
| Scoped `/__test/reset` with `worker_id` validation      | Task 2 |
| `seed_for_worker` (idempotent, sticky broker)           | Task 1 |
| `_reset_lock` retained                                  | Task 2 (verbatim in code) |
| `scripts/seed_test_db.py` schema-only                   | Task 3 |
| API audit                                                | Task 4 |
| `frontend/tests/fixtures/test-users.js` factory          | Task 5 |
| `frontend/tests/fixtures/index.js` worker fixture        | Task 5 |
| `frontend/playwright.config.js` parallelism              | Task 6 |
| Reset endpoint pytest (5 cases)                         | Task 1 + Task 2 |
| Cross-broker isolation pytest                            | Task 4 |
| E2E parallel run + 5-run stability                       | Task 8, Task 9 |
| Cross-pollution canary spec                              | Task 7 |
| CI workflow (no structural change)                       | n/a (verified by Task 9 + CI itself) |
