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
