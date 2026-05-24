"""End-to-end tests for POST /forensics/replay.

Uses the `client` fixture from the shared conftest. Auth is admin-only.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update as sa_update

from healthflow.database.models import Broker
from healthflow.forensics.tests.fixtures import make_invocation


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _override_forensics_session_factory(db_session_factory, monkeypatch):
    """Make /forensics/replay use the in-memory test factory, same DB as the
    `client` fixture so seeded rows are visible."""
    from healthflow.forensics import routes as forensics_routes
    monkeypatch.setattr(forensics_routes, "_get_session_factory", lambda: db_session_factory)


async def _make_admin(client, db_session, email="admin@example.com", password="Cromulent42!"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Admin"},
    )
    assert reg.status_code == 201
    await db_session.execute(
        sa_update(Broker).where(Broker.email == email).values(role="admin")
    )
    await db_session.commit()
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    body = login.json()
    broker = (await db_session.execute(select(Broker).where(Broker.email == email))).scalar_one()
    return body["access_token"], broker.id


@pytest.mark.asyncio
async def test_admin_case_replay_returns_200_with_timeline(client, db_session):
    access, broker_id = await _make_admin(client, db_session)
    case = uuid.uuid4()
    db_session.add(make_invocation(case_id=case, broker_id=broker_id, agent="comparison", timestamp=_T0))
    await db_session.commit()

    resp = await client.post(
        "/forensics/replay",
        headers={"Authorization": f"Bearer {access}"},
        json={"mode": "case", "case_id": str(case)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == str(case)
    assert len(body["invocations"]) == 1


@pytest.mark.asyncio
async def test_non_admin_gets_403(client):
    reg = await client.post(
        "/auth/register",
        json={"email": "broker@example.com", "password": "Cromulent42!", "full_name": "Broker"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/auth/login", json={"email": "broker@example.com", "password": "Cromulent42!"}
    )
    access = login.json()["access_token"]

    resp = await client.post(
        "/forensics/replay",
        headers={"Authorization": f"Bearer {access}"},
        json={"mode": "case", "case_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_gets_401(client):
    resp = await client.post(
        "/forensics/replay",
        json={"mode": "case", "case_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_case_returns_empty_not_404(client, db_session):
    """A case belonging to a different broker queried as the admin →
    200 with empty invocations (no info leak)."""
    access, admin_id = await _make_admin(client, db_session)
    case = uuid.uuid4()
    other_broker = uuid.uuid4()
    db_session.add(make_invocation(case_id=case, broker_id=other_broker, timestamp=_T0))
    await db_session.commit()

    resp = await client.post(
        "/forensics/replay",
        headers={"Authorization": f"Bearer {access}"},
        json={"mode": "case", "case_id": str(case)},
    )
    assert resp.status_code == 200
    assert resp.json()["invocations"] == []
