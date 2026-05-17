import pytest


async def _register_and_login(client, email="crud@example.com"):
    """Helper to register a broker and get an auth token."""
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "securepass123!",
            "full_name": "CRUD Broker",
        },
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "securepass123!"},
    )
    return login_resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_client(client):
    token = await _register_and_login(client, "create-client@example.com")
    response = await client.post(
        "/clients",
        json={
            "full_name": "Jane Doe",
            "zip_code": "10001",
            "age": 45,
            "income_level": "medium",
            "doctors": [{"name": "Dr. Chen", "npi": "1234567890"}],
            "prescriptions": ["Metformin"],
            "procedures": ["MRI"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Jane Doe"
    assert data["zip_code"] == "10001"
    assert data["age"] == 45
    assert "id" in data
    assert "broker_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_clients(client):
    token = await _register_and_login(client, "list-clients@example.com")
    # Create two clients
    await client.post(
        "/clients",
        json={
            "full_name": "Client One",
            "zip_code": "10001",
            "age": 30,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/clients",
        json={
            "full_name": "Client Two",
            "zip_code": "90210",
            "age": 50,
            "income_level": "high",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {c["full_name"] for c in data}
    assert "Client One" in names
    assert "Client Two" in names


@pytest.mark.asyncio
async def test_get_client_by_id(client):
    token = await _register_and_login(client, "get-client@example.com")
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Get Me",
            "zip_code": "60601",
            "age": 40,
            "income_level": "medium",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.get(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_nonexistent_client(client):
    token = await _register_and_login(client, "noexist@example.com")
    import uuid
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/clients/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_client(client):
    token = await _register_and_login(client, "update-client@example.com")
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Before Update",
            "zip_code": "10001",
            "age": 35,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.put(
        f"/clients/{client_id}",
        json={"full_name": "After Update", "age": 36},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "After Update"
    assert data["age"] == 36
    # Unchanged fields should stay the same
    assert data["zip_code"] == "10001"
    assert data["income_level"] == "low"


@pytest.mark.asyncio
async def test_delete_client(client):
    token = await _register_and_login(client, "delete-client@example.com")
    create_resp = await client.post(
        "/clients",
        json={
            "full_name": "Delete Me",
            "zip_code": "10001",
            "age": 25,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.delete(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_ownership_check_get(client):
    """Broker A cannot view Broker B's client."""
    token_a = await _register_and_login(client, "broker-a@example.com")
    token_b = await _register_and_login(client, "broker-b@example.com")

    # Broker A creates a client
    create_resp = await client.post(
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
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client_id = create_resp.json()["id"]

    # Broker B tries to access it
    response = await client.get(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    # 404 (not 403) per the multi-tenancy spec: don't leak existence of
    # another broker's records.
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ownership_check_update(client):
    """Broker A cannot update Broker B's client."""
    token_a = await _register_and_login(client, "owner-a@example.com")
    token_b = await _register_and_login(client, "owner-b@example.com")

    create_resp = await client.post(
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
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.put(
        f"/clients/{client_id}",
        json={"full_name": "Hacked Name"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    # 404 (not 403) per the multi-tenancy spec: don't leak existence of
    # another broker's records.
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ownership_check_delete(client):
    """Broker A cannot delete Broker B's client."""
    token_a = await _register_and_login(client, "del-a@example.com")
    token_b = await _register_and_login(client, "del-b@example.com")

    create_resp = await client.post(
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
        headers={"Authorization": f"Bearer {token_a}"},
    )
    client_id = create_resp.json()["id"]

    response = await client.delete(
        f"/clients/{client_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    # 404 (not 403) per the multi-tenancy spec: don't leak existence of
    # another broker's records.
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_client_without_auth(client):
    response = await client.post(
        "/clients",
        json={
            "full_name": "No Auth",
            "zip_code": "10001",
            "age": 30,
            "income_level": "low",
            "doctors": [],
            "prescriptions": [],
            "procedures": [],
        },
    )
    assert response.status_code == 401
