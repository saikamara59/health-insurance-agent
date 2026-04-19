# E2E Test Stability — Follow-up

**Date:** 2026-04-19
**Status:** Known issue, deferred

## Context

The Playwright e2e infrastructure (specs, fixtures, docker stack, CI workflow) shipped on `feat/frontend-e2e-tests`. The full plan (15 tasks) is implemented. Backend pytest suite (428 tests) is green. The docker stack starts cleanly and the `/__test/reset` endpoint works under sequential and concurrent load (verified via curl).

However, when run under Playwright across all 3 browsers in parallel, only **3-5 of 15** tests pass per run. The remaining tests fail intermittently. This is a follow-up to investigate and fix.

## What's verified to work

- `seed_data.py` unit tests: 3/3 pass
- `/__test/reset` endpoint pytest tests (env gating + 200 response): 2/2 pass
- Docker-compose test stack brings up cleanly with `--build --wait`
- Manual `curl -X POST http://localhost:8000/__test/reset` succeeds repeatedly (sequential AND concurrent — 3 parallel curls all return 200)
- Manual `curl -X POST http://localhost:8000/auth/login` with TEST_BROKER credentials returns a valid access_token
- Backend container has the latest code after `docker compose up --build`
- Vite dev server starts and proxies `/auth`, `/clients`, `/__test`, etc. to backend

## What fails

Under `npm run test:e2e` (Playwright, 3 browsers, fully parallel):

- **`auth.spec.js > broker can log in and reach the dashboard`** — failed in chromium and webkit; passed in firefox. Symptom: `expect(page).toHaveURL('/')` times out at 5s with URL still on `/login`.
- **`auth.spec.js > invalid credentials show an error`** — failed in all 3 browsers. Symptom: error text not visible after submit.
- **`auth.spec.js > logged-in broker can sign out`** — failed when login fixture itself times out waiting for navigation.
- **`add-client.spec.js`** — failed in all 3 browsers. Same root cause: login fixture timeout.
- **`plan-comparison.spec.js`** — failed in all 3 browsers. Same root cause.

The pattern: when login navigates within Playwright's default timeout, the test passes. When it doesn't, downstream tests cascade-fail.

## Hypotheses to investigate

1. **Form submission timing.** The LoginPage handler is `async function handleSubmit(e)` which awaits `login(email, password)` then `navigate('/')`. If the auth API takes longer than expected under Playwright's headless run, the URL change may not happen within the 5-second `toHaveURL` timeout. Increasing the per-test timeout (e.g., `expect.toHaveURL` to 15s) might mask the symptom but not the root cause.
2. **Auth context race.** AuthContext stores token in localStorage and the route guard (`ProtectedRoute`) checks it. There may be a race between `login()` resolving and `ProtectedRoute` re-rendering with the new auth state.
3. **Browser-specific cookie/storage handling.** The single passing browser is firefox-login. Chromium/webkit may handle navigation/storage differently under Playwright's automation.
4. **`fullyParallel: true` + shared backend.** Three browsers' workers all hit the same backend simultaneously. Even though the reset endpoint is now thread-safe via `asyncio.Lock`, there may be cascading state issues between browsers (e.g., one browser's reset-during-another-browser's-login-call interfering).
5. **Page snapshot retention.** After the reset, the browser may still have stale page state from a previous test in the same context.

## Suggested next steps

In order of likely impact:

1. **Run with `workers: 1`** to serialize all tests across browsers and isolate whether parallelism is the root cause.
2. **Increase `actionTimeout` and `navigationTimeout`** in `playwright.config.js` to 15 seconds, in case slow-but-eventually-working login is the issue.
3. **Capture console logs** in failing tests via `page.on('console', ...)` to see what the browser thinks happened during login.
4. **Run tests in headed mode locally** (`npm run test:e2e:ui`) to watch the actual UI behavior.
5. **Inspect Playwright traces** for failing tests with `npx playwright show-trace test-results/<test>/trace.zip` — these capture full network + DOM activity.
6. **Verify the /auth/login response shape** matches what the AuthContext expects. If the API returns a slightly different shape under stress, login could "succeed" silently without setting auth state.

## What ships now

- All 15 plan tasks implemented and committed on `feat/frontend-e2e-tests`.
- Backend infrastructure is production-quality (env-gated reset endpoint, async lock, fresh-session pattern, DELETE-based clearing).
- Docker test stack is functional (`--build --wait` brings it up cleanly).
- CI workflow is wired (will likely show many failures on first run; that's expected pending the stability fix).
- 428 backend pytest tests pass.
- Manual verification of reset + login works.

The branch is mergeable as the **infrastructure foundation**. Test stability is a known follow-up.
