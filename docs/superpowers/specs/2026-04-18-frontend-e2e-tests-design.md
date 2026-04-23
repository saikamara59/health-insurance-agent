# Frontend E2E Tests with Playwright — Design

**Date:** 2026-04-18
**Author:** Saidu Kamara
**Status:** Draft

## Problem

The HealthFlow React frontend has 18 pages and zero automated tests. The only safety net today is the 423 backend pytest tests, which can't catch regressions in routing, form wiring, broken API calls from the UI, or rendering bugs. Manual smoke testing doesn't scale and doesn't run on every push.

## Goal

Stand up Playwright e2e tests covering the broker's golden flows — login, add a client, run a plan comparison — running on every push across Chromium, Firefox, and WebKit. Tests target the live docker-compose stack so they exercise the same code path production uses.

## Non-goals

- Component-level / unit tests (Vitest + React Testing Library) — separate concern.
- Visual regression testing (screenshot diffing).
- Cross-spec test parallelism beyond what Playwright gives us out of the box.
- Mocking the LLM — golden flows here don't hit the agent layer; if a future flow does, it gets mocked at the agent layer in a follow-up.
- Replacing the existing pytest suite. Both run side-by-side.

## Scope

Three golden flows × three browsers × auto-DB-reset between specs:

1. **Auth** — login (happy + invalid creds), logout.
2. **Add client** — login → add client → see in client list.
3. **Plan comparison** — login → open seeded client → run comparison → see ranked plans.

Five test cases total. Estimated runtime: ~90s for the full matrix.

## Architecture

### File layout

```
docker-compose.test.yml            (new — overrides for tests)
frontend/
  package.json                     (modify — add @playwright/test, scripts)
  playwright.config.js             (new)
  tests/
    e2e/
      auth.spec.js                 (new)
      add-client.spec.js           (new)
      plan-comparison.spec.js      (new)
    fixtures/
      index.js                     (new — custom test fixture)
      test-users.js                (new — broker creds)
    global-setup.js                (new)
    global-teardown.js             (new)
  playwright-report/               (gitignored)
  test-results/                    (gitignored)
healthflow/
  api/test_router.py               (new — DB reset endpoint, env-gated)
  main.py                          (modify — conditionally include test_router)
seed.py                            (modify — extract run_seed() function)
docker-compose.yml                 (modify — add backend healthcheck)
.github/workflows/e2e.yml          (new)
.gitignore                         (modify — add playwright-report/, test-results/)
```

### Stack orchestration

The docker-compose stack provides the backend and redis. Playwright spins up Vite locally so frontend hot-reload still works during test development. The test override (`docker-compose.test.yml`) extends the base compose with:

- A `tmpfs`-backed test SQLite at `/data/healthflow_test.db` so DB state never touches host disk.
- `DATABASE_URL=sqlite+aiosqlite:////data/healthflow_test.db`.
- `JWT_SECRET=test-secret` and `ANTHROPIC_API_KEY=test-key-not-used`.
- `HEALTHFLOW_TEST_MODE=1` env var to enable the test reset endpoint.
- A one-shot `seed` service that depends on backend healthcheck, runs `python seed.py`, and exits.

### Backend healthcheck

Added to `docker-compose.yml` (useful for production too, not just tests):

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
  interval: 2s
  timeout: 3s
  retries: 15
```

`docker compose ... up -d --wait` blocks until backend reports healthy, then waits for `seed` to exit 0.

### Test reset endpoint

`healthflow/api/test_router.py` exposes `POST /__test/reset`:

1. Drops all tables via `Base.metadata.drop_all`.
2. Recreates schema via `Base.metadata.create_all`.
3. Calls `seed_db(session)` to insert the test broker and a small set of test clients directly via SQLAlchemy.
4. Returns `{"status": "reset"}`.

The router is **only included** in `healthflow/main.py` when `os.getenv("HEALTHFLOW_TEST_MODE") == "1"`. Production never sets it. On startup, when the env var is on, the app logs a warning: `"⚠️ test reset endpoint enabled — never run in production"`.

A new module `healthflow/seed_data.py` holds the canonical seed data — `TEST_BROKER` (email/password/full_name) and `TEST_CLIENTS` (a list of 3 client dicts with name/zip/age). `seed_db(session)` lives there too and creates rows directly via SQLAlchemy (using `hash_password` from `healthflow.auth.security` for the broker's password). The existing `seed.py` is left unchanged — it remains the HTTP-based broker/CLI tool. Test infrastructure depends only on `seed_data.py`, not on `seed.py`.

The "reuse seed.py" choice from brainstorming Question 7 is honored in spirit: tests use the same brokerage workflow data shape but via a faster, dependency-free DB path. Keeping `seed.py` separate avoids forcing the CLI tool to grow a session/engine API.

### Playwright config (`frontend/playwright.config.js`)

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

The Vite dev server proxies `/api/*` to the backend container at `http://localhost:8000`. Vite config addition:

```js
server: {
  proxy: {
    '/api': 'http://localhost:8000',
  },
},
```

### Custom test fixture (`tests/fixtures/index.js`)

```js
import { test as base, expect } from '@playwright/test'
export { expect }

export const test = base.extend({
  page: async ({ page, baseURL }, use) => {
    const apiURL = baseURL.replace('5173', '8000')
    const res = await fetch(`${apiURL}/__test/reset`, { method: 'POST' })
    if (!res.ok) throw new Error(`DB reset failed: ${res.status}`)
    await use(page)
  },
  login: async ({ page }, use) => {
    await use(async (creds) => {
      await page.goto('/login')
      await page.getByLabel('Email').fill(creds.email)
      await page.getByLabel('Password').fill(creds.password)
      await page.getByRole('button', { name: /sign in/i }).click()
      await page.waitForURL(/\/dashboard/)
    })
  },
})
```

`page` is overridden to call the reset endpoint before each test. `login` is a reusable async helper for tests beyond the auth spec.

### Test users fixture (`tests/fixtures/test-users.js`)

```js
export const broker = {
  email: 'broker@healthflow.test',
  password: 'TestBroker123!',
}
```

`seed.py` is updated (idempotently — `INSERT OR IGNORE` semantics) to ensure this broker account exists.

### Global setup / teardown

`global-setup.js`:
1. Spawn `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --wait`.
2. On non-zero exit, dump logs from `backend` and `seed` services and throw.
3. Resolve.

`global-teardown.js`:
1. Spawn `docker compose -f docker-compose.yml -f docker-compose.test.yml down -v --remove-orphans`.
2. Best-effort — log but don't throw on failure.

In CI both run unconditionally. Locally, `reuseExistingServer` lets you keep the stack up across runs by skipping the teardown manually if needed.

## Golden Flow Specs

### `auth.spec.js`

```js
import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can log in and reach dashboard', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(broker.email)
  await page.getByLabel('Password').fill(broker.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible()
})

test('invalid credentials show an error', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(broker.email)
  await page.getByLabel('Password').fill('wrong-password')
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page.getByText(/invalid|incorrect|wrong/i)).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test('logged-in broker can log out', async ({ page, login }) => {
  await login(broker)
  await page.getByRole('button', { name: /log ?out|sign ?out/i }).click()
  await expect(page).toHaveURL(/\/login/)
})
```

### `add-client.spec.js`

```js
import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can add a new client and see them in the list', async ({ page, login }) => {
  await login(broker)
  await page.getByRole('link', { name: /add client/i }).click()

  const name = `E2E Client ${Date.now()}`
  await page.getByLabel(/full name/i).fill(name)
  await page.getByLabel(/zip/i).fill('10001')
  await page.getByLabel(/age/i).fill('67')
  await page.getByRole('button', { name: /save|add|create/i }).click()

  await page.getByRole('link', { name: /clients/i }).click()
  await expect(page.getByText(name)).toBeVisible()
})
```

### `plan-comparison.spec.js`

```js
import { test, expect } from '../fixtures'
import { broker } from '../fixtures/test-users'

test('broker can run plan comparison for a seeded client and see ranked plans', async ({ page, login }) => {
  await login(broker)
  await page.getByRole('link', { name: /clients/i }).click()
  // seed.py creates 15 real-named clients; pick the first row to avoid coupling
  // tests to specific seed names (which may change as the seed evolves).
  await page.getByTestId('client-row').first().click()
  await page.getByRole('button', { name: /compare plans/i }).click()

  await expect(page.getByRole('heading', { name: /comparison|results/i })).toBeVisible({ timeout: 30000 })
  const planRows = page.getByTestId('plan-row')
  await expect(planRows).not.toHaveCount(0)
  await expect(planRows.first()).toContainText(/\$/)
})
```

## Selector Strategy

Tests use `getByRole`, `getByLabel`, `getByText` wherever possible — these tie tests to user-visible behavior, not DOM internals. Two `data-testid` additions are needed:

- `data-testid="plan-row"` on the comparison results row — `getByRole('row')` would match table headers + chrome.
- `data-testid="client-row"` on the client list row — picking "the first client" by role is brittle when the list shares a layout with cards/headers.

Both are one-line frontend edits.

## CI Workflow (`.github/workflows/e2e.yml`)

Triggers on every push to any branch. Single job, single runner. Steps:

1. Checkout.
2. Setup Node 20, npm cache.
3. `npm ci` in `frontend/`.
4. `npx playwright install --with-deps chromium firefox webkit`.
5. `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --wait` (with `ANTHROPIC_API_KEY=test-key-not-used`, `JWT_SECRET=test-secret`).
6. `npm run test:e2e` (with `CI=true`).
7. Always: tear down docker stack.
8. On failure: upload `playwright-report/` and `test-results/` as artifacts (14-day retention).

`timeout-minutes: 15`. Estimated runtime: 3-5min cold, 2-3min warm.

## Performance Budget

- 5 specs × 3 browsers = 15 test runs per push.
- Per-test reset: ~500ms.
- Per-test login: ~2s (live UI flow per Question 3).
- Total estimated wall time on a 4-core CI runner with Playwright's default parallelism: ~90s.

If runtime grows past 5 minutes, the next move is sharding by browser project across CI matrix jobs.

## Security Considerations

The `/__test/reset` endpoint can wipe the entire database. Three layers of protection:

1. Route is **only registered** when `HEALTHFLOW_TEST_MODE=1` is set.
2. Production `docker-compose.yml` does not set the env var.
3. Backend logs a startup warning whenever the var is on.

Production deployments must never set `HEALTHFLOW_TEST_MODE`. A future hardening step would be to also IP-allowlist the route to localhost, but the env var gate is sufficient for the threat model (no test mode = no route exists).

## Test Plan for the Test Infrastructure

The Playwright tests are themselves verified by:

- Backend: a new pytest test confirms `/__test/reset` is **not** registered when `HEALTHFLOW_TEST_MODE` is unset, and **is** registered when set.
- Backend: a pytest test confirms the reset endpoint actually wipes and re-seeds (calls it, verifies known seed data exists, inserts something, calls it again, verifies the inserted thing is gone).
- CI: green build on a no-op PR confirms the workflow itself runs.

## Files Touched

| File | Change |
| --- | --- |
| `frontend/package.json` | add `@playwright/test`, `test:e2e`, `test:e2e:ui` scripts |
| `frontend/playwright.config.js` | new |
| `frontend/vite.config.js` | add `server.proxy` for `/api` |
| `frontend/tests/e2e/auth.spec.js` | new |
| `frontend/tests/e2e/add-client.spec.js` | new |
| `frontend/tests/e2e/plan-comparison.spec.js` | new |
| `frontend/tests/fixtures/index.js` | new |
| `frontend/tests/fixtures/test-users.js` | new |
| `frontend/tests/global-setup.js` | new |
| `frontend/tests/global-teardown.js` | new |
| `frontend/src/pages/PlanComparisonPage.jsx` | add `data-testid="plan-row"` to result row |
| `frontend/src/pages/ClientListPage.jsx` | add `data-testid="client-row"` to client row |
| `healthflow/api/test_router.py` | new — env-gated reset endpoint |
| `healthflow/main.py` | conditionally include `test_router` |
| `healthflow/seed_data.py` | new — `TEST_BROKER`, `TEST_CLIENTS`, `seed_db(session)` |
| `docker-compose.yml` | add backend healthcheck |
| `docker-compose.test.yml` | new — test override |
| `.github/workflows/e2e.yml` | new |
| `.gitignore` | add `frontend/playwright-report/`, `frontend/test-results/` |
| `healthflow/tests/test_test_router.py` | new — verifies env gating + reset behavior |

## Open Questions

None.
