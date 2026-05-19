# Account Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four deferred account-management endpoints — `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password`, `/admin/brokers/{id}/unlock` — plus the supporting `Mailer` subsystem (`ConsoleMailer` + `SesMailer`), the `require_admin` dependency, and the `promote_admin.py` bootstrap script.

**Architecture:** Each endpoint sits in `healthflow/auth/router.py` (or a new `healthflow/auth/admin_router.py` for the admin route). A new `healthflow/email/` package owns the Mailer (`Mailer` protocol, `ConsoleMailer`, `SesMailer`, `get_mailer()` lazy-singleton). A new `PasswordResetToken` model joins `RefreshToken` and `PhiAccessLog` as a system table. The provider toggle is `EMAIL_PROVIDER=console|ses`; production targets AWS SES (BAA available). `boto3` is imported lazily so dev/test never load it.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x async, Pydantic 2, `python-jose` (JWT), `passlib[bcrypt]`, `click` (CLI), `boto3` (added). Test framework: `pytest` + `pytest-asyncio` + `httpx.AsyncClient`.

**Spec:** `docs/superpowers/specs/2026-05-18-account-management-design.md`

---

## File Structure

**New files:**
- `healthflow/email/__init__.py` — re-exports `Mailer`, `get_mailer`.
- `healthflow/email/mailer.py` — `Mailer` protocol, `ConsoleMailer`, `SesMailer`, `get_mailer()`, `_build_mailer()`.
- `healthflow/email/templates.py` — `render_password_reset(email, reset_url) -> (subject, text, html)`.
- `healthflow/auth/admin_router.py` — `admin_router` with `/admin/brokers/{broker_id}/unlock`.
- `scripts/promote_admin.py` — CLI script to flip a broker's role to `"admin"`.
- `healthflow/tests/auth/test_account_management.py` — all 31 new tests.

**Modified files:**
- `healthflow/auth/dependencies.py` — add `require_admin`.
- `healthflow/auth/security.py` — add `PASSWORD_RESET_EXPIRE_MINUTES`, `create_password_reset_token`.
- `healthflow/database/models.py` — add `PasswordResetToken` system table.
- `healthflow/models/schemas.py` — add `ChangePasswordRequest`, `ForgotPasswordRequest`, `ForgotPasswordResponse`, `ResetPasswordRequest`.
- `healthflow/auth/router.py` — append `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password`.
- `healthflow/main.py` — `app.include_router(admin_router)`.
- `healthflow/tests/conftest.py` — set `EMAIL_PROVIDER=console` and `FRONTEND_BASE_URL=https://test.example.com` at import time; teardown fixture resets the Mailer `_INSTANCE`.
- `requirements.txt` — add `boto3>=1.34`.
- `.env.example` — document `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `FRONTEND_BASE_URL`.
- `.claude/skills/healthflow-security/SKILL.md` — document RBAC, change-password / reset token revocation, per-email cooldown, mailer + BAA note.
- `docker-compose.test.yml` — add `EMAIL_PROVIDER=console` and `FRONTEND_BASE_URL=https://test.example.com` to both `backend` and `seed` services.
- `.github/workflows/e2e.yml` — add `EMAIL_PROVIDER: console` and `FRONTEND_BASE_URL: https://test.example.com` in the env block.

---

## Task 0: Baseline + branch + env-var groundwork

**Files:**
- Modify: `healthflow/tests/conftest.py:1-16`
- Modify: `docker-compose.test.yml`
- Modify: `.github/workflows/e2e.yml`
- Modify: `requirements.txt`

- [ ] **Step 1: Capture baseline test count and confirm green**

Run: `make test 2>&1 | tail -5`
Expected: `564 passed` (or whatever the current pre-change count is — record the number in the PR description).

- [ ] **Step 2: Create a working branch**

Run: `git checkout -b account-management`
Expected: switched to a new branch `account-management`.

- [ ] **Step 3: Add `EMAIL_PROVIDER=console` and `FRONTEND_BASE_URL` defaults to conftest**

Edit `healthflow/tests/conftest.py`. After the existing `PHI_ENCRYPTION_KEY` block (around line 16), add:

```python
# Default the email provider to the no-network ConsoleMailer for tests, and
# set FRONTEND_BASE_URL so the forgot-password router can build a reset link.
# Setting via setdefault keeps any explicit env override working.
os.environ.setdefault("EMAIL_PROVIDER", "console")
os.environ.setdefault("FRONTEND_BASE_URL", "https://test.example.com")
```

- [ ] **Step 4: Add `boto3` to requirements**

Edit `requirements.txt`. Append at the end:

```
boto3>=1.34
```

- [ ] **Step 5: Install the new dep**

Run: `.venv/bin/pip install -r requirements.txt -q`
Expected: succeeds.

- [ ] **Step 6: Mirror the env vars in `docker-compose.test.yml`**

Edit `docker-compose.test.yml`. In the `backend` `environment:` block, after `PHI_ENCRYPTION_KEY=...`, append:

```yaml
      - EMAIL_PROVIDER=console
      - FRONTEND_BASE_URL=https://test.example.com
```

Then add the same two lines under the `seed` service's `environment:` block.

- [ ] **Step 7: Mirror the env vars in `.github/workflows/e2e.yml`**

Edit `.github/workflows/e2e.yml`. In the `env:` block of the `Run Playwright` step, after `PHI_ENCRYPTION_KEY: AAAA...`, append:

```yaml
          EMAIL_PROVIDER: console
          FRONTEND_BASE_URL: https://test.example.com
```

- [ ] **Step 8: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -5`
Expected: same passing count as Step 1 (no new tests yet, nothing should have changed).

- [ ] **Step 9: Commit**

```bash
git add healthflow/tests/conftest.py docker-compose.test.yml .github/workflows/e2e.yml requirements.txt
git commit -m "Bootstrap env vars + boto3 dep for account-management work"
```

---

## Task 1: Mailer subsystem — Mailer protocol + ConsoleMailer + SesMailer + get_mailer

**Files:**
- Create: `healthflow/email/__init__.py`
- Create: `healthflow/email/mailer.py`
- Test: `healthflow/tests/auth/test_account_management.py`
- Modify: `healthflow/tests/conftest.py`

- [ ] **Step 1: Write the failing tests for the Mailer**

Create `healthflow/tests/auth/test_account_management.py`:

```python
"""Account management tests — Mailer + require_admin + change-password +
forgot-password + reset-password + admin force-unlock + promote_admin CLI.
"""
import logging
import os
from unittest.mock import MagicMock

import pytest


# ── Mailer ───────────────────────────────────────────────────────────────────


def test_console_mailer_logs_email_body(caplog):
    """ConsoleMailer.send writes the email body at INFO with to= and subject= markers."""
    from healthflow.email.mailer import ConsoleMailer

    mailer = ConsoleMailer()
    with caplog.at_level(logging.INFO, logger="healthflow.email.mailer"):
        mailer.send(
            to="alice@example.com",
            subject="Reset your password",
            text_body="Click here: https://test/reset?token=abc",
            html_body="<a href=\"https://test/reset?token=abc\">Click</a>",
        )

    messages = [r.getMessage() for r in caplog.records]
    assert any("to=alice@example.com" in m for m in messages)
    assert any("subject=Reset your password" in m for m in messages)
    assert any("https://test/reset?token=abc" in m for m in messages)


def test_get_mailer_returns_console_when_provider_is_console(monkeypatch):
    """EMAIL_PROVIDER=console → ConsoleMailer."""
    from healthflow.email import mailer as mailer_module
    from healthflow.email.mailer import ConsoleMailer

    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setattr(mailer_module, "_INSTANCE", None)

    assert isinstance(mailer_module.get_mailer(), ConsoleMailer)


def test_get_mailer_builds_ses_when_provider_is_ses(monkeypatch):
    """EMAIL_PROVIDER=ses + EMAIL_FROM_ADDRESS → SesMailer wrapping the boto3 client."""
    from healthflow.email import mailer as mailer_module
    from healthflow.email.mailer import SesMailer

    fake_client = MagicMock()
    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@healthflow.test")
    monkeypatch.setattr(mailer_module, "_INSTANCE", None)
    # Stub boto3.client so we don't need real AWS credentials.
    monkeypatch.setattr(
        "boto3.client", lambda service_name: fake_client if service_name == "ses" else None
    )

    instance = mailer_module.get_mailer()
    assert isinstance(instance, SesMailer)
    assert instance._client is fake_client
    assert instance._from == "noreply@healthflow.test"


def test_get_mailer_raises_when_ses_provider_missing_from_address(monkeypatch):
    """EMAIL_PROVIDER=ses without EMAIL_FROM_ADDRESS → RuntimeError."""
    from healthflow.email import mailer as mailer_module

    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.delenv("EMAIL_FROM_ADDRESS", raising=False)
    monkeypatch.setattr(mailer_module, "_INSTANCE", None)

    with pytest.raises(RuntimeError, match="EMAIL_FROM_ADDRESS is required"):
        mailer_module.get_mailer()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -v`
Expected: 4 errors, all `ModuleNotFoundError: No module named 'healthflow.email'`.

- [ ] **Step 3: Create the `healthflow/email/` package**

Create `healthflow/email/__init__.py`:

```python
from healthflow.email.mailer import Mailer, get_mailer

__all__ = ["Mailer", "get_mailer"]
```

- [ ] **Step 4: Create `healthflow/email/mailer.py`**

Create `healthflow/email/mailer.py`:

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
            raise RuntimeError(
                "EMAIL_FROM_ADDRESS is required when EMAIL_PROVIDER=ses"
            )
        return SesMailer(boto3.client("ses"), from_addr)
    raise RuntimeError(f"Unknown EMAIL_PROVIDER: {provider!r}")
```

- [ ] **Step 5: Add a Mailer-isolation autouse fixture to conftest**

Edit `healthflow/tests/conftest.py`. After the existing `isolate_server_log` fixture (end of file), append:

```python
@pytest.fixture(autouse=True)
def reset_mailer_singleton():
    """Each test starts with a fresh Mailer so EMAIL_PROVIDER overrides don't leak."""
    from healthflow.email import mailer as _mailer_module

    _mailer_module._INSTANCE = None
    yield
    _mailer_module._INSTANCE = None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -v`
Expected: 4 passed.

- [ ] **Step 7: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 4 new tests, all green.

- [ ] **Step 8: Commit**

```bash
git add healthflow/email/ healthflow/tests/auth/test_account_management.py healthflow/tests/conftest.py
git commit -m "Mailer subsystem: ConsoleMailer + SesMailer + lazy get_mailer()"
```

---

## Task 2: Email templates — render_password_reset

**Files:**
- Create: `healthflow/email/templates.py`
- Test: `healthflow/tests/auth/test_account_management.py`

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── Templates ────────────────────────────────────────────────────────────────


def test_render_password_reset_returns_subject_text_html():
    """render_password_reset returns (subject, text_body, html_body) with the reset URL."""
    from healthflow.email.templates import render_password_reset

    subject, text, html = render_password_reset(
        email="alice@example.com",
        reset_url="https://app.example.com/reset-password?token=abc.def.ghi",
    )

    assert subject == "Reset your HealthFlow password"
    assert "https://app.example.com/reset-password?token=abc.def.ghi" in text
    assert "https://app.example.com/reset-password?token=abc.def.ghi" in html
    assert "<a href=" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py::test_render_password_reset_returns_subject_text_html -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'healthflow.email.templates'`.

- [ ] **Step 3: Implement the templates module**

Create `healthflow/email/templates.py`:

```python
def render_password_reset(email: str, reset_url: str) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body) for a password-reset email."""
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

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py::test_render_password_reset_returns_subject_text_html -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add healthflow/email/templates.py healthflow/tests/auth/test_account_management.py
git commit -m "Password-reset email template (text + HTML)"
```

---

## Task 3: PasswordResetToken model + reset-token JWT helper

**Files:**
- Modify: `healthflow/database/models.py:185-208` (append after `RefreshToken`)
- Modify: `healthflow/auth/security.py:1-117` (append `create_password_reset_token`)
- Test: `healthflow/tests/auth/test_account_management.py`

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── PasswordResetToken model + JWT helper ────────────────────────────────────


@pytest.mark.asyncio
async def test_password_reset_token_model_persists(db_session):
    """A PasswordResetToken row inserts with broker_id, created_at, expires_at, used_at=None."""
    import uuid as _uuid
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from healthflow.database.models import PasswordResetToken

    now = datetime.now(timezone.utc)
    row = PasswordResetToken(
        id=_uuid.uuid4(),
        broker_id=_uuid.uuid4(),
        expires_at=now + timedelta(hours=1),
    )
    db_session.add(row)
    await db_session.flush()

    fetched = (await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.id == row.id)
    )).scalar_one()
    assert fetched.used_at is None
    assert fetched.broker_id == row.broker_id


def test_create_password_reset_token_embeds_jti_and_type():
    """create_password_reset_token returns a JWT with type='reset' and the given jti."""
    import uuid as _uuid
    from jose import jwt
    from healthflow.auth.security import (
        JWT_ALGORITHM,
        JWT_SECRET,
        create_password_reset_token,
    )

    broker_id = _uuid.uuid4()
    jti = _uuid.uuid4()
    token = create_password_reset_token(broker_id, jti)

    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == str(broker_id)
    assert payload["jti"] == str(jti)
    assert payload["type"] == "reset"
    assert "exp" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py::test_password_reset_token_model_persists healthflow/tests/auth/test_account_management.py::test_create_password_reset_token_embeds_jti_and_type -v`
Expected: both fail — `ImportError: cannot import name 'PasswordResetToken'` and `ImportError: cannot import name 'create_password_reset_token'`.

- [ ] **Step 3: Add the `PasswordResetToken` model**

Edit `healthflow/database/models.py`. After the `RefreshToken` class (around line 208), append:

```python


class PasswordResetToken(Base):
    """One row per password-reset request — single-use via `used_at`.

    System table — not tenant-scoped, not in _AUDITED_MODELS (reset bookkeeping
    is auth metadata, not patient-data access). The 60-second cooldown is
    enforced by querying this table; no Redis required.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 4: Add the `create_password_reset_token` helper**

Edit `healthflow/auth/security.py`. After the existing constants (around line 30), insert:

```python
PASSWORD_RESET_EXPIRE_MINUTES = 60
```

Then at the end of the file, append:

```python


def create_password_reset_token(broker_id: _uuid.UUID, jti: _uuid.UUID) -> str:
    """Create a single-use password-reset JWT bound to a PasswordResetToken row.

    The DB row is the authoritative state (single-use via `used_at`, expiry via
    `expires_at`); the JWT signature is the authentication mechanism. The router
    looks the row up by `jti` and asserts `used_at IS NULL` and not expired.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(broker_id),
        "type": "reset",
        "jti": str(jti),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)).timestamp()
        ),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py::test_password_reset_token_model_persists healthflow/tests/auth/test_account_management.py::test_create_password_reset_token_embeds_jti_and_type -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 2 new tests (7 from this PR so far), all green.

- [ ] **Step 7: Commit**

```bash
git add healthflow/database/models.py healthflow/auth/security.py healthflow/tests/auth/test_account_management.py
git commit -m "PasswordResetToken model + create_password_reset_token helper"
```

---

## Task 4: `require_admin` dependency

**Files:**
- Modify: `healthflow/auth/dependencies.py:1-80` (append `require_admin`)
- Test: `healthflow/tests/auth/test_account_management.py`

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── require_admin dependency ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_admin_returns_admin_broker():
    """When the current broker has role='admin', require_admin returns them."""
    from healthflow.auth.dependencies import require_admin
    from healthflow.database.models import Broker

    admin = Broker(email="a@x", hashed_password="h", full_name="A", role="admin")
    result = await require_admin(broker=admin)
    assert result is admin


@pytest.mark.asyncio
async def test_require_admin_raises_403_for_non_admin():
    """When the current broker has role='broker', require_admin raises HTTP 403."""
    from fastapi import HTTPException
    from healthflow.auth.dependencies import require_admin
    from healthflow.database.models import Broker

    broker = Broker(email="b@x", hashed_password="h", full_name="B", role="broker")
    with pytest.raises(HTTPException) as exc:
        await require_admin(broker=broker)
    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "require_admin" -v`
Expected: both FAIL with `ImportError: cannot import name 'require_admin'`.

- [ ] **Step 3: Implement `require_admin`**

Edit `healthflow/auth/dependencies.py`. At the end of the file (after `get_current_broker`), append:

```python


async def require_admin(broker: Broker = Depends(get_current_broker)) -> Broker:
    """Yield the current broker if they are an admin, else raise HTTP 403.

    Returns the broker so the route can use the admin's id for audit logging.
    No bearer → 401 propagates from get_current_broker. Wrong role → 403.
    """
    if broker.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return broker
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "require_admin" -v`
Expected: 2 passed.

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 2 new tests, all green.

- [ ] **Step 6: Commit**

```bash
git add healthflow/auth/dependencies.py healthflow/tests/auth/test_account_management.py
git commit -m "require_admin dependency: 403 when role != admin"
```

---

## Task 5: `POST /auth/change-password`

**Files:**
- Modify: `healthflow/models/schemas.py` (after `TokenResponse` at ~line 371)
- Modify: `healthflow/auth/router.py` (append endpoint)
- Test: `healthflow/tests/auth/test_account_management.py`

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── /auth/change-password ────────────────────────────────────────────────────


async def _register_and_login(client, email="user@example.com", password="Cromulent42!"):
    """Helper: register a broker and return (broker_id, access_token, refresh_token)."""
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert reg.status_code == 201
    broker_id = reg.json()["id"]
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    body = login.json()
    return broker_id, body["access_token"], body["refresh_token"]


@pytest.mark.asyncio
async def test_change_password_happy_path(client, db_session):
    """Valid current + valid new password → 204, password rehashed."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.auth.security import verify_password
    from healthflow.database.models import Broker

    broker_id, access, _ = await _register_and_login(client)

    resp = await client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": "Cromulent42!", "new_password": "Newpass99$word"},
    )
    assert resp.status_code == 204

    broker = (await db_session.execute(
        select(Broker).where(Broker.id == _uuid.UUID(broker_id))
    )).scalar_one()
    assert verify_password("Newpass99$word", broker.hashed_password)
    assert not verify_password("Cromulent42!", broker.hashed_password)


@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_401(client, db_session):
    """Wrong current_password → 401; password unchanged."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.auth.security import verify_password
    from healthflow.database.models import Broker

    broker_id, access, _ = await _register_and_login(client)

    resp = await client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": "WRONGPASSWORD!1", "new_password": "Newpass99$word"},
    )
    assert resp.status_code == 401
    assert "current password" in resp.json()["detail"].lower()

    broker = (await db_session.execute(
        select(Broker).where(Broker.id == _uuid.UUID(broker_id))
    )).scalar_one()
    assert verify_password("Cromulent42!", broker.hashed_password)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_new",
    [
        "short",                # too short
        "alllowercaseletters",  # no digit, no symbol
        "12345678!2345",        # no letter
        "password1234!",        # in common-password list (lowercased)
    ],
)
async def test_change_password_rejects_weak_new_password(client, bad_new):
    """Pydantic validator rejects policy violations → 422."""
    _, access, _ = await _register_and_login(client)

    resp = await client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": "Cromulent42!", "new_password": bad_new},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_requires_bearer(client):
    """No bearer → 401 from get_current_broker."""
    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "Cromulent42!", "new_password": "Newpass99$word"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_own_refresh_tokens(client, db_session):
    """All of THIS broker's active refresh-token rows get revoked."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import RefreshToken

    broker_id, access, _ = await _register_and_login(client)
    # The login above already created one RefreshToken row for this broker.
    pre = (await db_session.execute(
        select(RefreshToken).where(RefreshToken.broker_id == _uuid.UUID(broker_id))
    )).scalars().all()
    assert len(pre) >= 1
    assert all(r.revoked_at is None for r in pre)

    resp = await client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": "Cromulent42!", "new_password": "Newpass99$word"},
    )
    assert resp.status_code == 204

    # Expire cached rows so we re-read from the DB after the router committed.
    for r in pre:
        await db_session.refresh(r)
    assert all(r.revoked_at is not None for r in pre)


@pytest.mark.asyncio
async def test_change_password_does_not_revoke_other_brokers_tokens(client, db_session):
    """Other brokers' refresh tokens remain untouched (isolation regression)."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import RefreshToken

    # Broker A logs in and changes their password.
    _, access_a, _ = await _register_and_login(client, email="a@example.com")
    # Broker B logs in independently.
    broker_b_id, _, _ = await _register_and_login(client, email="b@example.com")
    b_rows_pre = (await db_session.execute(
        select(RefreshToken).where(RefreshToken.broker_id == _uuid.UUID(broker_b_id))
    )).scalars().all()
    assert all(r.revoked_at is None for r in b_rows_pre)

    resp = await client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {access_a}"},
        json={"current_password": "Cromulent42!", "new_password": "Newpass99$word"},
    )
    assert resp.status_code == 204

    for r in b_rows_pre:
        await db_session.refresh(r)
    assert all(r.revoked_at is None for r in b_rows_pre), \
        "Broker B's refresh tokens should NOT be revoked when Broker A changes password"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "change_password" -v`
Expected: all FAIL — `/auth/change-password` returns 404 Not Found (route doesn't exist).

- [ ] **Step 3: Add `ChangePasswordRequest` schema**

Edit `healthflow/models/schemas.py`. After `TokenResponse` (around line 371), insert:

```python


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password (re-auth)")
    new_password: str = Field(..., description="New password (must satisfy policy)")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        from healthflow.auth.security import validate_password
        validate_password(v)
        return v
```

- [ ] **Step 4: Implement `/auth/change-password`**

Edit `healthflow/auth/router.py`. Add the new schema import near the existing ones (top of file):

```python
from healthflow.models.schemas import (
    BrokerCreate,
    BrokerProfileUpdate,
    BrokerResponse,
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
)
```

Add the import for `update` from sqlalchemy and `RefreshToken` near the existing imports:

```python
from sqlalchemy import select, update as sa_update
```

(The existing file already imports `select`; replace that line with the combined import above.)

Then at the end of the router, after `update_profile`, append:

```python


@auth_router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Authenticated broker rotates their own password.

    Revokes all of the broker's active refresh tokens on success — a password
    change is a security event; other devices must re-login.
    """
    from healthflow.database.models import RefreshToken

    if not verify_password(payload.current_password, broker.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password",
        )

    broker.hashed_password = hash_password(payload.new_password)

    now = datetime.now(timezone.utc)
    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.broker_id == broker.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    await db.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "change_password" -v`
Expected: 6 passed.

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 6 new tests, all green.

- [ ] **Step 7: Commit**

```bash
git add healthflow/models/schemas.py healthflow/auth/router.py healthflow/tests/auth/test_account_management.py
git commit -m "POST /auth/change-password: re-auth + revoke own refresh tokens"
```

---

## Task 6: `POST /auth/forgot-password` + `POST /auth/reset-password`

**Files:**
- Modify: `healthflow/models/schemas.py` (append after `ChangePasswordRequest`)
- Modify: `healthflow/auth/router.py` (append endpoints)
- Test: `healthflow/tests/auth/test_account_management.py`

These ship together — splitting them leaves an unusable half-flow.

- [ ] **Step 1: Write the failing tests for `/auth/forgot-password`**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── /auth/forgot-password ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_known_email_creates_row_and_sends(client, db_session, caplog):
    """Known email → 200 generic message; one PasswordResetToken row; one mailer call."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import PasswordResetToken

    broker_id, _, _ = await _register_and_login(client, email="alice@example.com")

    with caplog.at_level(logging.INFO, logger="healthflow.email.mailer"):
        resp = await client.post(
            "/auth/forgot-password", json={"email": "alice@example.com"}
        )

    assert resp.status_code == 200
    assert "if an account exists" in resp.json()["message"].lower()

    rows = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == _uuid.UUID(broker_id)
        )
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].used_at is None

    log_messages = [r.getMessage() for r in caplog.records]
    assert any("to=alice@example.com" in m for m in log_messages)
    assert any("reset-password?token=" in m for m in log_messages)


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_same_response(client, db_session, caplog):
    """Unknown email → 200 same message; zero rows; zero mailer calls."""
    from sqlalchemy import select
    from healthflow.database.models import PasswordResetToken

    with caplog.at_level(logging.INFO, logger="healthflow.email.mailer"):
        resp = await client.post(
            "/auth/forgot-password", json={"email": "ghost@example.com"}
        )

    assert resp.status_code == 200
    assert "if an account exists" in resp.json()["message"].lower()

    rows = (await db_session.execute(select(PasswordResetToken))).scalars().all()
    assert rows == []
    assert not any("to=ghost@example.com" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_forgot_password_cooldown_swallows_second_request(client, db_session, caplog):
    """Two requests for the same email within 60s → one row, one mailer call."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import PasswordResetToken

    broker_id, _, _ = await _register_and_login(client, email="cool@example.com")

    with caplog.at_level(logging.INFO, logger="healthflow.email.mailer"):
        r1 = await client.post("/auth/forgot-password", json={"email": "cool@example.com"})
        r2 = await client.post("/auth/forgot-password", json={"email": "cool@example.com"})

    assert r1.status_code == 200
    assert r2.status_code == 200

    rows = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == _uuid.UUID(broker_id)
        )
    )).scalars().all()
    assert len(rows) == 1
    sent_count = sum(
        1 for r in caplog.records if "to=cool@example.com" in r.getMessage()
    )
    assert sent_count == 1


@pytest.mark.asyncio
async def test_forgot_password_after_cooldown_creates_new_row(client, db_session, caplog):
    """After the 60s window elapses, a second request creates a second row + sends."""
    import uuid as _uuid
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from healthflow.database.models import PasswordResetToken

    broker_id, _, _ = await _register_and_login(client, email="time@example.com")

    r1 = await client.post("/auth/forgot-password", json={"email": "time@example.com"})
    assert r1.status_code == 200

    # Backdate the existing row's created_at by 2 minutes to simulate the
    # cooldown window having elapsed. Far simpler than monkeypatching datetime.
    row = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == _uuid.UUID(broker_id)
        )
    )).scalar_one()
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    await db_session.commit()

    with caplog.at_level(logging.INFO, logger="healthflow.email.mailer"):
        r2 = await client.post("/auth/forgot-password", json={"email": "time@example.com"})
    assert r2.status_code == 200

    rows = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == _uuid.UUID(broker_id)
        )
    )).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_forgot_password_mailer_failure_still_returns_200(client, db_session, caplog, monkeypatch):
    """Mailer raises → 200 response unchanged; row still committed (cooldown survives);
    AuditLogger sees password_reset_send_failed."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import PasswordResetToken

    broker_id, _, _ = await _register_and_login(client, email="boom@example.com")

    from healthflow.email import mailer as mailer_module

    class FailingMailer:
        def send(self, *args, **kwargs):
            raise RuntimeError("SES is down")

    monkeypatch.setattr(mailer_module, "_INSTANCE", FailingMailer())

    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        resp = await client.post(
            "/auth/forgot-password", json={"email": "boom@example.com"}
        )

    assert resp.status_code == 200

    rows = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == _uuid.UUID(broker_id)
        )
    )).scalars().all()
    assert len(rows) == 1, "cooldown row must survive a mailer failure"

    assert any(
        "password_reset_send_failed" in r.getMessage() for r in caplog.records
    )
```

- [ ] **Step 2: Run forgot-password tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "forgot_password" -v`
Expected: 5 FAIL — `/auth/forgot-password` returns 404.

- [ ] **Step 3: Add `ForgotPasswordRequest`, `ForgotPasswordResponse`, `ResetPasswordRequest` schemas**

Edit `healthflow/models/schemas.py`. After the `ChangePasswordRequest` you added in Task 5, insert:

```python


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Email address to send a reset link to")


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Reset token from the email")
    new_password: str = Field(..., description="New password (must satisfy policy)")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        from healthflow.auth.security import validate_password
        validate_password(v)
        return v
```

- [ ] **Step 4: Implement `/auth/forgot-password` and `/auth/reset-password`**

Edit `healthflow/auth/router.py`. Extend the schema import block to include the three new schemas:

```python
from healthflow.models.schemas import (
    BrokerCreate,
    BrokerProfileUpdate,
    BrokerResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
```

Add `create_password_reset_token` to the security import block:

```python
from healthflow.auth.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
```

Then at the end of the router, after `change_password`, append:

```python


_FORGOT_PASSWORD_GENERIC_MESSAGE = (
    "If an account exists for that email, a reset link has been sent."
)
_FORGOT_PASSWORD_COOLDOWN_SECONDS = 60


def _frontend_base_url() -> str:
    value = os.getenv("FRONTEND_BASE_URL")
    if not value:
        raise RuntimeError(
            "FRONTEND_BASE_URL is required to build password-reset links"
        )
    return value.rstrip("/")


@auth_router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Send a password-reset email. Always returns the same generic 200 message
    regardless of whether the email exists, the cooldown is active, or the
    mailer fails. No enumeration; no error oracle.
    """
    from healthflow.database.models import PasswordResetToken
    from healthflow.email.mailer import get_mailer
    from healthflow.email.templates import render_password_reset
    from healthflow.logs.audit import AuditLogger
    import uuid as _uuid

    generic = ForgotPasswordResponse(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)

    result = await db.execute(select(Broker).where(Broker.email == payload.email))
    broker = result.scalar_one_or_none()
    if broker is None:
        return generic

    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(seconds=_FORGOT_PASSWORD_COOLDOWN_SECONDS)
    cooldown_q = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.broker_id == broker.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.created_at > cooldown_cutoff,
        ).limit(1)
    )
    if cooldown_q.scalar_one_or_none() is not None:
        return generic

    jti = _uuid.uuid4()
    expires_at = now + timedelta(minutes=60)
    row = PasswordResetToken(
        id=jti,
        broker_id=broker.id,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    # Commit the row BEFORE sending so the cooldown survives a mailer failure
    # and the audit log entry has a corresponding DB row to reference.
    await db.commit()

    token = create_password_reset_token(broker.id, jti)
    reset_url = f"{_frontend_base_url()}/reset-password?token={token}"
    subject, text_body, html_body = render_password_reset(broker.email, reset_url)

    try:
        get_mailer().send(broker.email, subject, text_body, html_body)
    except Exception as e:
        AuditLogger().log(
            "password_reset_send_failed",
            {"broker_id": str(broker.id), "error": repr(e)},
        )

    return generic
```

Make sure `os` is imported at the top of the router (`import os` near the top, if not already present).

- [ ] **Step 5: Run forgot-password tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "forgot_password" -v`
Expected: 5 passed.

- [ ] **Step 6: Write the failing tests for `/auth/reset-password`**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── /auth/reset-password ─────────────────────────────────────────────────────


async def _request_reset_token(client, db_session, email):
    """Helper: trigger forgot-password and return (broker_id, reset_jwt)."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.auth.security import create_password_reset_token
    from healthflow.database.models import Broker, PasswordResetToken

    resp = await client.post("/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    broker = (await db_session.execute(
        select(Broker).where(Broker.email == email)
    )).scalar_one()
    row = (await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.broker_id == broker.id)
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )).scalar_one()
    # Re-mint a JWT for the row's id — the forgot-password router doesn't
    # expose the JWT to tests; we reconstruct one with the row's jti.
    token = create_password_reset_token(broker.id, row.id)
    return str(broker.id), token


@pytest.mark.asyncio
async def test_reset_password_happy_path(client, db_session):
    """Valid token + valid new password → 204; password rehashed; row marked used."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.auth.security import verify_password
    from healthflow.database.models import Broker, PasswordResetToken

    await _register_and_login(client, email="reset@example.com")
    broker_id, token = await _request_reset_token(client, db_session, "reset@example.com")

    resp = await client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Brandnew99$word"},
    )
    assert resp.status_code == 204

    broker = (await db_session.execute(
        select(Broker).where(Broker.id == _uuid.UUID(broker_id))
    )).scalar_one()
    assert verify_password("Brandnew99$word", broker.hashed_password)

    row = (await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.broker_id == broker.id)
    )).scalar_one()
    assert row.used_at is not None


@pytest.mark.asyncio
async def test_reset_password_invalid_jwt_returns_401(client):
    """Garbage JWT → 401 generic message."""
    resp = await client.post(
        "/auth/reset-password",
        json={"token": "not-a-jwt", "new_password": "Brandnew99$word"},
    )
    assert resp.status_code == 401
    assert "reset token" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reset_password_wrong_type_claim_returns_401(client):
    """A valid JWT signed with the right secret but type='access' is rejected as 401."""
    from healthflow.auth.security import create_access_token
    import uuid as _uuid

    # An access token has type='access', not 'reset' — should be rejected.
    access = create_access_token({"sub": str(_uuid.uuid4()), "role": "broker"})
    resp = await client.post(
        "/auth/reset-password",
        json={"token": access, "new_password": "Brandnew99$word"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_401(client, db_session):
    """A token whose DB row's expires_at is in the past → 401."""
    import uuid as _uuid
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from healthflow.auth.security import create_password_reset_token
    from healthflow.database.models import Broker, PasswordResetToken

    await _register_and_login(client, email="expired@example.com")
    broker = (await db_session.execute(
        select(Broker).where(Broker.email == "expired@example.com")
    )).scalar_one()

    jti = _uuid.uuid4()
    row = PasswordResetToken(
        id=jti,
        broker_id=broker.id,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(row)
    await db_session.commit()

    token = create_password_reset_token(broker.id, jti)
    resp = await client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Brandnew99$word"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_replay_returns_401(client, db_session):
    """Using a token twice → second call returns 401; password stays the first rotation."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.auth.security import verify_password
    from healthflow.database.models import Broker

    await _register_and_login(client, email="replay@example.com")
    _, token = await _request_reset_token(client, db_session, "replay@example.com")

    r1 = await client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Firstreset9$word"},
    )
    assert r1.status_code == 204

    r2 = await client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Secondreset9$word"},
    )
    assert r2.status_code == 401

    broker = (await db_session.execute(
        select(Broker).where(Broker.email == "replay@example.com")
    )).scalar_one()
    assert verify_password("Firstreset9$word", broker.hashed_password)
    assert not verify_password("Secondreset9$word", broker.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_revokes_refresh_tokens(client, db_session):
    """Successful reset revokes all of the broker's active refresh tokens."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import Broker, RefreshToken

    await _register_and_login(client, email="rrev@example.com")
    broker_id, token = await _request_reset_token(client, db_session, "rrev@example.com")

    pre = (await db_session.execute(
        select(RefreshToken).where(RefreshToken.broker_id == _uuid.UUID(broker_id))
    )).scalars().all()
    assert len(pre) >= 1
    assert all(r.revoked_at is None for r in pre)

    resp = await client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Brandnew99$word"},
    )
    assert resp.status_code == 204

    for r in pre:
        await db_session.refresh(r)
    assert all(r.revoked_at is not None for r in pre)
```

- [ ] **Step 7: Run reset-password tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "reset_password" -v`
Expected: all 6 FAIL — `/auth/reset-password` returns 404.

- [ ] **Step 8: Implement `/auth/reset-password`**

Edit `healthflow/auth/router.py`. After the `forgot_password` route, append:

```python


@auth_router.post("/reset-password", status_code=204)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Consume a single-use reset token and rotate the password.

    Returns the same generic 401 for: invalid JWT, wrong type claim, unknown jti,
    used token, expired token, missing/inactive broker. Differentiating helps
    attackers more than legit users.
    """
    from healthflow.database.models import PasswordResetToken, RefreshToken
    import uuid as _uuid

    generic_401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired reset token",
    )

    try:
        claims = decode_token(payload.token)
    except ValueError:
        raise generic_401

    if claims.get("type") != "reset":
        raise generic_401

    broker_id_str = claims.get("sub")
    jti_str = claims.get("jti")
    if broker_id_str is None or jti_str is None:
        raise generic_401

    try:
        broker_id = _uuid.UUID(broker_id_str)
        jti = _uuid.UUID(jti_str)
    except ValueError:
        raise generic_401

    now = datetime.now(timezone.utc)

    row_result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.id == jti)
    )
    row = row_result.scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at < now:
        raise generic_401

    broker_result = await db.execute(select(Broker).where(Broker.id == broker_id))
    broker = broker_result.scalar_one_or_none()
    if broker is None or not broker.is_active:
        raise generic_401

    broker.hashed_password = hash_password(payload.new_password)
    row.used_at = now
    await db.execute(
        sa_update(RefreshToken)
        .where(
            RefreshToken.broker_id == broker.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.commit()
```

- [ ] **Step 9: Run reset-password tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "reset_password" -v`
Expected: 6 passed.

- [ ] **Step 10: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 11 new tests, all green.

- [ ] **Step 11: Commit**

```bash
git add healthflow/models/schemas.py healthflow/auth/router.py healthflow/tests/auth/test_account_management.py
git commit -m "POST /auth/forgot-password + /auth/reset-password with cooldown + token revocation"
```

---

## Task 7: `POST /admin/brokers/{broker_id}/unlock`

**Files:**
- Create: `healthflow/auth/admin_router.py`
- Modify: `healthflow/main.py:53` (mount the router)
- Test: `healthflow/tests/auth/test_account_management.py`

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── /admin/brokers/{id}/unlock ───────────────────────────────────────────────


async def _make_admin(client, db_session, email="admin@example.com"):
    """Helper: register a broker, promote them to admin, return access token."""
    import uuid as _uuid
    from sqlalchemy import select, update as sa_update
    from healthflow.database.models import Broker

    _, access, _ = await _register_and_login(client, email=email)
    await db_session.execute(
        sa_update(Broker).where(Broker.email == email).values(role="admin")
    )
    await db_session.commit()
    # Re-login so the new access token carries role="admin".
    login = await client.post(
        "/auth/login", json={"email": email, "password": "Cromulent42!"}
    )
    return login.json()["access_token"]


async def _create_locked_broker(client, db_session, email="locked@example.com"):
    """Helper: register a broker and set failed_login_count=5 + locked_until in the future."""
    import uuid as _uuid
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, update as sa_update
    from healthflow.database.models import Broker

    await _register_and_login(client, email=email)
    locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db_session.execute(
        sa_update(Broker).where(Broker.email == email).values(
            failed_login_count=5, locked_until=locked_until
        )
    )
    await db_session.commit()
    broker = (await db_session.execute(
        select(Broker).where(Broker.email == email)
    )).scalar_one()
    return str(broker.id)


@pytest.mark.asyncio
async def test_admin_unlock_clears_lock_state(client, db_session):
    """Admin unlocks a locked broker → 200; counter+lock cleared; locked user can log in."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import Broker

    admin_access = await _make_admin(client, db_session)
    target_id = await _create_locked_broker(client, db_session)

    resp = await client.post(
        f"/admin/brokers/{target_id}/unlock",
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"unlocked": True}

    target = (await db_session.execute(
        select(Broker).where(Broker.id == _uuid.UUID(target_id))
    )).scalar_one()
    assert target.failed_login_count == 0
    assert target.locked_until is None


@pytest.mark.asyncio
async def test_admin_unlock_rejects_non_admin(client, db_session):
    """Non-admin caller gets 403; target state unchanged."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import Broker

    _, broker_access, _ = await _register_and_login(client, email="plain@example.com")
    target_id = await _create_locked_broker(client, db_session)

    resp = await client.post(
        f"/admin/brokers/{target_id}/unlock",
        headers={"Authorization": f"Bearer {broker_access}"},
    )
    assert resp.status_code == 403

    target = (await db_session.execute(
        select(Broker).where(Broker.id == _uuid.UUID(target_id))
    )).scalar_one()
    assert target.failed_login_count == 5
    assert target.locked_until is not None


@pytest.mark.asyncio
async def test_admin_unlock_unknown_broker_returns_404(client, db_session):
    """Unknown broker_id → 404."""
    import uuid as _uuid

    admin_access = await _make_admin(client, db_session)
    ghost = _uuid.uuid4()

    resp = await client.post(
        f"/admin/brokers/{ghost}/unlock",
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_unlock_already_unlocked_is_idempotent(client, db_session):
    """Unlocking an already-unlocked broker → 200; same response shape."""
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import Broker

    admin_access = await _make_admin(client, db_session)
    _, _, _ = await _register_and_login(client, email="already-fine@example.com")
    target = (await db_session.execute(
        select(Broker).where(Broker.email == "already-fine@example.com")
    )).scalar_one()

    resp = await client.post(
        f"/admin/brokers/{target.id}/unlock",
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"unlocked": True}


@pytest.mark.asyncio
async def test_admin_unlock_no_bearer_returns_401(client):
    """No Authorization header → 401 from get_current_broker (not 403)."""
    import uuid as _uuid

    resp = await client.post(f"/admin/brokers/{_uuid.uuid4()}/unlock")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_unlock_emits_audit_event(client, db_session, caplog):
    """admin_force_unlock event includes both admin_id and target_broker_id."""
    import json
    import uuid as _uuid
    from sqlalchemy import select
    from healthflow.database.models import Broker

    admin_access = await _make_admin(client, db_session)
    admin = (await db_session.execute(
        select(Broker).where(Broker.email == "admin@example.com")
    )).scalar_one()
    target_id = await _create_locked_broker(client, db_session)

    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        resp = await client.post(
            f"/admin/brokers/{target_id}/unlock",
            headers={"Authorization": f"Bearer {admin_access}"},
        )
    assert resp.status_code == 200

    entries = [json.loads(r.getMessage()) for r in caplog.records if r.getMessage().startswith("{")]
    unlocks = [e for e in entries if e.get("event_type") == "admin_force_unlock"]
    assert len(unlocks) == 1
    details = unlocks[0]["details"]
    assert details["admin_id"] == str(admin.id)
    assert details["target_broker_id"] == target_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "admin_unlock" -v`
Expected: all 6 FAIL — `/admin/brokers/...` returns 404.

- [ ] **Step 3: Create `healthflow/auth/admin_router.py`**

Create `healthflow/auth/admin_router.py`:

```python
"""Admin-only endpoints. Mounted under prefix /admin and gated by require_admin."""
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import require_admin
from healthflow.database.config import get_db
from healthflow.database.models import Broker
from healthflow.logs.audit import AuditLogger

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/brokers/{broker_id}/unlock")
async def force_unlock_broker(
    broker_id: _uuid.UUID,
    admin: Broker = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin force-unlocks any broker's account.

    Clears failed_login_count and locked_until. Idempotent — unlocking an
    already-unlocked broker returns the same 200. The action is audit-logged
    with both ids (admin_force_unlock event).
    """
    target = (await db.execute(
        select(Broker).where(Broker.id == broker_id)
    )).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker not found",
        )

    target.failed_login_count = 0
    target.locked_until = None
    await db.commit()

    AuditLogger().log(
        "admin_force_unlock",
        {"admin_id": str(admin.id), "target_broker_id": str(broker_id)},
    )

    return {"unlocked": True}
```

- [ ] **Step 4: Mount the admin router in `main.py`**

Edit `healthflow/main.py`. After the existing `from healthflow.auth.router import auth_router` line, add:

```python
from healthflow.auth.admin_router import admin_router
```

After the existing `app.include_router(auth_router)` line, add:

```python
app.include_router(admin_router)
```

- [ ] **Step 5: Run admin-unlock tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "admin_unlock" -v`
Expected: 6 passed.

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 6 new tests, all green.

- [ ] **Step 7: Commit**

```bash
git add healthflow/auth/admin_router.py healthflow/main.py healthflow/tests/auth/test_account_management.py
git commit -m "POST /admin/brokers/{id}/unlock: clear lock state, audit-log the action"
```

---

## Task 8: `scripts/promote_admin.py`

**Files:**
- Create: `scripts/promote_admin.py`
- Test: `healthflow/tests/auth/test_account_management.py`

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/auth/test_account_management.py`:

```python
# ── scripts/promote_admin.py ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_admin_script_promotes_known_broker(client, db_session_factory, db_session, caplog):
    """_promote(email, factory) flips role to admin, returns 0, logs audit event."""
    import json
    from sqlalchemy import select

    from healthflow.database.models import Broker
    from scripts.promote_admin import _promote

    _, _, _ = await _register_and_login(client, email="promo@example.com")

    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        exit_code = await _promote("promo@example.com", db_session_factory)

    assert exit_code == 0

    broker = (await db_session.execute(
        select(Broker).where(Broker.email == "promo@example.com")
    )).scalar_one()
    assert broker.role == "admin"

    entries = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.getMessage().startswith("{")
    ]
    assert any(e.get("event_type") == "admin_promoted" for e in entries)


@pytest.mark.asyncio
async def test_promote_admin_script_unknown_email_returns_nonzero(db_session_factory, db_session):
    """Unknown email → returns 1; no DB writes."""
    from sqlalchemy import select
    from healthflow.database.models import Broker
    from scripts.promote_admin import _promote

    exit_code = await _promote("noone@example.com", db_session_factory)
    assert exit_code == 1

    # No admin promotion should have occurred.
    promoted = (await db_session.execute(
        select(Broker).where(Broker.role == "admin")
    )).scalars().all()
    assert promoted == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "promote_admin" -v`
Expected: both FAIL — `ModuleNotFoundError: No module named 'scripts.promote_admin'`.

- [ ] **Step 3: Create `scripts/promote_admin.py`**

Create `scripts/promote_admin.py`:

```python
"""Promote a broker to admin role.

Usage:
    python scripts/promote_admin.py --email someone@example.com

The first admin must be created this way (no API path creates admins).
The change is audit-logged via AuditLogger (event: admin_promoted).
"""
import asyncio
import sys

import click
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Broker
from healthflow.logs.audit import AuditLogger


async def _promote(email: str, factory: async_sessionmaker) -> int:
    """Returns exit code: 0 on success, 1 if no broker matches."""
    async with factory() as db:
        with system_context("admin promotion CLI"):
            broker = (await db.execute(
                select(Broker).where(Broker.email == email)
            )).scalar_one_or_none()
            if broker is None:
                click.echo(f"No broker found with email {email}.", err=True)
                return 1
            broker.role = "admin"
            await db.commit()
            AuditLogger().log(
                "admin_promoted",
                {"target_broker_id": str(broker.id), "via": "promote_admin.py"},
            )
            click.echo(f"Promoted {email} to admin.")
            return 0


@click.command()
@click.option("--email", required=True, help="Email of the broker to promote.")
def main(email: str) -> None:
    from healthflow.database.config import async_session_factory

    exit_code = asyncio.run(_promote(email, async_session_factory))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest healthflow/tests/auth/test_account_management.py -k "promote_admin" -v`
Expected: 2 passed.

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 2 new tests, all green. **Cumulative count: prior + 34** (the spec calls out 31 endpoint/dependency tests; the plan adds 3 thoroughness tests on the building blocks — template render, model persistence, no-bearer admin-unlock).

- [ ] **Step 6: Commit**

```bash
git add scripts/promote_admin.py healthflow/tests/auth/test_account_management.py
git commit -m "scripts/promote_admin.py: CLI to flip a broker to admin role"
```

---

## Task 9: Update `.env.example` + `healthflow-security` skill

**Files:**
- Modify: `.env.example`
- Modify: `.claude/skills/healthflow-security/SKILL.md`

- [ ] **Step 1: Document the new env vars in `.env.example`**

Edit `.env.example`. Append at the end:

```

# Email provider for transactional email (password reset).
# - console (default): logs the email body; no network I/O. Use for dev/tests.
# - ses: sends real email via AWS SES (BAA available under the standard AWS BAA;
#   set only in environments with a signed BAA when handling real PHI).
EMAIL_PROVIDER=console

# Required when EMAIL_PROVIDER=ses. The verified SES sender address.
# EMAIL_FROM_ADDRESS=noreply@your-domain.com

# Required for password-reset emails. The frontend's public origin; reset links
# look like ${FRONTEND_BASE_URL}/reset-password?token=...
FRONTEND_BASE_URL=http://localhost:5173
```

- [ ] **Step 2: Update the `healthflow-security` skill**

Edit `.claude/skills/healthflow-security/SKILL.md`. Add a new section after the existing auth-hardening section (or wherever the existing security rules live — adapt to the current structure). Add these rules:

```markdown
## Account management (PR #14)

- **Admin RBAC.** `Broker.role` is one of `"broker"` or `"admin"`. Use the
  `require_admin` dependency from `healthflow.auth.dependencies` on any route
  that must be admin-only — it returns 403 (not 401) when a non-admin is
  authenticated. Never check `broker.role == "admin"` inline in route bodies;
  always go through the dependency.

- **Admin bootstrap.** The only path to promote a broker to admin is
  `python scripts/promote_admin.py --email X`. There is no API endpoint that
  flips role; do not add one without a brainstorm round.

- **Password change → revoke refresh tokens.** Both `/auth/change-password` and
  `/auth/reset-password` MUST revoke every active `RefreshToken` row for the
  broker on success. A password change is a security event; other devices must
  re-login. Adding a code path that rotates a password without this revocation
  is a regression.

- **Forgot-password is generic, always.** `POST /auth/forgot-password` MUST
  return the same 200 response shape regardless of: email known/unknown,
  cooldown active/inactive, mailer succeeded/failed. Any branch that varies
  the HTTP response opens an enumeration or error oracle. Mailer failures go
  to `AuditLogger.log("password_reset_send_failed", ...)`, never to the client.

- **Reset-password is single-use.** The `PasswordResetToken.used_at` column
  is the authoritative single-use guard. Token replay (`used_at IS NOT NULL`),
  expiry (`expires_at < now`), and wrong-type-claim all return the same generic
  401. Differentiating helps attackers.

- **Per-email cooldown.** `/auth/forgot-password` MUST NOT issue a new reset
  token if there's an unexpired token created within the last 60 seconds for
  the same broker_id. This is the email-bomb defense; the cooldown row must
  be committed BEFORE the mailer call so a flaky mailer doesn't drop the
  cooldown.

- **Mailer selection.** `EMAIL_PROVIDER=console` is the default; `ses` enables
  AWS SES (BAA-eligible under the standard AWS BAA). Production deployments
  handling real PHI MUST set `EMAIL_PROVIDER=ses` and have a signed AWS BAA.
  Other providers (SendGrid, Resend, Postmark, Paubox) are not wired; adding
  one requires brainstorm + spec.
```

- [ ] **Step 3: Run the full suite one more time as a sanity check**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 34 new tests, all green.

- [ ] **Step 4: Commit**

```bash
git add .env.example .claude/skills/healthflow-security/SKILL.md
git commit -m "Document new env vars + healthflow-security rules for account management"
```

---

## Task 10: Final verification + push + PR

**Files:** none (operations only).

- [ ] **Step 1: Run lint**

Run: `make lint`
Expected: zero ruff findings.

- [ ] **Step 2: Run dead-code scan**

Run: `make dead-code`
Expected: zero findings.

- [ ] **Step 3: Run the full suite one more time**

Run: `make test 2>&1 | tail -3`
Expected: previous count + 34 new tests, all green. Record the new total.

- [ ] **Step 4: Push the branch**

Run: `git push -u origin account-management`
Expected: branch pushed.

- [ ] **Step 5: Open the PR**

Run:

```bash
gh pr create --title "Account management: RBAC + change/forgot/reset password + admin unlock" --body "$(cat <<'EOF'
## Summary

- Adds `POST /auth/change-password`, `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /admin/brokers/{id}/unlock`.
- New `healthflow/email/` package: `Mailer` protocol, `ConsoleMailer` (dev default), `SesMailer` (production target via `EMAIL_PROVIDER=ses`).
- New `require_admin` dependency; new `PasswordResetToken` system table.
- New `scripts/promote_admin.py` — the only path to create the first admin.
- 34 new tests; full suite green.
- HIPAA: AWS SES is BAA-eligible under the standard AWS BAA; non-PHI dev/test paths use `ConsoleMailer` with no network I/O.

## Spec
`docs/superpowers/specs/2026-05-18-account-management-design.md`

## Test plan
- [ ] CI green (full pytest suite).
- [ ] Manual: register → forgot-password → check server log for the reset URL → reset-password → log in with new password.
- [ ] Manual: register a second broker → `python scripts/promote_admin.py --email <first>` → log in as first broker → POST /admin/brokers/{second}/unlock with the second broker's id.

## Deploy notes
- `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `FRONTEND_BASE_URL` added to `.env.example`. Production: set `EMAIL_PROVIDER=ses` and `EMAIL_FROM_ADDRESS=<verified address>`.
- New table `password_reset_tokens` is picked up automatically by `Base.metadata.create_all` on next startup. No ALTER TABLE needed.

EOF
)"
```

Expected: PR URL is printed; CI begins.

- [ ] **Step 6: Wait for CI to pass and merge**

Watch the PR. When green, merge to main.

---

## Notes for the implementer

- **Order matters.** Tasks 1-3 are pure infrastructure; they don't change observable behavior. Task 4 adds the dependency; Tasks 5-8 add the endpoints. Don't reorder.
- **Time-travel in tests.** The codebase doesn't use `freezegun`. The forgot-password cooldown test (`test_forgot_password_after_cooldown_creates_new_row`) backdates the existing row's `created_at` rather than mocking `datetime.now` — far simpler. Use the same pattern if you ever need time-travel here.
- **Tenant context.** None of the new endpoints touch tenant-scoped tables (`Client`, `ActionHistory`, `Feedback`). They only touch `Broker`, `RefreshToken`, and `PasswordResetToken` — all system tables. No `system_context` needed in routers; only the `promote_admin.py` script uses it (because it runs outside a request).
- **Pydantic validators may surface as 422.** That's automatic. Don't add `try/except ValueError` in routers for password validation; let Pydantic handle it.
- **`make dead-code` ignores list.** The existing `--ignore-names` list in the Makefile covers all framework-callback patterns you'll add here. If you see a new false positive, document it; don't expand the list without a comment.
