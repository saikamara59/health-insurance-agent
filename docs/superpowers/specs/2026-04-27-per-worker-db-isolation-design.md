# Per-Worker DB Isolation for Playwright E2E Tests

**Date:** 2026-04-27
**Status:** Approved (design)
**Follow-up to:** PR #2 (Playwright e2e foundation, merged 2026-04-23)

## Problem

The Playwright e2e suite is pinned to `workers: 1` because parallel workers race on the shared SQLite test database. The `/__test/reset` endpoint wipes and re-seeds the entire DB before every test, so even with serialized resets, worker A's reset destroys rows worker B just created mid-test. The race is structural, not a locking bug.

This serializes the entire e2e suite, capping CI throughput and making it cost-prohibitive to grow test coverage.

## Goal

Enable parallel Playwright workers (target: 4 in CI) by isolating each worker's data, while keeping the architecture simple, scaling cleanly to N workers, and surviving a future Postgres migration without rework.

## Non-Goals

- High-parallelism load testing (8+ workers). The shared SQLite writer lock will eventually be the ceiling; we'll address it empirically if hit.
- Per-worker backend containers or per-worker DB files (Approach B/C from brainstorming). Both add infrastructure complexity that the application-level approach below avoids.
- Migrating tests to Postgres. The chosen design is storage-agnostic, so a Postgres migration would not require revisiting test isolation.

## Approach: Per-Worker Tenant Scope

Each Playwright worker is a `Broker`. Workers are isolated by the `broker_id` boundary that already exists in the data model (`Client → Broker`, `Feedback → Client → Broker`, etc.). The reset endpoint becomes scoped: it only wipes data owned by the requesting worker's broker.

Why this approach: the schema is already multi-tenant by broker. Using that boundary for tests is testing a property the production app already has (cross-broker isolation), instead of inventing a parallel test-only mechanism. It scales linearly with workers, requires no new infrastructure, and is invariant under storage migration.

## Worker Identity

Each Playwright worker derives a stable identity from `testInfo.parallelIndex`:

```
worker_id: "e2e-worker-{N}"
email:     "e2e-worker-{N}@healthflow.test"
password:  "test-password"
broker:    lazily provisioned on first reset for this worker_id
```

`parallelIndex` is the worker slot, not a per-test counter — workers are reused across many tests, so the same worker keeps the same `broker_id` for its entire lifetime. Sticky broker, just resets the data.

## Backend Changes

### `healthflow/api/test_router.py` — rewrite `/__test/reset`

New contract:

```
POST /__test/reset
body: { "worker_id": "e2e-worker-3" }
```

- Validate `worker_id` matches `^e2e-worker-\d+$`. Reject with 400 otherwise. There is no way to call this endpoint without a scope — accidental global wipes are impossible.
- In a single transaction (still under the existing `_reset_lock` for SQLite write safety):
  1. Look up the broker by deterministic email `{worker_id}@healthflow.test`. If missing, create it (lazy provisioning).
  2. Delete `Feedback`, `ActionHistory`, `PromptVariant`, `Client` rows owned (transitively) by that broker. **Do not** touch the `Broker` row — keep it stable so JWTs issued to it stay valid across resets.
  3. Re-seed the canonical client set, owned by this broker.

The `_reset_lock` stays. SQLite writes are still single-writer at the engine level, so serializing the write transaction is correct. What we're removing is the cross-worker data wipe, not the write serialization.

The endpoint remains gated on `HEALTHFLOW_TEST_MODE=1`.

### `healthflow/seed_data.py` — add `seed_for_worker`

```python
async def seed_for_worker(session, worker_id: str) -> Broker:
    """Idempotently provision a worker's broker and canonical client set."""
```

- Get-or-create the broker with the deterministic email/password
- Insert the canonical client set with `broker_id` pinned to this worker's broker
- Return the broker so the router can use its id for the deletes

Same canonical client set across workers — only the owning broker differs. Tests can write assertions like "client named 'Alice' exists" and they pass on every worker.

### `scripts/seed_test_db.py` — simplify

The script now only creates the schema (drop + create). All data lands lazily via `/__test/reset`. The `seed` service in `docker-compose.test.yml` becomes a one-shot schema-init step.

This means the seed script doesn't need to know how many workers Playwright will spawn. Adding a 5th worker tomorrow requires zero backend changes.

### API audit (one-time, in scope)

Walk every route in `healthflow/api/`. For each, confirm it scopes by `current_user.broker_id` (from JWT) and never returns rows across brokers. Anything that looks "global" gets either a scope filter added or an explicit comment explaining why it's safe (e.g., a `/health` endpoint).

This is not scope-creep — broker isolation must actually hold for the test design to work, and any leak found is a real bug worth fixing. Expectation: the app reads as broker-tenant throughout, but this is a known unknown until the audit completes.

## Test Infrastructure Changes

### `frontend/tests/fixtures/test-users.js`

Replace the single `broker` constant with a worker-aware factory:

```js
export function workerBroker(workerIndex) {
  const id = `e2e-worker-${workerIndex}`
  return {
    workerId: id,
    email:    `${id}@healthflow.test`,
    password: 'test-password',
  }
}
```

### `frontend/tests/fixtures/index.js`

Fixtures derive the worker from Playwright's built-in `testInfo.parallelIndex`:

```js
export const test = base.extend({
  workerBroker: async ({}, use, testInfo) => {
    await use(workerBroker(testInfo.parallelIndex))
  },

  page: async ({ page, baseURL, workerBroker }, use) => {
    await resetForWorker(baseURL, workerBroker.workerId)
    await use(page)
  },

  authedPage: async ({ context, baseURL, request, workerBroker }, use) => {
    await resetForWorker(baseURL, workerBroker.workerId, request)
    const { access_token, refresh_token } = await login(request, baseURL, workerBroker)
    await context.addInitScript(/* unchanged */)
    await use(await context.newPage())
  },
})
```

`resetForWorker` POSTs `{ worker_id }` to `/__test/reset`. The login fixture uses the worker's broker credentials.

**Tests don't change.** They import `test` from fixtures the same way and get an isolated broker for free. The three existing specs (`auth.spec.js`, `add-client.spec.js`, `plan-comparison.spec.js`) keep working unmodified.

### `frontend/playwright.config.js`

```js
fullyParallel: true,
workers: process.env.CI ? 4 : undefined,  // local: Playwright auto; CI: pinned 4
```

Pinning CI to 4 keeps runs deterministic and bounds resource use against the single backend container. Local devs get whatever their machine can handle (Playwright defaults to ~50% of cores).

The "Shared backend + single SQLite file" comment block at the top of the config gets deleted — it is now wrong.

## Validation Plan

### 1. Backend pytest

Existing 429 tests must stay green. The reset endpoint is the only modified production-adjacent surface; everything else is additive.

New unit tests for `test_router.py`:

- `POST /__test/reset` with valid `worker_id` → 200, broker created, only that broker's clients exist
- Same call twice → idempotent (no duplicate clients)
- Reset for worker 0 → reset for worker 1 → worker 0's data still intact (the actual isolation property)
- `POST /__test/reset` with no body → 400
- `POST /__test/reset` with malformed `worker_id` → 400

### 2. API audit verification

For each route surveyed in the audit, add (or confirm existing) a pytest case proving cross-broker isolation: broker A creates a client → broker B's auth context cannot see/modify/delete it. Any route the audit finds unscoped gets fixed in this same change, with a test.

### 3. E2E parallel run (the actual goal)

Locally and in CI, run the full e2e suite with `workers: 4`.

Acceptance criteria:
- All 3 existing specs pass
- Total wall-clock time drops meaningfully vs `workers: 1` (rough expectation: 2–3× faster, not 4× — there's serial setup/teardown overhead)
- No flaky failures across 5 consecutive runs

### 4. Cross-pollution smoke test

New spec `tests/e2e/isolation.spec.js` — two tests deliberately designed to interfere if isolation is broken:

- Test A: add a client named "Isolation-Probe-A", assert it appears in the list
- Test B: add a client named "Isolation-Probe-B", assert that "Isolation-Probe-A" does NOT appear in *its* list

If they ever run on the same worker, the per-test reset gives Test B a clean slate. If they run on different workers, broker-scoping guarantees B doesn't see A. Either way, both pass — *unless* isolation is genuinely broken, in which case B fails. This spec is the canary.

### 5. CI workflow

`.github/workflows/e2e.yml` — no structural change. Just confirms the `workers: 4` config runs cleanly. The workflow already uploads HTML reports and failure artifacts, so any flake leaves evidence.

## Risks & Open Questions

- **API audit may surface unscoped endpoints.** If found and intentional (e.g., a future admin UI), needs an explicit exception path. Not expected, but a known unknown.
- **SQLite writer lock contention** could become a ceiling at higher parallelism. Out of scope for this change; addressed empirically if hit.
- **Per-worker broker proliferation** in long-lived test DBs is a non-issue: brokers are created once per worker, never deleted, and the test DB is wiped on every CI run.
