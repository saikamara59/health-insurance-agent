"""Account management tests — Mailer + require_admin + change-password +
forgot-password + reset-password + admin force-unlock + promote_admin CLI.
"""
import logging
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
        "password123!",         # in common-password list (lowercased)
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
