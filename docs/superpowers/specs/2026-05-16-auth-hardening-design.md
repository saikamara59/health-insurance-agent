# Auth Hardening

**Date:** 2026-05-16
**Status:** Approved (design)
**Part of:** HIPAA-readiness portfolio-credible foundation (sub-project #4 of 5)

## Problem

HealthFlow's authentication has four concrete weaknesses that the `healthflow-security` skill has been flagging since day one:

1. **`JWT_SECRET` defaults to a known string.** `healthflow/auth/security.py:7`:
   ```python
   JWT_SECRET = os.getenv("JWT_SECRET", "healthflow-dev-secret-change-in-production")
   ```
   A deploy that forgets to set the env var silently runs with the known-bad value. Every JWT signed with that key is forgeable by anyone who has read the source.
2. **Password policy is essentially absent.** Only Pydantic's `min_length=8` enforces anything; "Password" passes, so does "12345678". No complexity rule, no common-password block-list.
3. **Unlimited login attempts.** `/auth/login` has no failed-attempt counter and no lockout. A brute-force attempt is bounded only by network bandwidth.
4. **Refresh tokens never rotate or revoke.** `/auth/refresh` issues a new access token but the same refresh token stays valid for its full 7-day expiry. Stolen refresh tokens cannot be invalidated; `/logout` does not exist.

## Goal

A defensible auth layer for the portfolio-grade HIPAA-readiness story:

- `JWT_SECRET` is loaded fail-loud — a missing or known-bad value raises at module import, so a misconfigured deploy crashes immediately.
- Passwords enforced at register time: ≥12 characters, letter + digit + non-alphanumeric, not in a bundled common-passwords block-list. Existing accounts keep working under their current passwords; the policy applies to new registrations and (future) password changes.
- Account lockout: 5 failed login attempts → 15-minute timed lock. Counter and lock persist on the `Broker` row, auto-expire, reset on successful login. Lock state is never leaked to the client (same generic 401 as wrong-password).
- Refresh-token rotation: every `/auth/refresh` issues a new refresh token and revokes the old one via a `refresh_tokens` table. Replaying a revoked token is treated as theft — all of that broker's refresh tokens get revoked, forcing re-login. A new `/auth/logout` revokes the presented refresh token.

## Non-Goals

Each of these is a deliberate deferral that would make this sub-project too large to land cleanly:

- **MFA (TOTP).** Its own sub-project — needs a frontend flow (enrollment QR, code entry, recovery codes) bigger than the rest of this PR combined.
- **`/auth/change-password` endpoint.** Pairs with the (deferred) "account management" sub-project that also covers forgot-password and admin force-reset.
- **`/auth/forgot-password` with email verification.** Deferred to the "account management" sub-project — needs an email-provider decision, a `password_reset_token` table, two new endpoints, two email templates, frontend pages, and rate limiting. Treated as its own focused PR.
- **Admin RBAC + admin force-unlock.** Deferred (already flagged from the multi-tenancy work). Lockout auto-expires after 15 minutes, which is the recovery path for now.
- **Per-IP rate limiting on auth endpoints** (separate concern from per-account lockout). Defer until anomaly detection.
- **Password rotation / max-age policy.** YAGNI for a portfolio piece.
- **Email notifications** ("new login from X", "your account was locked"). Pairs with the email-provider work in the deferred sub-project.

## Design

### Architecture

Four independent changes that share files but don't depend on each other — each lands as its own task, suite stays green between them.

The four pieces touch:

- `healthflow/auth/security.py` — `_load_jwt_secret()` helper; `validate_password()` helper; common-password frozenset.
- `healthflow/auth/router.py` — register password validation; login lockout flow; rewritten `/refresh`; new `/logout`.
- `healthflow/database/models.py` — two new `Broker` columns; new `RefreshToken` model.
- `healthflow/tests/auth/` — `test_auth_hardening.py` (new) plus tweaks to existing tests; an autouse conftest fixture that sets `JWT_SECRET` for the test process.

`get_current_broker` in `dependencies.py` is unchanged — lockout belongs on the login path, not on every request.

### 1. `JWT_SECRET` fail-loud

Replace `healthflow/auth/security.py:7` with:

```
_LEGACY_DEFAULT = "healthflow-dev-secret-change-in-production"

def _load_jwt_secret() -> str:
    value = os.getenv("JWT_SECRET")
    if not value:
        raise RuntimeError("JWT_SECRET environment variable is required")
    if value == _LEGACY_DEFAULT:
        raise RuntimeError("JWT_SECRET is set to the legacy default — set a real secret")
    return value

JWT_SECRET = _load_jwt_secret()
```

Module-import-time check — a misconfigured deploy crashes on startup, not at first login. The `.env.example` is updated with `JWT_SECRET=<generate a long random string>` and a note.

**Test fixture for the suite** lands BEFORE this change: `healthflow/tests/conftest.py` (or a `pytest.ini`/`pyproject.toml` `env =` block — pick whichever the project already uses) sets `JWT_SECRET=test-secret-not-for-production` before any auth imports. Without this, removing the default breaks every existing test.

### 2. Password policy

New helper in `healthflow/auth/security.py`:

```
_COMMON_PASSWORDS: frozenset[str] = frozenset(
    open(Path(__file__).parent / "common_passwords.txt").read().splitlines()
)

def validate_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not any(c.isalpha() for c in password):
        raise ValueError("Password must contain a letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain a digit")
    if all(c.isalnum() for c in password):
        raise ValueError("Password must contain a non-alphanumeric character")
    if password.lower() in _COMMON_PASSWORDS:
        raise ValueError("Password is too common — choose something less guessable")
```

`common_passwords.txt` ships in `healthflow/auth/` as a 200-line file (lowercased SecLists top-200). The frozenset is module-load-time, no I/O per call.

Wired into `BrokerCreate` via a Pydantic `field_validator` on `password` that calls `validate_password` and raises `ValueError` (Pydantic surfaces as 422 with the rule string).

**Existing brokers with shorter/weaker passwords keep working.** The policy applies only at register time today; the future change-password endpoint will enforce it then.

### 3. Account lockout

Two columns added to `Broker` in `models.py`:

```
failed_login_count: int = 0
locked_until: datetime | None = None
```

`/auth/login` flow becomes:

1. Load broker by email — generic 401 if not found (same as today, no enumeration).
2. **Lock check:** `if broker.locked_until and broker.locked_until > now: 401` with the *same* generic message as wrong-password. Don't reveal lock state.
3. `verify_password(...)`. On fail:
   - `broker.failed_login_count += 1`
   - If `failed_login_count >= 5`: `broker.locked_until = now + 15min`
   - `await db.commit()` (need to commit so the counter persists across requests)
   - Return generic 401.
4. On success: `broker.failed_login_count = 0; broker.locked_until = None`; issue tokens; commit.

No separate table — lock state is per-broker, fits naturally on `Broker`. No "you have N attempts left" hint to the client (a brute-force aid). The 15-minute auto-expiry is the recovery path; admin force-unlock is a future sub-project follow-up.

### 4. Refresh-token rotation + revocation

New model in `models.py` (system table, same pattern as `PhiAccessLog` — not tenant-scoped, not audited):

```
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
```

`broker_id` is a plain indexed `GUID` (not a `ForeignKey`), matching the `PhiAccessLog.broker_id` pattern — these system tables hold "who acted," not "who owns this row."

**Token-creation flow** (in `create_refresh_token`): create a `RefreshToken` row first, embed its `id` as the JWT `jti` claim, then sign the JWT. The JWT itself stays the same shape (`sub`, `type`, `exp`) plus the new `jti`.

**`/auth/refresh` flow** (rewritten):

1. Decode the refresh JWT (existing behavior). On invalid: 401.
2. Look up the `RefreshToken` row by `jti = payload["jti"]`. If missing: 401.
3. **Theft check:** if `row.revoked_at is not None`:
   - This token was already used — replay = theft signal.
   - `UPDATE refresh_tokens SET revoked_at = now WHERE broker_id = :b AND revoked_at IS NULL` — revoke all of that broker's active tokens, force re-login.
   - Emit a WARN-level audit event via the existing `AuditLogger`: `audit.log("refresh_token_replay_revoke_all", {"broker_id": ..., "presented_jti": ...})`. (NOT a `phi_access_log` entry — refresh-token events are auth, not PHI access.)
   - Return 401.
4. Revoke the presented token: `row.revoked_at = now`.
5. Create a new `RefreshToken` row; issue a new access token AND a new refresh token containing the new row's `id` as `jti`.
6. Commit; return both tokens.

**`/auth/logout` endpoint** (new): takes a `RefreshRequest` (the same shape as `/auth/refresh`), decodes the JWT, marks the corresponding `RefreshToken` row revoked. Access token expires naturally within 60 minutes. Returns 204.

**Important: `RefreshToken` is NOT in `_AUDITED_MODELS`.** Refresh-token bookkeeping is operational metadata, not patient-data access. Auditing every refresh would just create noise. The theft-signal mass-revoke is the one notable event and it goes through the WARN-level `AuditLogger`, not `phi_access_log`.

### Test plan

One new file `healthflow/tests/auth/test_auth_hardening.py` plus targeted extensions to existing `test_auth.py` / `test_auth_integration.py`. Grouped by piece:

**1. JWT_SECRET fail-loud (3 tests)** — use `monkeypatch.delenv("JWT_SECRET", raising=False)` + `importlib.reload(security)` to exercise:
- Unset env var → `RuntimeError`.
- Set to the legacy default → `RuntimeError`.
- Set to any other value → imports cleanly, `JWT_SECRET` matches.

**2. Password policy (6 tests)** —
- `validate_password` accepts a compliant password (e.g. `"Cromulent42!"`).
- Rejects too-short, letters-only, digits-only, no-symbol — one test each.
- Rejects a known common password (one from the bundled list).
- `/auth/register` returns 422 with a useful message on each kind of failure (one parameterized test).
- Regression: an existing broker with a 9-char alpha password can still log in (only register enforces the rule).

**3. Account lockout (5 tests)** —
- 4 failed attempts → 5th attempt still allowed (counter at 4, not locked).
- 5 failed attempts → 6th attempt returns 401; lock check fires before password verification (assert via a known-correct password that still gets 401 once locked).
- Lock auto-expires after 15 minutes (`monkeypatch.setattr` on `datetime.now` to advance the clock; `freezegun` is not in deps).
- Successful login resets both counter and any leftover `locked_until`.
- Lock check uses the *same* generic 401 message as wrong-password (no enumeration via response text).

**4. Refresh-token rotation (6 tests)** —
- `/auth/login` creates a `RefreshToken` row with `revoked_at = NULL` and a `jti` matching the JWT.
- `/auth/refresh` revokes the presented token's row, creates a new row, returns new access + refresh tokens with a new `jti`.
- Replaying the old refresh token returns 401.
- **Theft signal:** replaying a revoked token revokes ALL of that broker's active rows AND emits a WARN-level `refresh_token_replay_revoke_all` audit event.
- `/auth/logout` revokes the presented token's row; subsequent `/auth/refresh` with it returns 401.
- An expired refresh token (past the 7-day JWT `exp`) returns 401 without the theft-signal mass-revoke (normal expiration, not theft).

### Rollout (per-task, each commit green)

1. **Baseline + branch.** Capture pre-impl test count, confirm baseline green.
2. **Test conftest sets `JWT_SECRET`.** Before any other change. Required so the next step's fail-loud doesn't break the existing suite. Run the suite to confirm no regression.
3. **JWT_SECRET fail-loud** + 3 tests.
4. **Password policy** — `common_passwords.txt`, `validate_password`, register-endpoint wiring, 6 tests.
5. **Broker lockout columns + login flow** + 5 tests.
6. **`RefreshToken` model + `/refresh` rewrite + `/logout`** + 6 tests.
7. **Skill update** — `healthflow-security` documents the new rules (JWT_SECRET has no default; password policy enforcement point; lockout policy; refresh rotation + theft signal).
8. **Final verification + push + PR.**

### Database migration

Project uses `Base.metadata.create_all` at startup (no alembic) — see `healthflow/database/config.py` and `healthflow/main.py`. The two new `Broker` columns and the new `RefreshToken` table are picked up automatically on next startup.

**But:** `create_all` does NOT add columns to an existing table. For dev databases that already have a `brokers` table, the new `failed_login_count` / `locked_until` columns won't appear automatically — `SELECT` against the new columns will fail with `OperationalError: no such column`.

Mitigations:
- For dev/CI: tests use in-memory SQLite which is fresh each run — no issue.
- For the user's local `healthflow.db`: a one-liner `python -c "import sqlite3; conn = sqlite3.connect('healthflow.db'); conn.execute('ALTER TABLE brokers ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0'); conn.execute('ALTER TABLE brokers ADD COLUMN locked_until DATETIME'); conn.commit()"` documented in the PR description and in `.env.example` notes.
- For Docker: the lifespan's `create_all` creates `refresh_tokens` automatically; the two new `brokers` columns need the same ALTER TABLE — document as a one-time manual step in the PR.

Long-term, alembic is the right answer; explicitly out of scope for this sub-project.

### Risks

| Risk | Mitigation |
|---|---|
| Removing `JWT_SECRET` default breaks any code path that didn't set it (Docker, CI, `make dev`, `seed.py`) | Step 2 lands the test fixture; step 3 audits each entry point. `.env.example` documents the env var. `make dev` already sources `.env`. |
| Bundled common-passwords list grows stale | Start with SecLists top-200, document as a refreshable artifact in the spec, not a security claim of "exhaustive" |
| `freezegun` not in dependencies | Use `monkeypatch.setattr` on `datetime` for the time-travel test — no new dep |
| Existing tests run with the old default secret and break when it's removed | Order matters: step 2 (conftest fixture) lands BEFORE step 3 (fail-loud) |
| Two-clicks-on-refresh triggers the theft-signal mass-revoke for a legitimate user | The window is narrow because `/refresh` revokes atomically. If it proves noisy, the right fix is a short grace window — not added now; document the behavior |
| The lockout counter `commit()` inside `/login` could conflict with the existing request transaction | Audit the existing `/login` for any commit ordering. SQLAlchemy async session commits are explicit; one extra commit on the failure path is safe |
| Module-import-time fail-loud tests are awkward (`importlib.reload`) | The pattern is well-known and tested elsewhere in the suite (e.g. `test_test_router.py` reloads `config`); reuse the approach |
| Production `healthflow.db` lacks the new columns on first start after deploy | The PR description includes the one-time ALTER TABLE command. The fail-loud kicks in at startup but the column-missing failure surfaces only on first login attempt — surface as part of the deploy checklist in the PR |

## Acceptance

This sub-project is done when:

1. `JWT_SECRET` is read fail-loud (no default, no legacy value accepted); a misconfigured deploy raises at import.
2. New broker registration enforces the upgraded password policy (≥12 chars, complexity, common-list block); existing logins are unaffected.
3. 5 failed login attempts lock the account for 15 minutes; the lock auto-expires and resets on successful login; lock state is not leaked to the client.
4. Every `/auth/refresh` rotates the refresh token; replaying a revoked token triggers mass-revoke of that broker's active tokens; `/auth/logout` revokes the presented token.
5. The full test suite (existing + 20 new tests) is green.
6. The `healthflow-security` skill documents the four new rules.

## Out of Scope

Each is a deliberate deferral with a clear next home:
- MFA (TOTP) — its own future sub-project.
- `/auth/change-password`, `/auth/forgot-password` (email reset), email provider selection — the next "account management" sub-project after this one.
- Admin RBAC + admin force-unlock — deferred from multi-tenancy, paired with account management.
- Per-IP rate limiting on auth endpoints — pairs with anomaly detection.
- Password rotation / max-age policy.
- Email notifications for security events.
- Alembic migrations (one-off ALTER TABLE noted in PR for this change).
- Encryption at rest (sub-project #5).
