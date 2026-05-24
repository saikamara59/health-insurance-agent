"""Tests for the admin-only listing endpoints:
   GET /admin/brokers       — team table data
   GET /admin/audit/recent  — recent agent invocations
"""
import pytest
import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import update as sa_update

from healthflow.database.models import AgentInvocationLog, Broker


async def _register_and_login(client, email="user@example.com", password="Cromulent42!"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert reg.status_code == 201, reg.text
    broker_id = reg.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return broker_id, login.json()["access_token"], login.json().get("refresh_token")


async def _make_admin(client, db_session, email="admin@example.com"):
    _, access, _ = await _register_and_login(client, email=email)
    await db_session.execute(
        sa_update(Broker).where(Broker.email == email).values(role="admin")
    )
    await db_session.commit()
    login = await client.post(
        "/auth/login", json={"email": email, "password": "Cromulent42!"}
    )
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_brokers_lists_all_with_counts(client, db_session):
    """Admin lists every broker, including admin itself and brokers with 0 clients."""
    admin_token = await _make_admin(client, db_session)
    await _register_and_login(client, email="b1@example.com")
    await _register_and_login(client, email="b2@example.com")

    resp = await client.get(
        "/admin/brokers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    emails = {r["email"] for r in rows}
    assert {"admin@example.com", "b1@example.com", "b2@example.com"} <= emails
    for r in rows:
        assert "client_count" in r
        assert r["client_count"] == 0
        assert "role" in r and "locked_until" in r


@pytest.mark.asyncio
async def test_admin_brokers_rejects_non_admin(client):
    """A plain broker hitting /admin/brokers gets 403."""
    _, access, _ = await _register_and_login(client, email="plain@example.com")
    resp = await client.get(
        "/admin/brokers",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_brokers_no_auth_returns_401(client):
    """No bearer token → 401 from get_current_broker, not 403."""
    resp = await client.get("/admin/brokers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_audit_recent_returns_invocations(client, db_session):
    """Admin gets the most-recent agent invocations enriched with broker email."""
    admin_token = await _make_admin(client, db_session)
    broker_id, _, _ = await _register_and_login(client, email="logger@example.com")

    db_session.add(AgentInvocationLog(
        id=_uuid.uuid4(),
        broker_id=_uuid.UUID(broker_id),
        endpoint="/compare",
        agent="plan_comparison",
        event_type="compare.complete",
        model_used="claude-sonnet-4",
        duration_ms=1234,
        details={},
        created_at=datetime.now(timezone.utc),
    ))
    await db_session.commit()

    resp = await client.get(
        "/admin/audit/recent?limit=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    seeded = next((r for r in rows if r["agent"] == "plan_comparison"), None)
    assert seeded is not None
    assert seeded["broker_email"] == "logger@example.com"
    assert seeded["duration_ms"] == 1234


@pytest.mark.asyncio
async def test_admin_audit_recent_rejects_non_admin(client):
    """A plain broker hitting /admin/audit/recent gets 403."""
    _, access, _ = await _register_and_login(client, email="curious@example.com")
    resp = await client.get(
        "/admin/audit/recent",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_audit_recent_limit_validated(client, db_session):
    """limit must be 1..100; out-of-range returns 422."""
    admin_token = await _make_admin(client, db_session)
    resp = await client.get(
        "/admin/audit/recent?limit=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    resp = await client.get(
        "/admin/audit/recent?limit=101",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
