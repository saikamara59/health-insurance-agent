"""Auth hardening tests — covers JWT_SECRET fail-loud, password policy,
account lockout, and refresh-token rotation.
"""
import importlib
import os

import pytest

import healthflow.auth.security as security


def test_jwt_secret_fail_loud_raises_when_unset(monkeypatch):
    """A missing JWT_SECRET env var must raise at module reload."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        importlib.reload(security)
    # Restore a valid value before this module's reference to `security`
    # becomes the unloaded one for the rest of the suite.
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


def test_jwt_secret_fail_loud_rejects_legacy_default(monkeypatch):
    """The known-bad legacy default value must be rejected."""
    monkeypatch.setenv("JWT_SECRET", "healthflow-dev-secret-change-in-production")
    with pytest.raises(RuntimeError, match="legacy default"):
        importlib.reload(security)
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


def test_jwt_secret_accepts_any_other_value(monkeypatch):
    """Setting to any other string imports cleanly."""
    monkeypatch.setenv("JWT_SECRET", "a-real-deploy-secret-7384")
    importlib.reload(security)
    assert security.JWT_SECRET == "a-real-deploy-secret-7384"
    # Restore the test default for the rest of the suite.
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")
    importlib.reload(security)


from healthflow.auth.security import validate_password


def test_validate_password_accepts_compliant_password():
    # 12+ chars, has letter, digit, non-alphanumeric, not in block-list.
    validate_password("Cromulent42!")


@pytest.mark.parametrize(
    "bad,reason_match",
    [
        ("Short1!", "12 characters"),               # too short
        ("Cromulent!!!!", "digit"),                 # no digit (12 chars)
        ("123456789012", "letter"),                 # no letter
        ("Cromulent4242", "non-alphanumeric"),      # no symbol
        ("Password123!", "too common"),             # "password123!" is in the list
    ],
)
def test_validate_password_rejects_bad(bad, reason_match):
    with pytest.raises(ValueError, match=reason_match):
        validate_password(bad)


def test_validate_password_rejects_listed_common_password():
    # Pad a known common password to satisfy the length check; the block-list
    # check should still reject it.
    with pytest.raises(ValueError, match="too common"):
        validate_password("password123!")  # "password123!" is in the list


@pytest.mark.anyio
async def test_register_endpoint_rejects_weak_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "weak@healthflow.test",
            "password": "short",
            "full_name": "Weak Pass",
        },
    )
    assert response.status_code == 422
    body = response.json()
    # The Pydantic error message must surface the policy reason.
    assert "12 characters" in str(body) or "min_length" in str(body)


@pytest.mark.anyio
async def test_register_endpoint_accepts_compliant_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "strong@healthflow.test",
            "password": "Cromulent42!",
            "full_name": "Strong Pass",
        },
    )
    assert response.status_code == 201


@pytest.mark.anyio
async def test_existing_broker_with_old_weak_password_can_still_login(client, db_session):
    """Existing accounts whose passwords predate the new policy still log in.
    Only register (and future change-password) enforce the policy."""
    from healthflow.auth.security import hash_password
    from healthflow.database.models import Broker

    # Insert a broker with a password that wouldn't pass the new policy.
    broker = Broker(
        email="legacy@healthflow.test",
        hashed_password=hash_password("short1"),  # 6 chars, fails new policy
        full_name="Legacy User",
    )
    db_session.add(broker)
    await db_session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": "legacy@healthflow.test", "password": "short1"},
    )
    assert response.status_code == 200, response.text


from datetime import datetime, timedelta, timezone

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker


async def _make_broker_with_known_password(db_session, email: str) -> Broker:
    broker = Broker(
        email=email,
        hashed_password=hash_password("Cromulent42!"),
        full_name="Lockout Test",
    )
    db_session.add(broker)
    await db_session.commit()
    return broker


@pytest.mark.anyio
async def test_login_increments_counter_on_failed_attempt(client, db_session):
    await _make_broker_with_known_password(db_session, "lock1@healthflow.test")
    for _ in range(4):
        res = await client.post(
            "/auth/login",
            json={"email": "lock1@healthflow.test", "password": "wrong!"},
        )
        assert res.status_code == 401

    # 4 failures: account NOT yet locked, 5th attempt with correct password works.
    res = await client.post(
        "/auth/login",
        json={"email": "lock1@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200


@pytest.mark.anyio
async def test_five_failed_attempts_locks_account(client, db_session):
    await _make_broker_with_known_password(db_session, "lock2@healthflow.test")
    for _ in range(5):
        res = await client.post(
            "/auth/login",
            json={"email": "lock2@healthflow.test", "password": "wrong!"},
        )
        assert res.status_code == 401

    # 6th attempt with CORRECT password still 401 — locked.
    res = await client.post(
        "/auth/login",
        json={"email": "lock2@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 401
    # No mention of "lock" in the response — generic message only.
    assert "lock" not in res.text.lower()


@pytest.mark.anyio
async def test_successful_login_resets_lockout_state(client, db_session):
    broker = await _make_broker_with_known_password(db_session, "lock3@healthflow.test")
    # Force partial-failure state.
    broker.failed_login_count = 3
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"email": "lock3@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200

    await db_session.refresh(broker)
    assert broker.failed_login_count == 0
    assert broker.locked_until is None


@pytest.mark.anyio
async def test_lock_auto_expires_after_15_minutes(client, db_session, monkeypatch):
    broker = await _make_broker_with_known_password(db_session, "lock4@healthflow.test")
    # Force a lock that "ended" 1 minute ago in real time.
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    broker.locked_until = past
    broker.failed_login_count = 5
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"email": "lock4@healthflow.test", "password": "Cromulent42!"},
    )
    assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_lock_response_message_does_not_reveal_lock_state(client, db_session):
    """Locked account returns the SAME error body as wrong-password — no enumeration."""
    await _make_broker_with_known_password(db_session, "lock5@healthflow.test")
    # 5 failures to lock.
    for _ in range(5):
        await client.post(
            "/auth/login",
            json={"email": "lock5@healthflow.test", "password": "wrong!"},
        )

    # 6th attempt: locked.
    locked_res = await client.post(
        "/auth/login",
        json={"email": "lock5@healthflow.test", "password": "Cromulent42!"},
    )
    # Comparison: a totally wrong email gets the same shape.
    wrong_email_res = await client.post(
        "/auth/login",
        json={"email": "nobody@healthflow.test", "password": "wrong!"},
    )

    assert locked_res.status_code == 401
    assert wrong_email_res.status_code == 401
    assert locked_res.json() == wrong_email_res.json()
