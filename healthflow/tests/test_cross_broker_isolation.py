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
    _broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
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
    _broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
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
    _broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
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


@pytest.mark.anyio
async def test_broker_cannot_create_history_for_other_brokers_client(client, db_session):
    """POST /history must reject a client_id that belongs to another broker."""
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    _broker_b = await _make_broker(db_session, "iso-b@healthflow.test")
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
    res = await client.post(
        "/history",
        json={
            "client_id": str(a_client.id),
            "action_type": "compare",
            "request_data": {},
            "response_summary": {},
        },
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert res.status_code in (403, 404), (
        f"Cross-broker history create leak: {res.status_code} {res.text}"
    )


@pytest.mark.anyio
async def test_list_history_client_names_scoped_to_broker(client, db_session):
    """GET /history client_name resolution must not leak names across brokers."""
    broker_a = await _make_broker(db_session, "iso-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-b@healthflow.test")

    a_client = Client(
        broker_id=broker_a.id,
        full_name="A's Secret Client",
        zip_code="10001",
        age=40,
        income_level="medium",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    b_client = Client(
        broker_id=broker_b.id,
        full_name="B's Own Client",
        zip_code="10001",
        age=35,
        income_level="low",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(a_client)
    db_session.add(b_client)
    await db_session.flush()

    from healthflow.database.models import ActionHistory
    import uuid as _uuid

    b_action = ActionHistory(
        id=_uuid.uuid4(),
        broker_id=broker_b.id,
        client_id=b_client.id,
        action_type="compare",
        request_data={},
        response_summary={},
    )
    db_session.add(b_action)
    await db_session.commit()

    b_token = await _login(client, "iso-b@healthflow.test")
    res = await client.get("/history", headers={"Authorization": f"Bearer {b_token}"})
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 1
    assert entries[0]["client_name"] == "B's Own Client"
    # A's client name must never appear in B's history response.
    all_names = [e.get("client_name") for e in entries]
    assert "A's Secret Client" not in all_names
