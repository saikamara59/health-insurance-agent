"""Composite-write protection: broker A cannot create rows referencing broker B's data."""
import pytest

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


async def _make_broker(session, email: str) -> Broker:
    broker = Broker(
        email=email,
        hashed_password=hash_password("WriteTest123!"),
        full_name=email,
    )
    session.add(broker)
    await session.flush()
    return broker


async def _login(client, email: str, password: str = "WriteTest123!") -> str:
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.mark.anyio
async def test_broker_cannot_create_history_for_other_brokers_client(client, db_session):
    """POST /history with another broker's client_id must return 404, not write the row."""
    broker_a = await _make_broker(db_session, "wa@healthflow.test")
    _broker_b = await _make_broker(db_session, "wb@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id, full_name="A's Client",
        zip_code="10001", age=40, income_level="medium",
        doctors=[], prescriptions=[], procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "wb@healthflow.test")
    res = await client.post(
        "/history",
        headers={"Authorization": f"Bearer {b_token}"},
        json={
            "client_id": str(a_client.id),
            "action_type": "compare_plans",
            "request_data": {},
            "response_summary": {},
        },
    )
    assert res.status_code == 404, f"Cross-broker write leak: {res.status_code} {res.text}"


@pytest.mark.anyio
async def test_analytics_endpoint_returns_only_current_brokers_aggregates(client, db_session):
    """GET /feedback/analytics must aggregate only the requesting broker's feedback."""
    _broker_a = await _make_broker(db_session, "ana-a@healthflow.test")
    _broker_b = await _make_broker(db_session, "ana-b@healthflow.test")
    await db_session.commit()

    a_token = await _login(client, "ana-a@healthflow.test")
    b_token = await _login(client, "ana-b@healthflow.test")

    # A submits 2 feedback rows; B submits 5 with different agent_type.
    for _ in range(2):
        res = await client.post(
            "/feedback",
            headers={"Authorization": f"Bearer {a_token}"},
            json={"output_id": "o1", "agent_type": "compare",
                  "accuracy": 5, "clarity": 5, "helpfulness": 5, "comment": ""},
        )
        assert res.status_code == 201, res.text
    for _ in range(5):
        res = await client.post(
            "/feedback",
            headers={"Authorization": f"Bearer {b_token}"},
            json={"output_id": "o2", "agent_type": "translate",
                  "accuracy": 3, "clarity": 3, "helpfulness": 3, "comment": ""},
        )
        assert res.status_code == 201, res.text

    # A's analytics should see only "compare" with total_feedback=2.
    res = await client.get(
        "/feedback/analytics",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_feedback"] == 2
    assert {a["agent_type"] for a in body["agents"]} == {"compare"}

    # B's analytics should see only "translate" with total_feedback=5.
    res = await client.get(
        "/feedback/analytics",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_feedback"] == 5
    assert {a["agent_type"] for a in body["agents"]} == {"translate"}
