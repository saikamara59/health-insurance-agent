"""Verify that get_current_broker sets the tenant ContextVar for the request."""
import pytest

from healthflow.auth.tenant_context import current_broker_id


@pytest.mark.anyio
async def test_authenticated_request_sees_broker_in_context_var(client, db_session):
    """When a route runs under get_current_broker, current_broker_id is set."""
    # Register + log in a broker.
    res = await client.post(
        "/auth/register",
        json={
            "email": "ctx@healthflow.test",
            "password": "Ctx123!Pass",
            "full_name": "Context Test",
        },
    )
    assert res.status_code == 201, res.text

    res = await client.post(
        "/auth/login",
        json={"email": "ctx@healthflow.test", "password": "Ctx123!Pass"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Hit /clients (a tenant-scoped route). If the auth dependency didn't
    # set the ContextVar, the new tenant filter would raise on the SELECT.
    res = await client.get(
        "/clients", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json() == []  # no clients yet
