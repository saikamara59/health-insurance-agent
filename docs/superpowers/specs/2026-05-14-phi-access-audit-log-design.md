# PHI Access Audit Log

**Date:** 2026-05-14
**Status:** Approved (design)
**Part of:** HIPAA-readiness portfolio-credible foundation (sub-project #3 of 5)

## Problem

HealthFlow has no durable, queryable record of who accessed which patient's data, when, or how. HIPAA's Security Rule (§164.312(b), "audit controls") requires the ability to record and examine activity in systems that contain PHI — and a breach investigation needs to answer "show me everyone who touched patient X's records" with a real answer, not a shrug.

Three logging systems exist today, none of which is a PHI-access audit trail:

- **`AuditLogger`** (`healthflow/logs/audit.py`) — emits JSON *events* (`tool_called`, `phi_redacted`, etc.) to a `RotatingFileHandler` on `healthflow.log` (5 MB × 3 backups). It records agent activity, not row-level data access, and it is not durable — after three rotations the history is gone.
- **`ServerLogger`** (`healthflow/logs/server.py`) — HTTP request logging (method, path, status, duration, `user_id`). Request-level, not "which patient's record."
- **The `do_orm_execute` tenant-filter hook** (`healthflow/database/tenant_filter.py`) — already intercepts every SELECT/UPDATE/DELETE against the PHI tables and already knows the current broker. It enforces isolation but records nothing.

## Goal

A durable, queryable PHI access audit trail:

- One append-only row per PHI query in a dedicated `phi_access_log` table in `healthflow.db`.
- Each row captures **who** (broker), **what** (table + operation), **which patients** (the result/affected row IDs), **how/why** (the request endpoint), and **when**.
- Coverage of all four operations — `read`, `create`, `update`, `delete` — across all three PHI tables (`clients`, `action_history`, `feedback`).
- Enforced by infrastructure (SQLAlchemy event listeners), not by developers remembering to call an audit function — the same structural-enforcement principle as the tenant filter and the typed `PromptInput` redaction boundary.
- Queryable today via a CLI script (`scripts/audit_query.py`) by patient and by broker.

## Purpose and granularity (settled during brainstorming)

- **Primary job:** breach investigation + compliance evidence — a durable record answering "who accessed patient X's data, when, and how," plus existence of audit controls as a §164.312(b) checkbox. Not real-time anomaly detection (a much larger system, deferred).
- **Granularity:** per-query, with the result row IDs captured. One `GET /clients` returning 18 clients produces one entry whose `row_ids` lists all 18 client UUIDs. This answers "who accessed patient X" (find entries where X's UUID appears in `row_ids`) without the row-count explosion of per-row logging.

## Non-Goals

- **No failed-attempt logging.** Entries are written in the same transaction as the operation (see "Write timing"), so an operation that errors and rolls back leaves no entry. Capturing *attempts* is genuinely valuable but belongs with anomaly detection — explicit follow-up, not covered here.
- **No real-time anomaly detection or alerting.** Deferred.
- **No admin API endpoint.** The read surface is a CLI script. An admin endpoint depends on admin RBAC, which does not yet exist (it is a deferred follow-up from the multi-tenancy work). Explicit follow-up.
- **No automated retention/archival.** HIPAA expects ~6-year retention; `phi_access_log` grows unbounded. The spec defines the retention *expectation* but archival automation is out of scope.
- **No performance optimization.** Audit writes roughly double each PHI query's DB work. Accepted at portfolio scale; noted, not optimized.
- **No change to the existing `AuditLogger` or `ServerLogger`.** They keep their current jobs.

## Design

### Architecture

A new table, `phi_access_log`, stores one append-only row per PHI query. Two SQLAlchemy event listeners populate it, registered on the `healthflow.db` session factory at startup alongside `install_tenant_filter`:

- **`do_orm_execute`** — fires for SELECT / UPDATE / DELETE. Classifies the query against the PHI models, inspects the *result* to capture row IDs, and writes a `read` / `update` / `delete` entry.
- **`after_flush`** — fires when pending changes flush to the DB. INSERTs do *not* go through `do_orm_execute` (the same blind spot the tenant filter and composite-write protection already navigate), so this second listener pulls freshly-inserted PHI objects out of `session.new` and writes `create` entries.

Two request-scoped `ContextVar`s carry identity down to the database-layer listeners:

- **`current_broker_id`** — already exists (from the multi-tenancy work). The "who."
- **`current_endpoint`** — new, added to `healthflow/auth/tenant_context.py` next to `current_broker_id`. Set by a small FastAPI middleware at the start of each request, reset on teardown. The "how/why."

Background and system operations have no HTTP request; they already run inside `system_context(reason="...")`. Those entries record `broker_id = null` and `endpoint = "system:<reason>"`.

### The `phi_access_log` table

Added to `healthflow/database/models.py` alongside the other table definitions.

| Column | Type | Notes |
|---|---|---|
| `id` | `GUID` PK, default `uuid4` | The audit entry's own ID |
| `broker_id` | `GUID`, nullable, indexed | Who acted. Null for system operations. Not a FK-ownership column — see "Not tenant-scoped" below. |
| `table_name` | `String` | `clients` / `action_history` / `feedback` |
| `operation` | `String` | `read` / `create` / `update` / `delete` |
| `row_ids` | `JSON` | List of the touched row UUIDs (as strings) — result IDs for reads, affected IDs for writes |
| `row_count` | `Integer` | `len(row_ids)`, denormalized so volume queries don't parse JSON |
| `endpoint` | `String` | The `current_endpoint` value — request method + path, e.g. `GET /clients/{id}` — or `system:<reason>` for background work. The plan decides route-template vs. raw path; either is acceptable since patient UUIDs already live in `row_ids`. |
| `created_at` | `DateTime(timezone=True)`, default `_utcnow`, indexed | When |

Indexes on `broker_id` ("everything broker X did") and `created_at` ("everything in this window"). "Who accessed patient X" queries `row_ids` via SQLite's `json_each`; acceptable at portfolio scale. The spec notes that a dedicated `phi_access_log_rows` join table is the move at real scale — explicitly YAGNI now.

### Not tenant-scoped, and self-excluded

`phi_access_log` is **not** added to `TENANT_SCOPED_MODELS`. It is a system table:

- It deliberately records *everyone's* activity in one place — an audit log scoped to "only your own activity" cannot catch a bad actor.
- Its `broker_id` column means "who acted," not "who owns this row" — there is no tenant-ownership semantics for the tenant filter to enforce.

It is also **explicitly excluded from the audit listeners themselves.** Writing an audit entry is a database write; if `phi_access_log` were in the audit hook's scope, logging an access would log itself, recursively forever. The listeners check the target table and skip `phi_access_log`.

### Write timing

Audit entries are written **in the same transaction as the operation they record** (Option A from brainstorming). They commit together or roll back together. Every request in this app runs through `get_db`, which commits on success, so a read request already has a committing transaction the audit row rides along in.

Consequence: an operation that errors and rolls back leaves no audit entry — failed *attempts* are not captured. This is an accepted non-goal (see Non-Goals).

If building an audit entry itself raises (a bug in a listener), it must **fail loud**, not silently swallow — the same philosophy as `TenantContextMissing`. A broken audit listener means flying blind on compliance; better to surface it immediately than discover it during a breach investigation.

### Components

| File | Change |
|---|---|
| `healthflow/database/models.py` | NEW `PhiAccessLog` ORM model (the table above) |
| `healthflow/database/phi_audit.py` | NEW — `_on_do_orm_execute_audit` (read/update/delete listener with result inspection), `_on_after_flush_audit` (insert listener), `install_phi_audit(factory)` (idempotent registration) |
| `healthflow/auth/tenant_context.py` | NEW `current_endpoint` ContextVar |
| `healthflow/api/middleware.py` (or a new middleware) | NEW middleware that sets/resets `current_endpoint` per request |
| `healthflow/database/config.py` | Call `install_phi_audit(async_session_factory)` at startup, alongside `install_tenant_filter` / `install_raw_sql_guard` |
| `healthflow/tests/conftest.py` | Install the audit listeners on the test session factory (same pattern as `install_tenant_filter`) |
| `scripts/audit_query.py` | NEW — CLI to read the log back |
| `.claude/skills/healthflow-security/SKILL.md` | NEW section documenting the audit-log enforcement model |

### Reading the log back

The read surface for this sub-project is a CLI script, `scripts/audit_query.py`, with two modes:

- `--patient <uuid>` — every entry where the patient's UUID appears in `row_ids` ("everyone who touched this patient's records")
- `--broker <uuid>` — every entry for that broker ("everything this broker did")

It runs inside `system_context(reason="audit query CLI")` — a legitimate cross-tenant read — and prints results as a table. Usable today with no RBAC dependency. An admin API endpoint is an explicit follow-up that lands once admin RBAC exists.

### Test plan

1. **Model/table test** — `phi_access_log` is created with the expected columns and indexes.
2. **Read-path listener** — a `SELECT` against `clients` under a known broker + endpoint context produces exactly one entry with the right `broker_id`, `operation="read"`, `row_ids` matching the result, `endpoint` set.
3. **Insert-path listener** — `session.add(Client(...))` + flush produces a `create` entry (exercises the `after_flush` hook — what `do_orm_execute` misses).
4. **Update + delete** — same shape, `operation="update"` / `"delete"`.
5. **Self-exclusion** — writing a `phi_access_log` row directly does NOT generate another `phi_access_log` row (no recursion). The critical test.
6. **System-context** — a query inside `system_context(reason="...")` produces an entry with `broker_id=null` and `endpoint="system:<reason>"`.
7. **Multi-row capture** — a list query returning 3 clients produces one entry whose `row_ids` has all 3 (proves per-query-with-IDs granularity).
8. **CLI query** — seed known entries, run `audit_query.py --patient X` and `--broker Y`, assert the right rows return.
9. **Coexistence with the tenant filter** — both listeners hook `do_orm_execute`; assert both fire and the tenant filter still scopes correctly (the audit listener only reads state; the tenant filter modifies the statement).

### Rollout

Per-task, each commit green:

1. `PhiAccessLog` model in `models.py` + table-creation + model test.
2. `current_endpoint` ContextVar + the middleware that sets it.
3. `phi_audit.py` — the read/update/delete listener (`do_orm_execute`) with result inspection.
4. The insert listener (`after_flush`).
5. Wire `install_phi_audit` into `config.py` startup + the test conftest.
6. `scripts/audit_query.py` + its test.
7. Update the `healthflow-security` skill.
8. Final verification + PR.

### Risks

| Risk | Mitigation |
|---|---|
| Result inspection in `do_orm_execute` is the intricate part — capturing row IDs without breaking the query | Isolated in one listener function, covered by tests #2 and #7. If the SQLAlchemy mechanism proves too fragile, fall back to statement-level IDs for single-row lookups plus a row-count-only entry for list queries, and document the gap. |
| Audit writes double each PHI query's DB work | Accepted at portfolio scale. Same-transaction write keeps it correct; performance optimization is an explicit non-goal. |
| The audit listener and the tenant filter both hook `do_orm_execute` — and the audit listener *observes results*, not just context | **Ordering matters.** The tenant filter *modifies* the statement (adds the `WHERE broker_id` clause); the audit listener must run *after* that so it observes the already-scoped statement and its results. SQLAlchemy fires listeners in registration order, so `install_tenant_filter` must be called before `install_phi_audit` in `config.py` and the test conftest. Test #9 asserts both fire, the tenant filter still scopes correctly, and the audit `row_ids` reflect the scoped (not unscoped) result set. |
| `after_flush` fires for every flush, including non-PHI inserts | The listener filters `session.new` to the three PHI models before doing any work — non-PHI inserts are a cheap early return. |
| A listener bug silently loses audit coverage | Listeners fail loud (raise), not swallow — same philosophy as `TenantContextMissing`. Test #5 and #6 exercise the listener paths. |

## Acceptance

This sub-project is done when:

1. `phi_access_log` exists in `healthflow.db` with the columns and indexes above.
2. `phi_audit.py` exists with both listeners; `install_phi_audit` is wired into `config.py` and the test conftest.
3. `current_endpoint` ContextVar exists and is set per-request by middleware.
4. All four operations (`read` / `create` / `update` / `delete`) across all three PHI tables produce audit entries; the listeners skip `phi_access_log` itself.
5. `scripts/audit_query.py` answers `--patient` and `--broker` queries.
6. The full test plan passes; the full suite is green.
7. The `healthflow-security` skill documents the audit-log enforcement model.

## Out of Scope

- Failed-attempt logging (pairs with anomaly detection).
- Real-time anomaly detection and alerting.
- Admin API endpoint for the audit log (depends on admin RBAC — a deferred follow-up).
- Automated retention/archival (HIPAA's ~6-year expectation is noted; automation deferred).
- A `phi_access_log_rows` join table for scale (YAGNI until real volume).
- Auth hardening (sub-project #4), encryption at rest (sub-project #5).
