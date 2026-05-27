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
    # Production /auth/register creates accounts as pending. Tests want a
    # ready-to-use account, so flip is_active=True via the test-only router.
    act = await client.post("/__test/activate-broker", json={"email": email})
    assert act.status_code == 200, act.text
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


# ── approve / deactivate ─────────────────────────────────────────────────────


async def _register_pending(client, email: str) -> str:
    """Register a broker WITHOUT activating — returns the new broker_id."""
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "Cromulent42!", "full_name": "Pending User"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_pending_broker_cannot_log_in(client):
    """A registered-but-not-approved account hits 403 with the pending msg."""
    await _register_pending(client, "pending-login@example.com")
    resp = await client.post(
        "/auth/login",
        json={"email": "pending-login@example.com", "password": "Cromulent42!"},
    )
    assert resp.status_code == 403
    assert "pending" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_approve_makes_broker_able_to_log_in(client, db_session):
    """Admin approves → broker can now log in."""
    admin_token = await _make_admin(client, db_session)
    new_id = await _register_pending(client, "to-approve@example.com")

    approve = await client.post(
        f"/admin/brokers/{new_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200
    assert approve.json()["approved"] is True

    login = await client.post(
        "/auth/login",
        json={"email": "to-approve@example.com", "password": "Cromulent42!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_admin_approve_rejects_non_admin(client, db_session):
    """Plain broker cannot approve another broker — 403."""
    _, broker_token, _ = await _register_and_login(client, email="not-admin@example.com")
    target_id = await _register_pending(client, "still-pending@example.com")
    resp = await client.post(
        f"/admin/brokers/{target_id}/approve",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_approve_unknown_broker_returns_404(client, db_session):
    admin_token = await _make_admin(client, db_session)
    resp = await client.post(
        f"/admin/brokers/{_uuid.uuid4()}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_deactivate_blocks_login(client, db_session):
    """Admin deactivates a previously-active broker → next login 403."""
    admin_token = await _make_admin(client, db_session)
    broker_id, _, _ = await _register_and_login(client, email="will-be-revoked@example.com")

    resp = await client.post(
        f"/admin/brokers/{broker_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    login = await client.post(
        "/auth/login",
        json={"email": "will-be-revoked@example.com", "password": "Cromulent42!"},
    )
    assert login.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client, db_session):
    """Foot-gun guard — admin trying to deactivate their own account gets 403."""
    from sqlalchemy import select
    from healthflow.database.models import Broker

    admin_token = await _make_admin(client, db_session)
    admin = (await db_session.execute(
        select(Broker).where(Broker.email == "admin@example.com")
    )).scalar_one()
    resp = await client.post(
        f"/admin/brokers/{admin.id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
