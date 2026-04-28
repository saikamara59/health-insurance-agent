"""Broker A must not see/modify/delete broker B's data.

This is the load-bearing property for per-worker e2e isolation. If any route
returns or accepts cross-broker access, it's a real production bug and must
be fixed before parallel e2e workers can be trusted.
"""
import pytest
from httpx import AsyncClient

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


async def _make_broker(session, email: str) -> Broker:
    broker = Broker(
        email=email,
        hashed_password=hash_password("TestWorker123!"),
        full_name=email,
    )
    session.add(broker)
    await session.flush()
    return broker


async def _login(client: AsyncClient, email: str, password: str = "TestWorker123!") -> str:
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.mark.anyio
async def test_broker_cannot_read_other_brokers_clients(client, db_session):
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Only Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.get(
        "/clients", headers={"Authorization": f"Bearer {b_token}"}
    )
    assert res.status_code == 200
    names = [c["full_name"] for c in res.json()]
    assert "A's Only Client" not in names
    assert names == [], f"Broker B should have zero clients but got: {names}"


@pytest.mark.anyio
async def test_broker_cannot_read_other_brokers_client_by_id(client, db_session):
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Only Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.get(
        f"/clients/{a_client.id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    # Either 404 (broker B can't see A's client) or 403 (forbidden) is acceptable.
    # 200 means cross-broker leak — fix the route.
    assert res.status_code in (403, 404), f"Cross-broker read leak: {res.status_code} {res.text}"


@pytest.mark.anyio
async def test_broker_cannot_delete_other_brokers_client(client, db_session):
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Only Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.delete(
        f"/clients/{a_client.id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert res.status_code in (403, 404), f"Cross-broker delete leak: {res.status_code} {res.text}"

    # And A's client should still exist.
    a_token = await _login(client, "iso-a@healthflow.test")
    res = await client.get(
        f"/clients/{a_client.id}",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert res.status_code == 200
