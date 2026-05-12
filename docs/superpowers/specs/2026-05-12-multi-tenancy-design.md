# Multi-Tenancy and Tenant Data Isolation

**Date:** 2026-05-12
**Status:** Approved (design)
**Part of:** HIPAA-readiness portfolio-credible foundation (sub-project #2 of 5)

## Problem

The schema already has `broker_id` foreign keys on every PHI table (`clients`, `action_history`, `feedback`), so HealthFlow has *de facto* per-broker tenancy at the data layer. What's missing is enforcement: every query must remember to filter by `broker_id`, and a single forgotten `WHERE` clause leaks one broker's clients to another.

We also have no automated, comprehensive proof that cross-tenant access is impossible — only one isolation test (`tests/test_cross_broker_isolation.py`, 115 lines) covering the read path on a subset of routes.

For the project to credibly claim "HIPAA-ready foundation," tenant isolation must be:
1. Enforced by infrastructure, not by developer discipline.
2. Provable by an automated test suite that exercises every PHI route.
3. Documented in a single, discoverable place.

## Goal

Tenant isolation in `healthflow.db` becomes a property of the database session itself, not of individual queries. Specifically:

- Any ORM query against a tenant-scoped table is auto-filtered by the current request's `broker_id`. Forgetting the filter is impossible.
- Querying a tenant-scoped table with no current broker raises `TenantContextMissing` (loud failure, not silent leak).
- Cross-tenant access — read or write — returns 404 (no existence leak).
- A `tests/tenancy/` suite proves the property holds across every PHI route, including the asyncio + contextvars correctness case.

## Non-Goals

- **No schema migration.** The `broker_id` columns and FKs already exist.
- **No agency/firm tenancy.** One broker = one tenant. A future sub-project may introduce an `Agency` parent if/when product direction calls for it.
- **No PHI redaction in LLM prompts** — that's sub-project #1, separate spec.
- **No PHI access audit log** — that's sub-project #3. The existing `ActionHistory` table records broker *actions*, not data *access*.
- **No auth hardening** (MFA, JWT secret default, password policy) — sub-project #4.
- **No encryption at rest or hosting migration** — sub-projects #5 and (deferred) #6.
- **No reorganization of the other 68 test files.** Tenancy tests live under `tests/tenancy/`; everything else stays where it is.

## Design

### Architecture

A request-scoped tenant context (`contextvars.ContextVar[uuid.UUID | None]`) holds the current broker's ID for the life of a request. The FastAPI auth dependency reads the JWT, resolves the broker, and sets the context var; on dependency teardown the var is reset to its prior value.

A SQLAlchemy `do_orm_execute` event listener registered on the async `Session` inspects every ORM execution. For each statement targeting a registered tenant-scoped model, the listener applies `Statement.where(Model.broker_id == current_broker_id.get())`. If the var is unset, it raises `TenantContextMissing` rather than executing.

Three escape hatches:

1. **Public endpoints** (`/login`, `/register`, `/healthz`, plan search against `healthflow_data.db`) never set the context var. The hook isn't registered against the public-data DB session, so plan/drug/zip queries are unaffected. Tenant-scoped queries from these contexts would raise — which is correct behavior.
2. **System context** — a `with system_context():` block clears the var temporarily for legitimate cross-tenant operations (seeders, migrations, the data-refresh script). Logs WARN on entry and exit. Allowed call sites are explicitly listed (see "Use of system_context" below) and audited.
3. **Future cross-broker reads** (none today) — must explicitly opt in via `system_context()`. A grep for the function is the audit trail.

On a tenant-scoped lookup that returns no rows because of the auto-filter, the route returns **404, not 403**, to avoid leaking whether a record exists in another tenant.

### Data model

| Table | Tenant-scoped? | Notes |
|---|---|---|
| `brokers` | No — IS the tenant | Auth target. Login query uses `email`, never `broker_id`. |
| `clients` | Yes | `broker_id` FK + index already present. |
| `action_history` | Yes | `broker_id` FK + index already present. Has `client_id` too — see composite-write rule below. |
| `feedback` | Yes | `broker_id` FK + index already present. |
| `prompt_variants` | No — global config | A/B test config, system-managed. Reads bypass; writes only via system context. |

Tables in `healthflow_data.db` (`plans`, `plan_zips`, `plan_counties`, `drugs`) are public reference data and use a separate engine/session. The hook is registered only on the `healthflow.db` session factory.

**No schema migration is required.** No `ALTER TABLE`, no data backfill, no down-migration to write.

**Composite-write rule.** `ActionHistory` has both `broker_id` and `client_id`. The hook auto-fills the `broker_id` filter on read, but on write the application must look up the referenced `client_id` first via the filtered `Client` query. A 404 from that lookup short-circuits the write. A unit test in group #2 proves: "Broker A cannot create an `ActionHistory` referencing Broker B's client."

### Code surface

**New: `healthflow/auth/tenant_context.py`**

```
current_broker_id: ContextVar[UUID | None]
require_current_broker() -> UUID                    # raises TenantContextMissing if unset
system_context() -> contextmanager[None]            # temporarily None; WARN log on entry/exit
class TenantContextMissing(Exception): ...
```

**New: `healthflow/database/tenant_filter.py`**

- `TENANT_SCOPED_MODELS = {Client, ActionHistory, Feedback}` — explicit registry. Adding a future PHI model is a deliberate one-line registry change that surfaces in code review.
- `do_orm_execute` listener registered on the `healthflow.db` async session. For each ORM execution that targets a registered model:
  - If `current_broker_id.get()` is a UUID: append `WHERE broker_id = :tenant`. DEBUG log: `tenant_filter: scoped {table} to broker={short_uuid}`.
  - If unset and not inside `system_context()`: raise `TenantContextMissing`. ERROR log includes the SQL and the call stack.

**Modified: `healthflow/auth/dependencies.py`** (the existing `get_current_broker` dependency)

- After resolving the broker from the JWT, calls `current_broker_id.set(broker.id)` and stores the returned token.
- Uses a `yield` dependency so on teardown it calls `current_broker_id.reset(token)`. Per-request isolation under concurrency comes from `contextvars`'s asyncio integration.

**Modified: `healthflow/api/client_router.py`** (and any sibling routers that touch PHI)

- Remove route params, body fields, or query params named `broker_id`. The session is the only source of truth.
- Routes that look up by record ID stop adding `WHERE broker_id =` themselves — the hook does it. A request for another broker's record returns `None` from the query → 404.
- The `ActionHistory` write path loads `client_id` first via the filtered `Client` query before constructing the row.

**Modified: `scripts/refresh_data.py`, `seed.py`, any future migration scripts**

- Wrap DB writes against `healthflow.db` in `with system_context():`. Most touch only `healthflow_data.db` and need no change.
- `seed.py` creates demo brokers under system context, then enters each broker's context to create that broker's clients. Demonstrates both patterns.

**Deletion target:** any `GET /brokers/{id}/clients` style endpoint where the client supplies its own `broker_id`. The endpoint becomes `GET /clients`.

### Use of `system_context`

Initial allowed call sites (each with a code comment justifying it):

- `seed.py` — creates demo brokers and (per-broker) demo clients
- `scripts/refresh_data.py` — writes to `healthflow_data.db` only; PHI session not entered, but documented anyway
- Any Alembic migration that backfills tenant-scoped data

A grep for `system_context` is the audit trail. New uses require code-review justification.

### Test plan

All tenancy tests live under `healthflow/tests/tenancy/`:

```
healthflow/tests/tenancy/
  __init__.py
  test_cross_broker_isolation.py     # moved from tests/ — group #1 (read isolation)
  test_cross_broker_writes.py        # new — group #2 (composite-write protection)
  test_tenant_filter.py              # new — group #3 (hook unit tests, raise behavior)
  test_tenant_context.py             # new — group #4 (asyncio contextvars correctness)
```

Groups #5 (public-endpoint regression) and #6 (system-context guardrails) fold into existing files (`tests/test_auth.py`, existing `seed.py`/`refresh_data.py` smoke tests) — they're a few cases each.

**Group #1 — read isolation (existing file, extended).**
- Parameterized over every PHI route: `GET /clients`, `GET /clients/{id}`, list/detail for `action_history` and `feedback`. Auth as Broker A, assert no Broker B record visible. Detail endpoints return 404 for B's IDs.

**Group #2 — write isolation (new file).**
- Auth as A; POST `ActionHistory` with `client_id` belonging to B → 404.
- Auth as A; PUT/DELETE on B's client ID → 404.

**Group #3 — hook unit tests (new file).**
- Tenant-scoped query with no context set → raises `TenantContextMissing`.
- Tenant-scoped query inside `system_context()` → no filter, returns all rows.
- Non-tenant-scoped query (`Broker`, `PromptVariant`) with no context → no filter, succeeds.
- DEBUG log emitted on filter application; ERROR + SQL emitted on raise.

**Group #4 — context lifecycle (new file).**
- `asyncio.gather` of two FastAPI test-client requests under different broker tokens; assert no leakage in either response. This is the bug `contextvars` exists to prevent — proving it with a test is the credibility marker.
- After a request returns, the context var is reset to its prior value.

**Groups #5 and #6 — fold into existing files.**
- Public endpoints (`/login`, `/register`, `/healthz`, plan search) succeed without a tenant context.
- `seed.py` and `scripts/refresh_data.py` complete end-to-end without raising `TenantContextMissing`.

### Rollout

No feature flag — the hook is correctness, not a feature.

1. Land `tenant_context.py` + `tenant_filter.py` + the `tests/tenancy/` suite. Listener is registered, but existing manual `WHERE broker_id =` filters in routers stay (belt-and-suspenders during transition).
2. Migrate routers one at a time: remove manual filters, remove `broker_id` request params. Run the tenancy suite after each migration.
3. Once every router is migrated, remove any leftover manual filters and any "I trust the caller" comments.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| Async / `contextvars` subtlety: a background task spawned from a request could lose the context. | Document in `tenant_context.py` docstring. Wrap any spawned background work in an explicit `current_broker_id.set()` or `system_context()`. Test group #4 covers concurrent requests. |
| Raw SQL via `session.execute(text(...))` bypasses the ORM-level `do_orm_execute` hook. | Add an `before_execute` listener on the engine that scans textual SQL for tenant-scoped table names and raises if no `broker_id =` clause is present. Heuristic, not bulletproof, but catches accidental raw SQL. |
| Tests that mock `Session` may bypass the listener. | Integration tests in groups #1 and #2 use the real session. Mocked tests by definition aren't testing the filter — document in the suite README. |
| `system_context()` becomes overused. | Audit script: grep for `system_context`; require a justification comment at each call site. Initial allowlist is the three sites named above. |
| Existing 436-test suite breaks because every test now needs a tenant context. | Most tests are already broker-scoped via fixtures. Audit pass during rollout step 1: find tests that hit PHI tables without a current broker, fix the fixture. Estimated 10–30 test files affected. |

### Observability

- DEBUG: per-filter-application log line including table and short broker UUID. Off by default; flip on when debugging.
- ERROR: `TenantContextMissing` raises log the SQL and the call stack — this is a bug, not user error.
- (Optional, if observability stack is ever added) counter `tenant_filter_applied_total{table=...}`.

## Out of Scope

- PHI redaction in LLM prompts and logs (sub-project #1)
- PHI access audit log (sub-project #3)
- Auth hardening — MFA, JWT secret default, session policy (sub-project #4)
- Encryption at rest and key management (sub-project #5)
- Postgres / RLS migration (deferred sub-project #6)
- BAAs, privacy policy, breach plan, risk analysis (sub-projects #7–#9, deferred)
- Reorganization of the other 68 test files (separate concern, not blocking this work)

## Acceptance

This sub-project is done when:

1. `healthflow/auth/tenant_context.py` and `healthflow/database/tenant_filter.py` exist and are wired into the auth dependency and the `healthflow.db` session factory.
2. Every PHI router has been migrated; no router accepts `broker_id` as a request param.
3. `healthflow/tests/tenancy/` contains the four files above and all tests pass.
4. Existing 436-test suite (with any updated fixtures) passes.
5. `seed.py` and `scripts/refresh_data.py` run end-to-end.
6. The `healthflow-security` skill is updated to reference the new enforcement model and the `system_context()` audit pattern.
