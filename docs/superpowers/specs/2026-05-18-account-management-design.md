# Account Management

**Date:** 2026-05-18
**Status:** Approved (design)
**Part of:** HIPAA-readiness portfolio-credible foundation — first follow-up to the five-piece foundation, builds on the auth-hardening deferrals.

## Problem

Auth-hardening (PR #12) landed account lockout, refresh-token rotation, fail-loud `JWT_SECRET`, and a real password policy. It explicitly deferred four account-management features that pair together:

1. **No `/auth/change-password`.** An authenticated broker cannot rotate their password without an admin reset.
2. **No `/auth/forgot-password`.** A broker who forgets their password has no recovery path other than asking an admin to issue a new password manually.
3. **No admin RBAC.** `Broker.role` defaults to `"broker"` and is a freeform string; nothing enforces it anywhere. The first place we'd actually check it is the admin force-unlock endpoint.
4. **No admin force-unlock.** Lockout auto-expires after 15 minutes, but during the window the user is stuck. For a portfolio piece this is workable; for a real product an admin needs an unlock button.

(2) drags in an entirely new dependency — email delivery — that the other three don't share, but the four read together as one coherent "account management" story and ship more cleanly in a single PR.

## Goal

Four endpoints, one supporting subsystem (email), and a bootstrap path for the first admin.

- `POST /auth/change-password` lets an authenticated broker rotate their own password (re-auth via current password; revokes all of their refresh tokens on success).
- `POST /auth/forgot-password` accepts an email, always returns 200 with a generic message (no enumeration), and — when the email matches a broker and the per-email cooldown window is clear — issues a single-use reset token and sends an email via the Mailer subsystem.
- `POST /auth/reset-password` consumes a reset token + new password; rotates the password; marks the token used; revokes the broker's refresh tokens.
- `POST /admin/brokers/{broker_id}/unlock` lets an admin reset `failed_login_count` and `locked_until` on any broker, with an audit log entry.
- A `Mailer` subsystem with `ConsoleMailer` (dev/test default) and `SesMailer` (AWS SES production target), selected by `EMAIL_PROVIDER` env var.
- A `scripts/promote_admin.py` CLI script as the only path to create the first admin.

## Non-Goals

- **MFA (TOTP).** Its own future sub-project — needs an enrollment flow + recovery codes + frontend, all bigger than this PR.
- **Email notifications for security events** ("you just changed your password", "your account was locked", "new login from X"). Pairs with anomaly detection; would multiply the templates and the test surface for marginal benefit today.
- **Per-IP rate limiting on auth endpoints.** Per-email cooldown via the token table covers the forgot-password email-bomb case without introducing a Redis dependency. Per-IP limiting pairs with anomaly detection.
- **Self-service email-change verification.** The existing `PUT /auth/profile` lets a broker change their email without re-verification. Tightening that pairs better with the email-notifications work; deferred.
- **Frontend pages.** This PR is backend + Mailer only. The reset-password frontend page is implied by the reset URL but is a separate frontend PR.
- **Alembic migrations.** The two new tables and the role check use `Base.metadata.create_all` like the rest of the project. Alembic is a project-wide concern, not this sub-project's to introduce.
- **Account deletion / data export (GDPR).** Separate compliance sub-project.
- **Token-shape upgrades (PASETO, etc).** Stick with JWT for consistency with access + refresh + reset tokens.

## Design

### Architecture

Four endpoints + one Mailer subsystem + one admin-bootstrap CLI. Each piece lands as its own task; suite stays green between commits.

**Files touched:**

- `healthflow/email/__init__.py`, `healthflow/email/mailer.py` *(new)* — `Mailer` protocol, `ConsoleMailer`, `SesMailer`, `get_mailer()` lazy-singleton.
- `healthflow/email/templates.py` *(new)* — `render_password_reset(email, reset_url)` returning `(subject, text_body, html_body)`. Inline f-string templates.
- `healthflow/auth/router.py` *(modify)* — append `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password`.
- `healthflow/auth/admin_router.py` *(new)* — `/admin/brokers/{broker_id}/unlock`, mounted under prefix `/admin`.
- `healthflow/auth/dependencies.py` *(modify)* — add `require_admin` (depends on `get_current_broker`, raises 403 if role != "admin").
- `healthflow/auth/security.py` *(modify)* — `create_password_reset_token()` / `verify_password_reset_token()` helpers (JWT, 1h expiry, `type="reset"`).
- `healthflow/database/models.py` *(modify)* — new `PasswordResetToken` model (system table, same pattern as `RefreshToken`).
- `healthflow/models/schemas.py` *(modify)* — `ChangePasswordRequest`, `ForgotPasswordRequest`, `ResetPasswordRequest`. New-password fields use `validate_password` via a Pydantic `field_validator`.
- `healthflow/main.py` *(modify)* — mount the new `admin_router`.
- `scripts/promote_admin.py` *(new)* — `python scripts/promote_admin.py --email X` flips role to `"admin"`; logs via `AuditLogger`.
- `requirements.txt` *(modify)* — add `boto3>=1.34` (imported lazily inside `_build_mailer` only when `EMAIL_PROVIDER=ses`).
- `healthflow/tests/conftest.py` *(modify)* — set `EMAIL_PROVIDER=console` at import time alongside `JWT_SECRET` / `PHI_ENCRYPTION_KEY`.
- `healthflow/tests/auth/test_account_management.py` *(new)* — 31 tests covering all four endpoints + admin-bootstrap script + Mailer behaviors.
- `.env.example` *(modify)* — document `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, and `FRONTEND_BASE_URL`.
- `.claude/skills/healthflow-security/SKILL.md` *(modify)* — document the new RBAC rule, change-password / reset-password token-revocation behavior, and the per-email cooldown.

**Key separations:**

- `PasswordResetToken` is a system table — not tenant-scoped, not in `_AUDITED_MODELS`. Same call as `RefreshToken`. Reset bookkeeping is auth metadata, not patient-data access.
- The admin-unlock event IS audit-worthy (admin acting on someone else's account) and goes through `AuditLogger.log("admin_force_unlock", {...})` — not `phi_access_log` (it's not PHI), but it goes into the structured audit stream.
- `require_admin` lives in `dependencies.py` (alongside `get_current_broker`) because it depends on it. `admin_router.py` imports it. No circular dependency.
- The Mailer module never touches the DB or auth. It accepts a rendered email and sends. `templates.py` is pure functions. The router orchestrates: generate token → persist row → render template → call mailer.

### 1. Mailer subsystem

`healthflow/email/mailer.py`:

```python
import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None: ...


class ConsoleMailer:
    """Dev/test mailer — logs the email body at INFO. No network I/O."""
    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        logger.info("EMAIL[to=%s, subject=%s]\n%s", to, subject, text_body)


class SesMailer:
    """Production mailer backed by AWS SES."""
    def __init__(self, client, from_address: str):
        self._client = client
        self._from = from_address

    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        self._client.send_email(
            Source=self._from,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Text": {"Data": text_body},
                    "Html": {"Data": html_body},
                },
            },
        )


_INSTANCE: Mailer | None = None


def get_mailer() -> Mailer:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _build_mailer()
    return _INSTANCE


def _build_mailer() -> Mailer:
    provider = os.getenv("EMAIL_PROVIDER", "console")
    if provider == "console":
        return ConsoleMailer()
    if provider == "ses":
        import boto3  # local import — boto3 only loaded when actually used
        from_addr = os.getenv("EMAIL_FROM_ADDRESS")
        if not from_addr:
            raise RuntimeError("EMAIL_FROM_ADDRESS is required when EMAIL_PROVIDER=ses")
        return SesMailer(boto3.client("ses"), from_addr)
    raise RuntimeError(f"Unknown EMAIL_PROVIDER: {provider!r}")
```

- `_INSTANCE` is lazy (not module-load-time) so tests can `monkeypatch.setattr(mailer, "_INSTANCE", FakeMailer())` before any code path hits `get_mailer`.
- `boto3` is imported inside `_build_mailer` — `EMAIL_PROVIDER=console` (the default) never loads it. Keeps cold-start fast for dev / tests / CI.
- Production fail-loud (missing `EMAIL_FROM_ADDRESS`) happens on first `get_mailer()` call, not at module import — acceptable because the first request that hits forgot-password surfaces it immediately, and deferring the check keeps the import-time graph clean.

**HIPAA note for `.env.example`:** AWS SES is covered under the standard AWS BAA. Set `EMAIL_PROVIDER=ses` only in environments where a signed AWS BAA is in place if real PHI is being processed.

### 2. Templates

`healthflow/email/templates.py`:

```python
def render_password_reset(email: str, reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your HealthFlow password"
    text_body = f"""Hello,

We received a request to reset your HealthFlow password.

Click this link within the next hour to set a new password:
{reset_url}

If you didn't request this, you can safely ignore this email.

— HealthFlow
"""
    html_body = f"""<p>Hello,</p>
<p>We received a request to reset your HealthFlow password.</p>
<p><a href="{reset_url}">Reset password</a> (link expires in 1 hour)</p>
<p>If you didn't request this, you can safely ignore this email.</p>
<p>— HealthFlow</p>
"""
    return subject, text_body, html_body
```

Inline strings, no Jinja, no template directory. If a second template ever exists this gets revisited. The `email` parameter is reserved for future personalization but not interpolated today (the email content is identical regardless of the recipient — only the URL varies).

### 3. `PasswordResetToken` model

```python
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- `broker_id` is a plain indexed `GUID` (no FK) matching the `RefreshToken` / `PhiAccessLog` pattern.
- **NOT** added to `_AUDITED_MODELS` — same reasoning as `RefreshToken`.
- The cooldown query is `WHERE broker_id = :b AND used_at IS NULL AND created_at > :now - 60s ORDER BY created_at DESC LIMIT 1` — if it returns a row, we don't issue a new token.

### 4. JWT helpers

In `healthflow/auth/security.py`:

```python
PASSWORD_RESET_EXPIRE_MINUTES = 60

def create_password_reset_token(broker_id: uuid.UUID, jti: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(broker_id),
        "type": "reset",
        "jti": str(jti),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

Decoding reuses the existing `decode_token()` helper; the router checks `payload["type"] == "reset"`. The DB row is the source of truth for `used_at` and exists-or-not — the JWT just carries the `jti` and provides tamper-detection.

### 5. `require_admin` dependency

In `healthflow/auth/dependencies.py`:

```python
async def require_admin(broker: Broker = Depends(get_current_broker)) -> Broker:
    if broker.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return broker
```

Returns the admin broker so the route can use the admin's id for audit logging. No bearer → 401 from `get_current_broker` (propagated, not overwritten). Wrong role → 403.

### 6. Endpoint contracts

**`POST /auth/change-password`** — authenticated broker rotates their own password.

Request: `{"current_password": str, "new_password": str}`
Response: `204 No Content`

Flow:
1. `get_current_broker` dependency loads the broker.
2. `verify_password(current_password, broker.hashed_password)` → if wrong, raise `HTTPException(401, "Invalid current password")`.
3. `validate_password(new_password)` runs via the Pydantic `field_validator` on the request model; failure surfaces as `422` with the rule string.
4. `broker.hashed_password = hash_password(new_password)`.
5. **Revoke all of this broker's active refresh tokens**: `UPDATE refresh_tokens SET revoked_at = now WHERE broker_id = :b AND revoked_at IS NULL`. Forces re-login on every other device.
6. Commit (single transaction — password update + revocation must succeed or fail together). Return 204.

**`POST /auth/forgot-password`** — unauthenticated, kicks off email flow.

Request: `{"email": str}`
Response: `200 {"message": "If an account exists for that email, a reset link has been sent."}`

Flow (server-side):
1. Look up broker by email. If not found, return the generic message.
2. **Cooldown check**: if a `PasswordResetToken` row for this `broker_id` exists with `used_at IS NULL` and `created_at > now - 60s`, return the generic message without sending.
3. Generate `jti = uuid.uuid4()`. Create `PasswordResetToken` row (`broker_id`, `created_at=now`, `expires_at=now+1h`, `used_at=None`).
4. **Commit the row first** (`await db.commit()`). The cooldown row must survive a mailer failure — otherwise a flaky mailer makes the cooldown moot and the audit entry orphaned.
5. Sign reset JWT with `jti`. Build `reset_url = f"{FRONTEND_BASE_URL}/reset-password?token={token}"`. `FRONTEND_BASE_URL` from env, fail-loud at first use if unset.
6. `subject, text, html = render_password_reset(email, reset_url)`.
7. Try `get_mailer().send(email, subject, text, html)`. On any exception: catch broadly, `AuditLogger.log("password_reset_send_failed", {"broker_id": str(broker.id), "error": repr(e)})`. **Do NOT change the response.**
8. Return the generic message.

**`POST /auth/reset-password`** — unauthenticated, completes the flow.

Request: `{"token": str, "new_password": str}`
Response: `204 No Content`

Flow:
1. `validate_password(new_password)` via Pydantic.
2. Decode JWT → on `ValueError`, raise `HTTPException(401, "Invalid or expired reset token")`.
3. Assert `payload["type"] == "reset"` → else same 401.
4. Look up `PasswordResetToken` row by `jti`. If missing, `used_at IS NOT NULL`, or `expires_at < now` → same 401.
5. Load broker by `sub`. If not found or inactive → same 401.
6. `broker.hashed_password = hash_password(new_password)`.
7. `row.used_at = datetime.now(timezone.utc)`.
8. **Revoke all of broker's active refresh tokens** (same query as change-password).
9. Commit (single transaction — password update + `used_at` + revocation must succeed or fail together). Return 204.

**`POST /admin/brokers/{broker_id}/unlock`** — admin force-unlocks a locked account.

Request: empty body. Path param: `broker_id` (UUID).
Response: `200 {"unlocked": true}`

Flow:
1. `require_admin` dependency yields the calling admin (else 401/403).
2. Load target broker by id. If not found → `HTTPException(404, "Broker not found")`.
3. `target.failed_login_count = 0; target.locked_until = None`.
4. Commit.
5. `AuditLogger.log("admin_force_unlock", {"admin_id": str(admin.id), "target_broker_id": str(broker_id)})`.
6. Return `{"unlocked": true}`.

Idempotent — unlocking an already-unlocked account returns the same 200 with the same body.

### 7. Admin bootstrap

`scripts/promote_admin.py`:

```python
"""Promote a broker to admin role.

Usage: python scripts/promote_admin.py --email someone@example.com

The first admin must be created this way (no API path creates admins).
Subsequent admins can also use this script, or — once a frontend admin panel
exists — be promoted from there. Either way, the change is audit-logged.
"""
```

- Uses `click` (already a dep).
- Runs inside `system_context("admin promotion CLI")` to bypass tenant filter.
- Exits 0 on success with `Promoted <email> to admin.` on stdout.
- Exits 1 on not-found with `No broker found with email <email>.` on stderr.
- Calls `AuditLogger.log("admin_promoted", {"target_broker_id": str(broker.id), "via": "promote_admin.py"})` on success.

### 8. Error handling matrix

Generic-by-default. Every "this didn't work" returns the same shape; differentiating helps the attacker more than the user.

| Endpoint | Failure mode | Response |
|---|---|---|
| `POST /auth/change-password` | Wrong current password | `401 {"detail": "Invalid current password"}` |
| `POST /auth/change-password` | New password fails policy | `422` from Pydantic (rule string in detail) |
| `POST /auth/change-password` | No bearer / invalid bearer | `401` from `get_current_broker` |
| `POST /auth/forgot-password` | Email doesn't exist | `200 {"message": "If an account exists..."}` |
| `POST /auth/forgot-password` | Cooldown active | `200 {"message": "If an account exists..."}` |
| `POST /auth/forgot-password` | Mailer raises | `200`; `AuditLogger.log("password_reset_send_failed", ...)` |
| `POST /auth/reset-password` | Token invalid / expired / used / wrong type | `401 {"detail": "Invalid or expired reset token"}` |
| `POST /auth/reset-password` | New password fails policy | `422` from Pydantic |
| `POST /admin/brokers/{id}/unlock` | Not authenticated | `401` from `get_current_broker` |
| `POST /admin/brokers/{id}/unlock` | Not admin | `403 {"detail": "Admin role required"}` |
| `POST /admin/brokers/{id}/unlock` | Target broker not found | `404 {"detail": "Broker not found"}` |

Two subtle points:

1. **Forgot-password's "same response on mailer failure"** is intentional. A flaky SES would otherwise become a side-channel oracle (`200` = email exists, `500` = exists but send broke). The audit log captures the server-side reality.
2. **Reset-password's single 401 for all four failure modes** (invalid JWT signature / unknown jti / `used_at IS NOT NULL` / `expires_at < now`). Differentiating would help users debug typos but help attackers more (e.g., "valid jti, already used" tells them they hit a real account).

### 9. Test plan

One new file `healthflow/tests/auth/test_account_management.py` + a tweak to `conftest.py` to set `EMAIL_PROVIDER=console` at import time. Grouped by piece, 31 tests total.

**Mailer (4 tests)**
- `ConsoleMailer.send` logs the body at INFO with `to=` / `subject=` markers.
- `get_mailer()` returns `ConsoleMailer` when `EMAIL_PROVIDER=console`.
- `get_mailer()` builds `SesMailer` when `EMAIL_PROVIDER=ses` (monkeypatch `boto3.client` to a stub; assert `_from` set from `EMAIL_FROM_ADDRESS`).
- `get_mailer()` raises `RuntimeError` for `EMAIL_PROVIDER=ses` without `EMAIL_FROM_ADDRESS`.

**`require_admin` dependency (3 tests)**
- Returns the broker when `role == "admin"`.
- Raises 403 when `role == "broker"`.
- Inherits 401 propagation from `get_current_broker` (no bearer → 401, not 403).

**`/auth/change-password` (6 tests)**
- Happy path: valid current + valid new → 204; `broker.hashed_password` rehashed; `verify_password(new, ...)` succeeds.
- Wrong current → 401, password unchanged.
- New password fails policy (too short / no symbol / common-list hit — parameterized) → 422.
- No bearer → 401.
- Revokes all of this broker's active refresh tokens (assert `revoked_at IS NOT NULL` on every row pre-existing for that broker).
- Does NOT revoke OTHER brokers' refresh tokens (isolation regression).

**`/auth/forgot-password` (5 tests)**
- Known email → 200 generic message; one `PasswordResetToken` row created; `ConsoleMailer` received one send call with the reset URL.
- Unknown email → 200 same message; zero `PasswordResetToken` rows; zero mailer calls.
- Cooldown: two consecutive requests within 60s → second produces zero new rows and zero mailer calls; response still 200.
- After cooldown window expires (advance the clock via `monkeypatch.setattr` on `datetime`) → third request produces a new row.
- Mailer raises → 200 response unchanged; `PasswordResetToken` row still exists (cooldown survives); `AuditLogger` saw `password_reset_send_failed`.

**`/auth/reset-password` (6 tests)**
- Happy path: token from forgot-password flow → 204; password rehashed; row's `used_at IS NOT NULL`.
- Invalid JWT → 401 generic message.
- Token with wrong `type` claim → 401.
- Expired token → 401 (`expires_at < now`).
- Reused token (replay) → 401; password remains the rotated one.
- Revokes all of broker's active refresh tokens (same assertion as change-password).

**`/admin/brokers/{id}/unlock` (5 tests)**
- Admin unlocks locked broker → 200; `failed_login_count == 0`; `locked_until is None`; locked broker can now log in.
- Non-admin gets 403; broker state unchanged.
- Unknown broker_id → 404.
- Already-unlocked broker → 200 (idempotent); state unchanged.
- Emits `AuditLogger.log("admin_force_unlock", {...})` with both `admin_id` and `target_broker_id`.

**Admin bootstrap script (2 tests)**
- `promote_admin.py --email known@example.com` flips role and exits 0; audit event logged.
- Unknown email → non-zero exit; no DB writes; clear stderr message.

### 10. Rollout (per-task, each commit green)

1. **Baseline + branch.** Capture pre-impl test count, confirm baseline green. Add `EMAIL_PROVIDER=console` to `conftest.py` and `docker-compose.test.yml`. Run the suite to confirm no regression.
2. **Mailer subsystem** + 4 tests. `healthflow/email/mailer.py`, `templates.py`, `requirements.txt` (boto3).
3. **`PasswordResetToken` model + JWT helpers** (no endpoint yet — model + `create_password_reset_token` / decode check helpers).
4. **`require_admin` dependency** + 3 tests.
5. **`/auth/change-password`** + 6 tests.
6. **`/auth/forgot-password` + `/auth/reset-password`** + 11 tests. These ship together — splitting forgot from reset leaves an unusable half-flow.
7. **`admin_router.py` + `/admin/brokers/{id}/unlock` + mount in `main.py`** + 5 tests.
8. **`scripts/promote_admin.py`** + 2 tests.
9. **`healthflow-security` skill update** — RBAC rule, change-password/reset token revocation, per-email cooldown, mailer provider selection, BAA note.
10. **`.env.example` update** + final verification + push + PR.

### 11. Database migration

Same approach as auth-hardening:

- `Base.metadata.create_all` picks up the new `password_reset_tokens` table on startup.
- No `ALTER TABLE` needed (no new columns on existing tables).
- For dev DBs that already exist: `create_all` is idempotent and creates the new table on next startup. Documented in PR description.

### 12. Risks

| Risk | Mitigation |
|---|---|
| Reset-token email goes to attacker who controls the inbox | Out of scope to defend against (you control your email = you own the account). MFA sub-project mitigates by adding a second factor. |
| `_INSTANCE` global leaks between tests if not reset | `conftest.py` sets `EMAIL_PROVIDER=console` and resets `_INSTANCE = None` in a teardown fixture for the mailer test module. |
| `boto3` adds 10MB to the image | Local import inside `_build_mailer` keeps it out of the import graph for `EMAIL_PROVIDER=console`. Acceptable for the prod image once provider is enabled. |
| SES sandbox mode blocks sending to unverified addresses on first deploy | Document in `.env.example`: SES starts in sandbox; request production access before going live; verify the `EMAIL_FROM_ADDRESS` domain first. |
| Per-email cooldown allows email-bomb with multiple emails | The cooldown caps per-address requests at 60/hour. Cross-address flooding is per-IP territory — explicitly deferred to anomaly detection. |
| `FRONTEND_BASE_URL` env var not set in prod → broken reset links | Add fail-loud check on first forgot-password request (same pattern as `EMAIL_FROM_ADDRESS`). |
| Admin bootstrap script run against wrong DB → wrong account promoted | Script prints `Promoted <email> to admin.` and the connected DB URL before exiting. User confirms by reading output. |
| Reset token JWT signed with `JWT_SECRET` collides semantically with access/refresh tokens | The `type` claim (`"reset"` vs `"access"` vs `"refresh"`) discriminates. Endpoints explicitly check `type`. |
| Race: two simultaneous forgot-password requests within the cooldown window both pass the check | The cooldown is best-effort UX, not a security boundary. Worst case: one extra email. The token table accumulates two rows; both still expire in 1h. |
| Change-password / reset-password revoke loop in a transaction may deadlock | The `UPDATE refresh_tokens` is by indexed `broker_id` only; no other writer touches the same rows in the same transaction. Single-statement update is safe. |

## Acceptance

This sub-project is done when:

1. An authenticated broker can `POST /auth/change-password` with their current and a new password; the new password is enforced by `validate_password`; all of their refresh tokens are revoked.
2. An unauthenticated request to `POST /auth/forgot-password` always returns 200 with a generic message; a real-email request creates a `PasswordResetToken` row and sends an email via the active Mailer; a duplicate request within 60s is silently swallowed.
3. `POST /auth/reset-password` with a valid single-use token rotates the password, marks the token used, and revokes the broker's refresh tokens; replay, expiry, wrong-type, and invalid tokens all return the same generic 401.
4. `POST /admin/brokers/{id}/unlock` lets an admin clear `failed_login_count` / `locked_until` on any broker; non-admins get 403; the action is audit-logged with both ids.
5. `scripts/promote_admin.py --email X` is the only path to create admins; the change is audit-logged.
6. `EMAIL_PROVIDER=console` is the default; `EMAIL_PROVIDER=ses` (with `EMAIL_FROM_ADDRESS`) sends real email via AWS SES.
7. The full test suite (existing + 31 new tests) is green.
8. The `healthflow-security` skill documents the new rules (RBAC, per-email cooldown, token revocation on password change, mailer provider selection + BAA note).

## Out of Scope

Each is a deliberate deferral with a clear next home:

- MFA (TOTP) — its own future sub-project.
- Email notifications for security events ("password changed", "new login from X") — pairs with anomaly detection.
- Per-IP rate limiting on auth endpoints — pairs with anomaly detection.
- Self-service email-change verification — pairs with email notifications.
- Frontend pages (reset-password page, admin unlock UI) — separate frontend PR.
- Alembic migrations — project-wide concern, not this sub-project's to introduce.
- Account deletion / data export (GDPR) — separate compliance sub-project.
- Password rotation / max-age policy — YAGNI for a portfolio piece.
