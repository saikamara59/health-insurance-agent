import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "newbroker@example.com",
            "password": "securepass123!",
            "full_name": "New Broker",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newbroker@example.com"
    assert data["full_name"] == "New Broker"
    assert data["role"] == "broker"
    # New accounts are inactive until an admin approves them.
    assert data["is_active"] is False
    assert "id" in data
    # Password should not be in response
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post(
        "/auth/register",
        json={
            "email": "dup@example.com",
            "password": "securepass123!",
            "full_name": "First Broker",
        },
    )
    response = await client.post(
        "/auth/register",
        json={
            "email": "dup@example.com",
            "password": "anotherpass123!",
            "full_name": "Second Broker",
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_short_password(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "full_name": "Short Pass",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    # Register, then activate (production registration creates pending accounts).
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "securepass123!",
            "full_name": "Login Broker",
        },
    )
    await client.post("/__test/activate-broker", json={"email": "login@example.com"})
    # Login
    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "securepass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_pending_approval_returns_403(client):
    """A newly registered (un-approved) account cannot log in — 403 with
    a 'pending approval' message that the frontend can surface."""
    await client.post(
        "/auth/register",
        json={
            "email": "pending@example.com",
            "password": "securepass123!",
            "full_name": "Pending Broker",
        },
    )
    response = await client.post(
        "/auth/login",
        json={"email": "pending@example.com", "password": "securepass123!"},
    )
    assert response.status_code == 403
    assert "pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register",
        json={
            "email": "wrongpw@example.com",
            "password": "securepass123!",
            "full_name": "Wrong PW Broker",
        },
    )
    response = await client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "securepass123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_flow(client):
    # Register, activate, login
    await client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "securepass123!",
            "full_name": "Refresh Broker",
        },
    )
    await client.post("/__test/activate-broker", json={"email": "refresh@example.com"})
    login_response = await client.post(
        "/auth/login",
        json={"email": "refresh@example.com", "password": "securepass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client):
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.token.value"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(client):
    """Using an access token as a refresh token should fail."""
    await client.post(
        "/auth/register",
        json={
            "email": "noaccess@example.com",
            "password": "securepass123!",
            "full_name": "No Access Broker",
        },
    )
    await client.post("/__test/activate-broker", json={"email": "noaccess@example.com"})
    login_response = await client.post(
        "/auth/login",
        json={"email": "noaccess@example.com", "password": "securepass123!"},
    )
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
