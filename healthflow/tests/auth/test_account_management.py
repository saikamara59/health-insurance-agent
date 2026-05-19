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
