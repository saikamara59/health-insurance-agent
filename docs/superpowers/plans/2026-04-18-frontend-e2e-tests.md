# Frontend E2E Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Playwright e2e coverage for the broker's golden flows (login, add client, plan comparison) running on every push across Chromium, Firefox, and WebKit, against the live docker-compose backend stack.

**Architecture:** Backend exposes an env-gated `POST /__test/reset` endpoint that wipes + reseeds the DB via a new `healthflow/seed_data.py` module. A `docker-compose.test.yml` overlay runs the backend with `HEALTHFLOW_TEST_MODE=1` against a tmpfs SQLite. Playwright spins up Vite locally, fixtures auto-call the reset endpoint before each test, and three spec files cover the golden flows.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / pytest (existing). New: `@playwright/test` (Node 20), Docker Compose, GitHub Actions.

Spec: `docs/superpowers/specs/2026-04-18-frontend-e2e-tests-design.md`

**Notes for the implementer:**
- Selectors below were chosen by reading the actual JSX. Login uses labels "Work Email" and "Credentials" (not "Email" / "Password"). Submit button text is "Authenticate". After login, the app navigates to `/` (root), where DashboardPage renders an h1 starting with "Good morning, ".
- Logout button is in `frontend/src/components/Sidebar.jsx` with `aria-label="Sign out"`.
- Run backend tests with `python3 -m pytest healthflow/tests/...` (the `pytest` binary is not on PATH; activate the venv or use the module form).

---

### Task 1: Add `healthflow/seed_data.py` (constants + DB seeder)

**Files:**
- Create: `healthflow/seed_data.py`
- Create: `healthflow/tests/test_seed_data.py`

- [ ] **Step 1: Write the failing test**

Create `healthflow/tests/test_seed_data.py`:

```python
import pytest
from sqlalchemy import select

from healthflow.database.models import Broker, Client
from healthflow.seed_data import TEST_BROKER, TEST_CLIENTS, seed_db


@pytest.mark.anyio
async def test_seed_db_creates_test_broker(db_session):
    await seed_db(db_session)
    await db_session.commit()
    result = await db_session.execute(select(Broker).where(Broker.email == TEST_BROKER["email"]))
    broker = result.scalar_one()
    assert broker.full_name == TEST_BROKER["full_name"]


@pytest.mark.anyio
async def test_seed_db_creates_test_clients(db_session):
    await seed_db(db_session)
    await db_session.commit()
    result = await db_session.execute(select(Client))
    clients = result.scalars().all()
    assert len(clients) == len(TEST_CLIENTS)
    names = {c.full_name for c in clients}
    assert names == {c["full_name"] for c in TEST_CLIENTS}


@pytest.mark.anyio
async def test_seed_db_clients_belong_to_test_broker(db_session):
    await seed_db(db_session)
    await db_session.commit()
    broker_result = await db_session.execute(select(Broker).where(Broker.email == TEST_BROKER["email"]))
    broker = broker_result.scalar_one()
    client_result = await db_session.execute(select(Client))
    clients = client_result.scalars().all()
    assert all(c.broker_id == broker.id for c in clients)
```

- [ ] **Step 2: Confirm it fails**

```bash
python3 -m pytest healthflow/tests/test_seed_data.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'healthflow.seed_data'`.

- [ ] **Step 3: Implement `healthflow/seed_data.py`**

```python
"""Canonical test seed data and DB-direct seeder for the e2e test stack.

Used by `healthflow/api/test_router.py`'s reset endpoint. Distinct from the
top-level `seed.py` (which is an HTTP-based broker tool).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


TEST_BROKER = {
    "email": "broker@healthflow.test",
    "password": "TestBroker123!",
    "full_name": "E2E Test Broker",
}

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


async def seed_db(session: AsyncSession) -> None:
    """Insert TEST_BROKER and TEST_CLIENTS into a fresh schema.

    Caller is responsible for committing.
    """
    broker = Broker(
        email=TEST_BROKER["email"],
        hashed_password=hash_password(TEST_BROKER["password"]),
        full_name=TEST_BROKER["full_name"],
    )
    session.add(broker)
    await session.flush()

    for client_data in TEST_CLIENTS:
        client = Client(
            broker_id=broker.id,
            full_name=client_data["full_name"],
            zip_code=client_data["zip_code"],
            age=client_data["age"],
            income_level=client_data["income_level"],
            doctors=client_data["doctors"],
            prescriptions=client_data["prescriptions"],
            procedures=client_data["procedures"],
        )
        session.add(client)
    await session.flush()
```

- [ ] **Step 4: Confirm tests pass**

```bash
python3 -m pytest healthflow/tests/test_seed_data.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add healthflow/seed_data.py healthflow/tests/test_seed_data.py
git commit -m "feat: add seed_data module with TEST_BROKER and seed_db"
```

---

### Task 2: Add env-gated test reset router

**Files:**
- Create: `healthflow/api/test_router.py`
- Create: `healthflow/tests/test_test_router.py`

- [ ] **Step 1: Write the failing test (env-gating + reset behavior)**

Create `healthflow/tests/test_test_router.py`:

```python
import os
from importlib import reload

import pytest
from sqlalchemy import select

from healthflow.database.models import Broker, Client
from healthflow.seed_data import TEST_BROKER


@pytest.mark.anyio
async def test_reset_endpoint_returns_404_when_test_mode_off(client, monkeypatch):
    monkeypatch.delenv("HEALTHFLOW_TEST_MODE", raising=False)
    # main.py decides include based on env var at import time, so reload
    import healthflow.main as main_module
    reload(main_module)
    response = await client.post("/__test/reset")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_reset_endpoint_works_when_test_mode_on(client, monkeypatch):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    import healthflow.main as main_module
    reload(main_module)
    response = await client.post("/__test/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "reset"}


@pytest.mark.anyio
async def test_reset_endpoint_seeds_test_broker(client, monkeypatch, db_session):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    import healthflow.main as main_module
    reload(main_module)
    await client.post("/__test/reset")
    result = await db_session.execute(select(Broker).where(Broker.email == TEST_BROKER["email"]))
    broker = result.scalar_one_or_none()
    assert broker is not None
    assert broker.full_name == TEST_BROKER["full_name"]


@pytest.mark.anyio
async def test_reset_endpoint_clears_existing_data(client, monkeypatch, db_session):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    import healthflow.main as main_module
    reload(main_module)

    # First reset, then add a stray client
    await client.post("/__test/reset")
    broker_result = await db_session.execute(select(Broker))
    broker = broker_result.scalars().first()
    db_session.add(Client(
        broker_id=broker.id,
        full_name="Stray Client",
        zip_code="99999",
        age=99,
        income_level="low",
        doctors=[],
        prescriptions=[],
        procedures=[],
    ))
    await db_session.commit()

    # Second reset should remove the stray
    await client.post("/__test/reset")
    result = await db_session.execute(select(Client).where(Client.full_name == "Stray Client"))
    assert result.scalar_one_or_none() is None
```

- [ ] **Step 2: Confirm it fails**

```bash
python3 -m pytest healthflow/tests/test_test_router.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'healthflow.api.test_router'` or with `405`/`404` responses.

- [ ] **Step 3: Implement `healthflow/api/test_router.py`**

```python
"""Test-only router. Wipes and re-seeds the DB.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from healthflow.database.config import engine, get_db
from healthflow.database.models import Base
from healthflow.seed_data import seed_db


test_router = APIRouter(prefix="/__test", tags=["test"])


@test_router.post("/reset")
async def reset_db(db: AsyncSession = Depends(get_db)) -> dict:
    """Drop all tables, recreate schema, re-seed with TEST_BROKER + TEST_CLIENTS."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await seed_db(db)
    await db.commit()
    return {"status": "reset"}
```

- [ ] **Step 4: Wire conditional registration in `healthflow/main.py`**

Find the existing imports section. After `from healthflow.feedback.router import feedback_router`, add:

```python
import logging
import os
```

(Only add `import logging` and `import os` if not already imported above.)

Find the section where routers are included (the block of `app.include_router(...)` calls). After the last existing include, add:

```python
if os.getenv("HEALTHFLOW_TEST_MODE") == "1":
    from healthflow.api.test_router import test_router
    app.include_router(test_router)
    logging.warning("⚠️ test reset endpoint enabled — never run in production")
```

- [ ] **Step 5: Confirm tests pass**

```bash
python3 -m pytest healthflow/tests/test_test_router.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Confirm full backend suite still passes**

```bash
python3 -m pytest healthflow/tests/ -q
```

Expected: all tests pass (430+ now).

- [ ] **Step 7: Commit**

```bash
git add healthflow/api/test_router.py healthflow/main.py healthflow/tests/test_test_router.py
git commit -m "feat: add env-gated /__test/reset endpoint for e2e DB isolation"
```

---

### Task 3: Add backend healthcheck to `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add healthcheck to backend service**

In `docker-compose.yml`, find the `backend:` service block. Inside it, after the `restart: unless-stopped` line, add:

```yaml
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 2s
      timeout: 3s
      retries: 15
      start_period: 5s
```

The full backend service block should now look like:

```yaml
  backend:
    build:
      context: .
      target: backend
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - JWT_SECRET=${JWT_SECRET:-healthflow-dev-secret-change-in-production}
      - DATABASE_URL=${DATABASE_URL:-sqlite+aiosqlite:///healthflow.db}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 2s
      timeout: 3s
      retries: 15
      start_period: 5s
```

- [ ] **Step 2: Verify the YAML parses**

```bash
docker compose -f docker-compose.yml config > /dev/null && echo OK
```

Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add healthcheck to backend service"
```

---

### Task 4: Create `docker-compose.test.yml`

**Files:**
- Create: `docker-compose.test.yml`

- [ ] **Step 1: Write the override file**

Create `docker-compose.test.yml`:

```yaml
services:
  backend:
    environment:
      - ANTHROPIC_API_KEY=test-key-not-used
      - JWT_SECRET=test-secret
      - DATABASE_URL=sqlite+aiosqlite:////data/healthflow_test.db
      - HEALTHFLOW_TEST_MODE=1
    tmpfs:
      - /data

  seed:
    build:
      context: .
      target: backend
    environment:
      - ANTHROPIC_API_KEY=test-key-not-used
      - JWT_SECRET=test-secret
      - DATABASE_URL=sqlite+aiosqlite:////data/healthflow_test.db
      - HEALTHFLOW_TEST_MODE=1
    depends_on:
      backend:
        condition: service_healthy
    command: ["python", "-c", "import asyncio; from healthflow.database.config import engine, get_db; from healthflow.database.models import Base; from healthflow.seed_data import seed_db; from sqlalchemy.ext.asyncio import AsyncSession\nasync def main():\n    async with engine.begin() as conn:\n        await conn.run_sync(Base.metadata.drop_all)\n        await conn.run_sync(Base.metadata.create_all)\n    async for s in get_db():\n        await seed_db(s); await s.commit(); break\nasyncio.run(main())"]
```

- [ ] **Step 2: Reconsider — the inline command is too brittle**

The inline `command` above has multiline Python in a YAML string, which is hard to maintain. Replace it with a small helper script.

Create `scripts/seed_test_db.py`:

```python
"""Wipe + reseed the test DB. Run inside the backend container by docker-compose.test.yml."""
import asyncio

from healthflow.database.config import engine, get_db
from healthflow.database.models import Base
from healthflow.seed_data import seed_db


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async for session in get_db():
        await seed_db(session)
        await session.commit()
        break


if __name__ == "__main__":
    asyncio.run(main())
```

Then rewrite `docker-compose.test.yml` to use it:

```yaml
services:
  backend:
    environment:
      - ANTHROPIC_API_KEY=test-key-not-used
      - JWT_SECRET=test-secret
      - DATABASE_URL=sqlite+aiosqlite:////data/healthflow_test.db
      - HEALTHFLOW_TEST_MODE=1
    tmpfs:
      - /data

  seed:
    build:
      context: .
      target: backend
    environment:
      - ANTHROPIC_API_KEY=test-key-not-used
      - JWT_SECRET=test-secret
      - DATABASE_URL=sqlite+aiosqlite:////data/healthflow_test.db
      - HEALTHFLOW_TEST_MODE=1
    depends_on:
      backend:
        condition: service_healthy
    command: ["python", "scripts/seed_test_db.py"]
```

- [ ] **Step 3: Verify the merged compose parses**

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml config > /dev/null && echo OK
```

Expected: prints `OK`.

- [ ] **Step 4: Smoke test the stack manually**

```bash
ANTHROPIC_API_KEY=stub JWT_SECRET=stub docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --wait
```

Expected: backend reports healthy and `seed` exits 0 within ~30 seconds.

Verify the reset endpoint works through the running stack:

```bash
curl -s -X POST http://localhost:8000/__test/reset
```

Expected: `{"status":"reset"}`.

Tear down:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml down -v --remove-orphans
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.test.yml scripts/seed_test_db.py
git commit -m "feat: add docker-compose.test.yml and seed_test_db helper"
```

---

### Task 5: Add `data-testid` to plan and client rows

**Files:**
- Modify: `frontend/src/pages/PlanComparisonPage.jsx` (line 283)
- Modify: `frontend/src/pages/ClientListPage.jsx` (line 142)

- [ ] **Step 1: Edit `PlanComparisonPage.jsx`**

Find this line (around line 283):

```jsx
                  <div key={p.plan_id || i} className={`plan-card ${isBest ? 'best' : ''}`}>
```

Replace with:

```jsx
                  <div key={p.plan_id || i} data-testid="plan-row" className={`plan-card ${isBest ? 'best' : ''}`}>
```

- [ ] **Step 2: Edit `ClientListPage.jsx`**

Find this line (around line 142):

```jsx
                  <tr key={c.id} className="row" onClick={() => navigate(`/clients/${c.id}`)}>
```

Replace with:

```jsx
                  <tr key={c.id} data-testid="client-row" className="row" onClick={() => navigate(`/clients/${c.id}`)}>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/PlanComparisonPage.jsx frontend/src/pages/ClientListPage.jsx
git commit -m "feat: add data-testid to plan and client rows for e2e selectors"
```

---

### Task 6: Install Playwright + scripts + .gitignore

**Files:**
- Modify: `frontend/package.json`
- Modify: `.gitignore`

- [ ] **Step 1: Install Playwright**

```bash
cd frontend && npm install --save-dev @playwright/test && cd ..
```

- [ ] **Step 2: Install browsers**

```bash
cd frontend && npx playwright install --with-deps chromium firefox webkit && cd ..
```

(On CI this is repeated; locally it caches.)

- [ ] **Step 3: Add scripts to `frontend/package.json`**

In the `"scripts"` block, after `"preview": "vite preview"`, add:

```json
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
```

The full scripts block should look like:

```json
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  },
```

- [ ] **Step 4: Update `.gitignore`**

Append to `.gitignore`:

```
frontend/playwright-report/
frontend/test-results/
frontend/playwright/.cache/
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json .gitignore
git commit -m "chore: install @playwright/test and gitignore artifacts"
```

---

### Task 7: Create `frontend/playwright.config.js`

**Files:**
- Create: `frontend/playwright.config.js`

- [ ] **Step 1: Write the config**

Create `frontend/playwright.config.js`:

```js
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/global-setup.js',
  globalTeardown: './tests/global-teardown.js',
  fullyParallel: true,
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

- [ ] **Step 2: Commit**

```bash
git add frontend/playwright.config.js
git commit -m "chore: add playwright.config.js"
```

---

### Task 8: Add `__test` proxy to `vite.config.js`

**Files:**
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Add `/__test` to the proxy table**

In `frontend/vite.config.js`, find the `proxy:` block. After the existing `'/feedback': 'http://localhost:8000',` line, add:

```js
      '/__test': 'http://localhost:8000',
```

The full block should now look like:

```js
    proxy: {
      '/auth': 'http://localhost:8000',
      '/clients': 'http://localhost:8000',
      '/compare': 'http://localhost:8000',
      '/calculate': 'http://localhost:8000',
      '/translate': 'http://localhost:8000',
      '/appeal': 'http://localhost:8000',
      '/verify': 'http://localhost:8000',
      '/estimate': 'http://localhost:8000',
      '/plans': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
      '/__test': 'http://localhost:8000',
    }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/vite.config.js
git commit -m "chore: proxy /__test through Vite to backend"
```

---

### Task 9: Create test fixtures

**Files:**
- Create: `frontend/tests/fixtures/test-users.js`
- Create: `frontend/tests/fixtures/index.js`

- [ ] **Step 1: Write `test-users.js`**

Create `frontend/tests/fixtures/test-users.js`:

```js
export const broker = {
  email: 'broker@healthflow.test',
  password: 'TestBroker123!',
}
```

- [ ] **Step 2: Write `index.js` (custom test fixture with auto-reset + login helper)**

Create `frontend/tests/fixtures/index.js`:

```js
import { test as base, expect } from '@playwright/test'

export { expect }

export const test = base.extend({
  // Auto-reset DB before each test by calling the backend reset endpoint directly.
  page: async ({ page, baseURL }, use) => {
    const apiURL = baseURL.replace(':5173', ':8000')
    const res = await fetch(`${apiURL}/__test/reset`, { method: 'POST' })
    if (!res.ok) {
      throw new Error(`DB reset failed: ${res.status} ${await res.text()}`)
    }
    await use(page)
  },
  // Reusable login helper. Usage: await login(broker)
  login: async ({ page }, use) => {
    await use(async (creds) => {
      await page.goto('/login')
      await page.getByLabel(/work email/i).fill(creds.email)
      await page.getByLabel(/credentials/i).fill(creds.password)
      await page.getByRole('button', { name: /authenticate/i }).click()
      await page.waitForURL('/')
    })
  },
})
```

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/fixtures/test-users.js frontend/tests/fixtures/index.js
git commit -m "chore: add Playwright test fixtures (auto-reset + login helper)"
```

---

### Task 10: Create global-setup and global-teardown

**Files:**
- Create: `frontend/tests/global-setup.js`
- Create: `frontend/tests/global-teardown.js`

- [ ] **Step 1: Write `global-setup.js`**

Create `frontend/tests/global-setup.js`:

```js
import { spawnSync } from 'node:child_process'

export default async function globalSetup() {
  console.log('🐳 Starting docker-compose test stack...')
  const result = spawnSync(
    'docker',
    [
      'compose',
      '-f', '../docker-compose.yml',
      '-f', '../docker-compose.test.yml',
      'up', '-d', '--wait',
    ],
    {
      stdio: 'inherit',
      env: {
        ...process.env,
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || 'test-key-not-used',
        JWT_SECRET: process.env.JWT_SECRET || 'test-secret',
      },
    }
  )
  if (result.status !== 0) {
    console.error('❌ docker compose up failed; dumping logs:')
    spawnSync(
      'docker',
      ['compose', '-f', '../docker-compose.yml', '-f', '../docker-compose.test.yml', 'logs', 'backend', 'seed'],
      { stdio: 'inherit' }
    )
    throw new Error(`docker compose up failed with exit code ${result.status}`)
  }
  console.log('✅ Stack up and seeded')
}
```

- [ ] **Step 2: Write `global-teardown.js`**

Create `frontend/tests/global-teardown.js`:

```js
import { spawnSync } from 'node:child_process'

export default async function globalTeardown() {
  console.log('🐳 Tearing down docker-compose test stack...')
  spawnSync(
    'docker',
    [
      'compose',
      '-f', '../docker-compose.yml',
      '-f', '../docker-compose.test.yml',
      'down', '-v', '--remove-orphans',
    ],
    { stdio: 'inherit' }
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/global-setup.js frontend/tests/global-teardown.js
git commit -m "chore: add Playwright global setup/teardown for docker stack"
```

---

### Task 11: Write `auth.spec.js`

**Files:**
- Create: `frontend/tests/e2e/auth.spec.js`

- [ ] **Step 1: Write the spec**

Create `frontend/tests/e2e/auth.spec.js`:

```js
import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can log in and reach the dashboard', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(broker.email)
  await page.getByLabel(/credentials/i).fill(broker.password)
  await page.getByRole('button', { name: /authenticate/i }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: /good morning/i })).toBeVisible()
})

test('invalid credentials show an error', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel(/work email/i).fill(broker.email)
  await page.getByLabel(/credentials/i).fill('wrong-password')
  await page.getByRole('button', { name: /authenticate/i }).click()
  await expect(page.getByText(/authentication failed|invalid|incorrect/i)).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test('logged-in broker can sign out', async ({ page, login }) => {
  await login(broker)
  await page.getByRole('button', { name: /sign out/i }).click()
  await expect(page).toHaveURL(/\/login/)
})
```

- [ ] **Step 2: Run the spec (requires the docker stack up; global-setup handles this)**

```bash
cd frontend && npm run test:e2e -- auth.spec.js && cd ..
```

Expected: 3 tests × 3 browsers = 9 passed.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/auth.spec.js
git commit -m "test: e2e coverage for login, invalid creds, and logout"
```

---

### Task 12: Write `add-client.spec.js`

**Files:**
- Create: `frontend/tests/e2e/add-client.spec.js`

- [ ] **Step 1: Write the spec**

Create `frontend/tests/e2e/add-client.spec.js`:

```js
import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can add a new client and see them in the list', async ({ page, login }) => {
  await login(broker)
  await page.goto('/clients/new')

  const name = `E2E Client ${Date.now()}`
  // AddClientPage labels are visual-only (no htmlFor), so use placeholders
  await page.getByPlaceholder(/marjorie calloway/i).fill(name)
  await page.getByPlaceholder('10025').fill('10001')
  await page.getByPlaceholder('67').fill('67')
  await page.getByRole('combobox').first().selectOption('low')
  await page.getByRole('button', { name: /create client/i }).click()

  await page.goto('/clients')
  await expect(page.getByText(name)).toBeVisible()
})
```

- [ ] **Step 2: Run the spec**

```bash
cd frontend && npm run test:e2e -- add-client.spec.js && cd ..
```

Expected: 1 test × 3 browsers = 3 passed.

If the test fails because a placeholder selector doesn't match, open `frontend/src/pages/AddClientPage.jsx` and verify the actual placeholder text. The form uses placeholders "Marjorie Calloway" / "10025" / "67" today; if those change, update the spec to match.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/add-client.spec.js
git commit -m "test: e2e coverage for add-client flow"
```

---

### Task 13: Write `plan-comparison.spec.js`

**Files:**
- Create: `frontend/tests/e2e/plan-comparison.spec.js`

- [ ] **Step 1: Write the spec**

Create `frontend/tests/e2e/plan-comparison.spec.js`:

```js
import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can run plan comparison for a seeded client and see ranked plans', async ({ page, login }) => {
  await login(broker)
  await page.goto('/compare')
  // PlanComparisonPage has a client-selector <select>; seed_data.py provides Eleanor Rigby
  await page.getByRole('combobox').first().selectOption({ label: /eleanor rigby/i })
  await page.getByRole('button', { name: /compare plans/i }).click()

  // Plan fetch hits real CMS data via the seeded backend — give it generous time
  const planRows = page.getByTestId('plan-row')
  await expect(planRows.first()).toBeVisible({ timeout: 30_000 })
  await expect(planRows.first()).toContainText(/\$/)
})
```

- [ ] **Step 2: Run the spec**

```bash
cd frontend && npm run test:e2e -- plan-comparison.spec.js && cd ..
```

Expected: 1 test × 3 browsers = 3 passed.

If the test fails because the client dropdown structure changed, open `frontend/src/pages/PlanComparisonPage.jsx` and confirm the select element is still the first combobox on the page. If `/compare` requires additional form fields before the button is enabled, fill them in the test before clicking.

- [ ] **Step 3: Run all specs together**

```bash
cd frontend && npm run test:e2e && cd ..
```

Expected: 5 tests × 3 browsers = 15 passed.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/e2e/plan-comparison.spec.js
git commit -m "test: e2e coverage for plan comparison flow"
```

---

### Task 14: Add CI workflow

**Files:**
- Create: `.github/workflows/e2e.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: E2E Tests

on:
  push:
    branches: ['**']

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend deps
        working-directory: frontend
        run: npm ci

      - name: Install Playwright browsers
        working-directory: frontend
        run: npx playwright install --with-deps chromium firefox webkit

      - name: Build & start docker stack
        env:
          ANTHROPIC_API_KEY: test-key-not-used
          JWT_SECRET: test-secret
        run: docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --wait

      - name: Run Playwright
        working-directory: frontend
        env:
          CI: true
        run: npm run test:e2e

      - name: Tear down docker stack
        if: always()
        run: docker compose -f docker-compose.yml -f docker-compose.test.yml down -v --remove-orphans

      - name: Upload Playwright report on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-${{ github.run_id }}
          path: frontend/playwright-report/
          retention-days: 14

      - name: Upload traces & videos on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-traces-${{ github.run_id }}
          path: frontend/test-results/
          retention-days: 14
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/e2e.yml
git commit -m "ci: run Playwright e2e tests on every push"
```

---

### Task 15: Final verification

**Files:** none

- [ ] **Step 1: Full backend pytest**

```bash
python3 -m pytest healthflow/tests/ -q
```

Expected: all tests pass (430+ now with the 7 new backend tests added in Tasks 1-2).

- [ ] **Step 2: Full e2e locally**

```bash
cd frontend && npm run test:e2e && cd ..
```

Expected: 5 tests × 3 browsers = 15 passed in ~2 minutes.

- [ ] **Step 3: Confirm no test artifacts leaked into git**

```bash
git status --short
git ls-files frontend/playwright-report frontend/test-results 2>/dev/null
```

Expected: working tree clean (or only pre-existing unrelated changes). The `git ls-files` command prints nothing.

- [ ] **Step 4: Push the branch and watch CI**

If working on a feature branch, push it and open the GitHub Actions tab. Confirm the `E2E Tests` workflow runs, completes green, and (if a test were to fail) artifacts upload correctly.

---

## Notes on edge cases & known landmines

- **Login form has TWO modes (sign in vs register).** The fixture's login uses sign-in mode (default). If `isRegisterMode` ever becomes the default, fixtures break. Don't change the LoginPage default mode.
- **`reload(main_module)`** in test_router tests is necessary because router inclusion is decided at import time via `os.getenv`. Tests must reload the module after monkeypatching the env var. This is brittle but pragmatic.
- **`tmpfs` on docker-compose** requires Docker for Linux semantics. On macOS Docker Desktop this works because containers run inside a VM that supports tmpfs. CI uses `ubuntu-latest` so this is fine.
- **The seed service exits 0 immediately** after seeding. `--wait` blocks until backend is healthy AND seed has exited; both are required.
- **First docker build is slow (~3-5min)** because it runs `pip install` for the backend image. CI gets no Docker layer cache by default. If CI time becomes a problem, follow up with `docker/build-push-action` + `cache-from: type=gha`.
- **Plan comparison uses real CMS data via the live seeded backend.** Network calls happen — that's why the assertion has `timeout: 30_000`. If CMS is down during a CI run, this test will flake. Acceptable for a v1.
- **Add-client navigation: `/clients/new`** assumes the route exists. Verify by checking `frontend/src/main.jsx` route definitions. If the route is named differently (e.g. `/add-client`), update the spec.
