import pytest
import uuid
from healthflow.auth.security import create_access_token, hash_password
from healthflow.database.models import Broker


@pytest.mark.asyncio
async def test_valid_token_returns_broker(client, db_session):
    """A valid access token should authenticate and return the broker."""
    broker = Broker(
        email="dep-test@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Dep Test Broker",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    token = create_access_token({"sub": str(broker.id), "role": "broker"})
    response = await client.get(
        "/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should not be 401 — token is valid
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_missing_token_returns_401(client):
    """A request without a token should return 401."""
    response = await client.get("/clients")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client):
    """A request with an invalid token should return 401."""
    response = await client.get(
        "/clients",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_nonexistent_broker_returns_401(client):
    """A valid token for a non-existent broker should return 401."""
    fake_id = str(uuid.uuid4())
    token = create_access_token({"sub": fake_id, "role": "broker"})
    response = await client.get(
        "/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
