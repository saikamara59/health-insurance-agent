import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from healthflow.auth.security import JWT_SECRET, JWT_ALGORITHM


@pytest.mark.asyncio
async def test_full_broker_workflow(client):
    """End-to-end: register -> login -> create client -> list -> get -> update -> verify."""

    # Step 1: Register a broker
    register_resp = await client.post(
        "/auth/register",
        json={
            "email": "e2e@example.com",
            "password": "securepass123",
            "full_name": "E2E Broker",
        },
    )
    assert register_resp.status_code == 201
    broker_id = register_resp.json()["id"]

    # Step 2: Login
    login_resp = await client.post(
        "/auth/login",
        json={"email": "e2e@example.com", "password": "securepass123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 3: Create a client
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Jane Doe",
            "zip_code": "10001",
            "age": 45,
            "income_level": "medium",
            "doctors": [{"name": "Dr. Chen", "npi": "1234567890"}],
            "prescriptions": ["Metformin", "Lisinopril"],
            "procedures": ["MRI"],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    client_data = create_resp.json()
    client_id = client_data["id"]
    assert client_data["broker_id"] == broker_id
    assert client_data["full_name"] == "Jane Doe"
    assert len(client_data["doctors"]) == 1
    assert len(client_data["prescriptions"]) == 2

    # Step 4: Create a second client
    create_resp2 = await client.post(
        "/clients",
        json={
            "full_name": "John Smith",
            "zip_code": "90210",
            "age": 30,
            "income_level": "high",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers=headers,
    )
    assert create_resp2.status_code == 201

    # Step 5: List clients — should see both
    list_resp = await client.get("/clients", headers=headers)
    assert list_resp.status_code == 200
    clients_list = list_resp.json()
    assert len(clients_list) == 2

    # Step 6: Get a specific client
    get_resp = await client.get(f"/clients/{client_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["full_name"] == "Jane Doe"

    # Step 7: Update the client
    update_resp = await client.put(
        f"/clients/{client_id}",
        json={"age": 46, "prescriptions": ["Metformin", "Lisinopril", "Atorvastatin"]},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["age"] == 46
    assert len(updated["prescriptions"]) == 3

    # Step 8: Delete the second client
    second_id = create_resp2.json()["id"]
    delete_resp = await client.delete(f"/clients/{second_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Verify only one client remains
    list_resp2 = await client.get("/clients", headers=headers)
    assert len(list_resp2.json()) == 1

    # Step 9: Refresh the token
    refresh_resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_access_token = refresh_resp.json()["access_token"]
    assert new_access_token is not None
    assert refresh_resp.json()["token_type"] == "bearer"

    # Step 10: Use the new token to access clients
    new_headers = {"Authorization": f"Bearer {new_access_token}"}
    list_resp3 = await client.get("/clients", headers=new_headers)
    assert list_resp3.status_code == 200
    assert len(list_resp3.json()) == 1


@pytest.mark.asyncio
async def test_multi_broker_isolation(client):
    """Two brokers should not see each other's clients."""

    # Register Broker A
    await client.post(
        "/auth/register",
        json={
            "email": "isolation-a@example.com",
            "password": "securepass123",
            "full_name": "Broker A",
        },
    )
    login_a = await client.post(
        "/auth/login",
        json={"email": "isolation-a@example.com", "password": "securepass123"},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register Broker B
    await client.post(
        "/auth/register",
        json={
            "email": "isolation-b@example.com",
            "password": "securepass123",
            "full_name": "Broker B",
        },
    )
    login_b = await client.post(
        "/auth/login",
        json={"email": "isolation-b@example.com", "password": "securepass123"},
    )
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Broker A creates a client
    resp_a = await client.post(
        "/clients",
        json={
            "full_name": "A's Client",
            "zip_code": "10001",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers=headers_a,
    )
    assert resp_a.status_code == 201
    a_client_id = resp_a.json()["id"]

    # Broker B creates a client
    resp_b = await client.post(
        "/clients",
        json={
            "full_name": "B's Client",
            "zip_code": "90210",
            "age": 35,
            "income_level": "high",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers=headers_b,
    )
    assert resp_b.status_code == 201

    # Broker A lists clients — should see only their own
    list_a = await client.get("/clients", headers=headers_a)
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["full_name"] == "A's Client"

    # Broker B lists clients — should see only their own
    list_b = await client.get("/clients", headers=headers_b)
    assert len(list_b.json()) == 1
    assert list_b.json()[0]["full_name"] == "B's Client"

    # Broker B cannot access Broker A's client
    cross_resp = await client.get(f"/clients/{a_client_id}", headers=headers_b)
    assert cross_resp.status_code == 403

    # Broker B cannot update Broker A's client
    cross_update = await client.put(
        f"/clients/{a_client_id}",
        json={"full_name": "Hacked"},
        headers=headers_b,
    )
    assert cross_update.status_code == 403

    # Broker B cannot delete Broker A's client
    cross_delete = await client.delete(f"/clients/{a_client_id}", headers=headers_b)
    assert cross_delete.status_code == 403


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    """Requests with an expired access token should be rejected with 401."""

    # Register and login to get a real broker sub
    await client.post(
        "/auth/register",
        json={
            "email": "expired@example.com",
            "password": "securepass123",
            "full_name": "Expired Broker",
        },
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": "expired@example.com", "password": "securepass123"},
    )
    assert login_resp.status_code == 200

    # Craft an already-expired access token
    expired_payload = {
        "sub": "expired@example.com",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    expired_headers = {"Authorization": f"Bearer {expired_token}"}

    # Any protected endpoint should reject the expired token
    resp = await client.get("/clients", headers=expired_headers)
    assert resp.status_code == 401
