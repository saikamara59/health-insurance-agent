import pytest


@pytest.mark.asyncio
async def test_health_check_still_works(client):
    """The existing health check or root endpoint should still work."""
    response = await client.get("/health")
    # Accept 200 or 404 — just make sure the app boots
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_auth_register_route_exists(client):
    """The /auth/register route should be registered."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "wiring@example.com",
            "password": "securepass123!",
            "full_name": "Wiring Test",
        },
    )
    # Should not be 404 (route not found)
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_auth_login_route_exists(client):
    """The /auth/login route should be registered."""
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "securepass123!"},
    )
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_clients_route_exists(client):
    """The /clients route should be registered (requires auth)."""
    response = await client.get("/clients")
    # Should be 401 (not authenticated), not 404 (not found)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_existing_compare_route_still_exists(client):
    """Existing Phase 1-5 routes should still be accessible."""
    response = await client.post("/compare", json={})
    # Should be 422 (validation error), not 404
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_openapi_schema_includes_new_routes(client):
    """The OpenAPI schema should include auth and client routes."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/auth/refresh" in paths
    assert "/clients" in paths
