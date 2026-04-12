import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker
from healthflow.auth.security import hash_password, create_access_token


async def _create_broker_and_token(db: AsyncSession):
    """Helper: create a broker and return (broker, access_token)."""
    broker_id = uuid.uuid4()
    broker = Broker(
        id=broker_id,
        email=f"route-{broker_id.hex[:6]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="Route Tester",
    )
    db.add(broker)
    await db.commit()

    token = create_access_token({"sub": str(broker_id), "type": "access"})
    return broker, token


@pytest.mark.anyio
async def test_submit_feedback(client: AsyncClient, db_session: AsyncSession):
    broker, token = await _create_broker_and_token(db_session)
    resp = await client.post(
        "/feedback",
        json={
            "output_id": "sess-100",
            "agent_type": "compare",
            "accuracy": 5,
            "clarity": 4,
            "helpfulness": 4,
            "comment": "Nice work",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["accuracy"] == 5
    assert data["agent_type"] == "compare"
    assert data["broker_id"] == str(broker.id)


@pytest.mark.anyio
async def test_submit_feedback_invalid_rating(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    resp = await client.post(
        "/feedback",
        json={
            "output_id": "sess-100",
            "agent_type": "compare",
            "accuracy": 0,
            "clarity": 4,
            "helpfulness": 4,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_list_feedback(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    # Submit two
    for i in range(2):
        await client.post(
            "/feedback",
            json={
                "output_id": f"sess-{i}",
                "agent_type": "compare",
                "accuracy": 4,
                "clarity": 4,
                "helpfulness": 4,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_list_feedback_filter(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    await client.post(
        "/feedback",
        json={"output_id": "s1", "agent_type": "compare", "accuracy": 4, "clarity": 4, "helpfulness": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/feedback",
        json={"output_id": "s2", "agent_type": "translate", "accuracy": 3, "clarity": 3, "helpfulness": 3},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/feedback?agent_type=compare",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["agent_type"] == "compare"


@pytest.mark.anyio
async def test_get_analytics(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    await client.post(
        "/feedback",
        json={"output_id": "a1", "agent_type": "compare", "accuracy": 5, "clarity": 5, "helpfulness": 5},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/feedback/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_feedback"] == 1
    assert len(data["agents"]) == 1


@pytest.mark.anyio
async def test_reward_score(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    await client.post(
        "/feedback",
        json={"output_id": "r1", "agent_type": "compare", "accuracy": 5, "clarity": 5, "helpfulness": 5},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/feedback/reward-score",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert "overall_avg" in data


@pytest.mark.anyio
async def test_weekly_report(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)

    resp = await client.get(
        "/feedback/weekly-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "worst_agent" in data
    assert "best_agent" in data


@pytest.mark.anyio
async def test_feedback_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/feedback",
        json={"output_id": "x", "agent_type": "compare", "accuracy": 3, "clarity": 3, "helpfulness": 3},
    )
    assert resp.status_code == 401

    resp = await client.get("/feedback")
    assert resp.status_code == 401

    resp = await client.get("/feedback/analytics")
    assert resp.status_code == 401
