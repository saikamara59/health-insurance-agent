---
name: healthflow-security
description: Use when touching healthflow/auth/, healthflow/agents/ (LLM calls), client/PHI fields in healthflow/database/models.py, env/config, the seed script, or anything that logs request bodies. Project-specific PHI and secret-handling rules for HealthFlow.
---

# HealthFlow Security Notes

Project-specific traps. Generic OWASP advice (parameterize SQL, sanitize HTML, etc.) is not repeated here — assume those.

## PHI on the wire to Anthropic

Five agents in `healthflow/agents/` send data to Claude: `comparison_agent`, `cost_calculator_agent`, `network_agent`, `translation_agent`, `appeal_agent`. Client records contain medications, conditions, doctors, NPIs — all PHI. The convention is now enforced by the type system and AST tests.

**Rule:** Never call an agent's `_build_prompt` directly with raw arguments.
Construct the agent's `PromptInput` dataclass (in `healthflow/agents/prompt_inputs.py`)
and pass that. `_build_prompt` is type-annotated to accept only the
`PromptInput` — there is no path from a raw string to a prompt body that
skips the redaction boundary. A static `ast` test
(`tests/agents/test_no_raw_prompt_path.py`) enforces this.

**Rule:** Free-text fields on a `PromptInput` (denial text, document content,
questions) are redacted by the dataclass constructor via `PHIRedactor`.
Structured fields — medication names, procedure names, doctor names + NPIs —
pass through by design. Under the no-BAA threat model, medication/procedure
names are de-identified content (not among HIPAA's 18 identifiers) and doctor
NPIs are public NPPES registry data, not patient PHI.

**Rule:** When adding a new agent, add a `PromptInput` dataclass for it in
`prompt_inputs.py`. If it has free-text fields, redact them in `__post_init__`
using the `_redact_field` helper (frozen dataclass — reassigning a field needs
`object.__setattr__`; appending to `_redaction_log` does not). Emit the
`phi_redacted` audit event with `prompt_input.redaction_summary`.

**Rule:** Don't log raw prompt payloads. The `phi_redacted` audit event logs
only counts and placeholder types (`prompt_input.redaction_summary`), never
the redacted-or-raw text itself.

## Tenant isolation is enforced by infrastructure, not code review

Every PHI-table query is auto-filtered by `broker_id` via a SQLAlchemy
`do_orm_execute` listener registered at app startup
(`healthflow/database/tenant_filter.py`). The current broker is read from
a `ContextVar` set by the auth dependency in
`healthflow/auth/dependencies.py:get_current_broker`. Forgetting a
`WHERE broker_id = ...` clause in a route is now structurally impossible
for SELECT/UPDATE/DELETE.

**Rule:** When adding a new PHI table, add it to `TENANT_SCOPED_MODELS`
in `healthflow/database/tenant_filter.py`. Adding it anywhere else
(e.g., creating an ORM class with a `broker_id` column but forgetting
the registry) means the table will silently bypass enforcement.

**Rule:** INSERTs into tenant-scoped tables don't go through the hook
(unit-of-work flush bypasses `do_orm_execute`). Composite writes —
inserting a row that references another tenant-scoped row by ID
(e.g., `ActionHistory.client_id`) — must load the referenced row through
the filter first. If the load returns `None`, return 404. See
`healthflow/api/history_router.py:create_history` for the canonical
pattern.

**Rule:** Cross-broker reads are legitimate only at audited call sites
and must use `with system_context(reason="..."):`. The required `reason`
argument shows up in the WARN-level audit log. Allowed sites today:
`feedback/prompt_updater.py` and `feedback/reward_model.py` (RLHF needs
all brokers' feedback), `api/test_router.py` (e2e reset endpoint),
test fixtures in `tests/conftest.py` and `tests/database/test_database_models.py`.
Adding a new call site requires a justification comment and code review.

**Rule:** Cross-broker analytics endpoints exposed to non-admin users
are forbidden. Today: `feedback/analytics` is per-broker (no
`system_context`, the auto-filter scopes the underlying SELECT).
`/reward-score` and `/weekly-report` currently return *system-wide*
aggregates because their underlying `reward_model.score_outputs`
runs entirely in `system_context()` — RLHF needs cross-broker data
and there is no admin-role gate yet. Adding admin RBAC and gating
those two endpoints on it is a tracked follow-up. If you add a new
endpoint that returns aggregates, default to per-broker; if
cross-broker is needed, gate on the future admin role rather than
exposing it to any authenticated broker.

## Every PHI access is audited automatically

Every query against a PHI table (`clients`, `action_history`, `feedback`)
writes an append-only row to `phi_access_log` — who (broker), what (table +
operation), which patients (result row IDs), how/why (request endpoint), and
when. Enforced by two SQLAlchemy listeners in `healthflow/database/phi_audit.py`
(`do_orm_execute` for read/update/delete, `after_flush` for inserts), installed
at startup *after* the tenant filter. You never call an audit function — it
fires on its own.

**Rule:** `phi_access_log` is a system table — NOT in `TENANT_SCOPED_MODELS`,
NOT audited by its own listeners (writing an entry is a DB write; auditing the
audit table would recurse forever). When adding a new PHI table, add it to
`_AUDITED_MODELS` in `phi_audit.py` AND `TENANT_SCOPED_MODELS` in
`tenant_filter.py` — they are deliberately separate lists but a new PHI table
belongs in both.

**Rule:** Background/system code that touches PHI must run inside
`system_context(reason="...")` — the reason becomes the audit entry's
`endpoint` as `system:<reason>`, so the audit trail explains itself. Code that
runs with no broker and no `system_context` records `endpoint="unknown"` —
that is a smell worth investigating.

**Rule:** Listener ordering is load-bearing. `install_phi_audit` MUST be
called after `install_tenant_filter` (in `config.py` and the test conftest) —
the audit listener invokes the statement and must observe it already
tenant-scoped, so `row_ids` reflects what the broker could actually see.

**Rule:** Read the audit log via `scripts/audit_query.py` (`--patient` /
`--broker`). It runs inside `system_context()` because reading the whole audit
trail is a legitimate cross-tenant operation. An admin API endpoint is a
follow-up that depends on admin RBAC.

## Auth hardening rules (enforced)

**Rule:** `JWT_SECRET` is read fail-loud in `healthflow/auth/security.py`.
A missing env var OR the legacy value `"healthflow-dev-secret-change-in-production"`
raises `RuntimeError` at module import. There is no default. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"` and set it in
your `.env` or deploy environment.

**Rule:** New broker registration goes through `validate_password` (in
`healthflow/auth/security.py`): ≥12 chars, letter + digit + non-alphanumeric,
not in the bundled common-passwords block-list (`common_passwords.txt`).
Existing accounts with weaker passwords keep working — only registration
(and the future change-password endpoint) enforces the policy.

**Rule:** `/auth/login` enforces an account lockout — 5 failed attempts in
a row → 15-minute timed lock on the `brokers` row (`failed_login_count`
and `locked_until` columns). Lock auto-expires; successful login resets
both columns. The response body for a locked account is identical to the
wrong-password response — never leak lock state to the client (brute-force
aid).

**Rule:** Refresh tokens rotate on every `/auth/refresh` and persist their
revocation state in the `refresh_tokens` table. Replaying a revoked
refresh token is treated as theft — ALL of that broker's active refresh
tokens get revoked and a WARN-level `refresh_token_replay_revoke_all`
audit event is emitted via `AuditLogger`. `/auth/logout` revokes the
presented refresh token (access tokens expire naturally within 60 minutes).
`refresh_tokens` is a system table — NOT in `TENANT_SCOPED_MODELS` and
NOT in `_AUDITED_MODELS` (per-token CRUD would just create audit noise;
the one notable event goes through `AuditLogger`).

## Two databases — don't cross them

- `healthflow.db` → brokers, clients, prescriptions (PHI/PII)
- `healthflow_data.db` → CMS plans, ZIPs (public reference data)

**Rule:** Don't add foreign keys, joins, or backups that mix them. Keeping them separate is the only data-classification boundary this project has.

## Secrets and rotating keys

`.env.example` lists: `ANTHROPIC_API_KEY`, `JWT_SECRET`, `HUD_API_TOKEN`, and (in flight) `MARKETPLACE_API_KEY`.

**Rule:** Healthcare.gov Marketplace keys rotate every ~60 days. When implementing the ACA fetcher, treat HTTP 401 from `marketplace.api.healthcare.gov` as "key expired" with a clear actionable error (not a generic auth failure). Don't retry on 401.

**Rule:** Never commit `.env`, `~/.cache/healthflow/*`, or either `.db` file. The cache holds 39k HUD ZIPs but is rebuildable; the DBs hold PHI.

## Demo credentials in seed.py

`seed.py` creates `demo@healthflow.com / healthflow123`. This is intentional for local demos.

**Rule:** Never reuse this credential pattern for staging/prod. If you add a new "demo" account, it must be gated behind an explicit `SEED_DEMO=1` env var, not run on every startup.

## Logs

`healthflow.log` at repo root and `logs/` are not in `.gitignore`-equivalent containers — verify before any logging change. PHI in logs is the easiest accidental leak in this codebase.

## Quick checklist when reviewing a security-sensitive change

- [ ] No full `Client` objects passed into agent prompts or logs
- [ ] No new env var with an unsafe string default (look at `os.getenv("X", "...")`)
- [ ] No query/migration that joins `healthflow.db` and `healthflow_data.db`
- [ ] 401 from external APIs handled distinctly from other auth errors
- [ ] No new file path that could end up checked in containing PHI (`.db`, `.log`, cache dumps)
