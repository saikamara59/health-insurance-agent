"""Verify that get_current_broker sets the tenant ContextVar for the request."""
import pytest


@pytest.mark.anyio
async def test_authenticated_request_sees_broker_in_context_var(client, db_session):
    """When a route runs under get_current_broker, current_broker_id is set."""
    # Register + log in a broker.
    res = await client.post(
        "/auth/register",
        json={
            "email": "ctx@healthflow.test",
            "password": "Ctx123!Pass1",
            "full_name": "Context Test",
        },
    )
    assert res.status_code == 201, res.text
    await client.post("/__test/activate-broker", json={"email": "ctx@healthflow.test"})

    res = await client.post(
        "/auth/login",
        json={"email": "ctx@healthflow.test", "password": "Ctx123!Pass1"},
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


import asyncio


@pytest.mark.anyio
async def test_concurrent_authenticated_requests_do_not_leak_data(client, db_session):
    """Two simultaneous /clients requests under different broker tokens must
    each see only their own broker's client list. This is the integration-
    level proof that ContextVar isolation works end-to-end through the
    FastAPI dispatch + auth dependency + tenant filter stack.
    """
    # Register and log in two brokers, each with one client.
    for label, email in (("a", "leak-a@healthflow.test"), ("b", "leak-b@healthflow.test")):
        res = await client.post(
            "/auth/register",
            json={"email": email, "password": "Leak123!Pass1", "full_name": label.upper()},
        )
        assert res.status_code == 201, res.text
        await client.post("/__test/activate-broker", json={"email": email})

    async def login(email):
        res = await client.post(
            "/auth/login", json={"email": email, "password": "Leak123!Pass1"}
        )
        assert res.status_code == 200
        return res.json()["access_token"]

    token_a = await login("leak-a@healthflow.test")
    token_b = await login("leak-b@healthflow.test")

    # Each broker creates one client with a label-distinguishing name.
    for token, name in ((token_a, "A's client"), (token_b, "B's client")):
        res = await client.post(
            "/clients",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "full_name": name,
                "zip_code": "10001",
                "age": 40,
                "income_level": "medium",
                "doctors": [],
                "prescriptions": [],
                "procedures": [],
            },
        )
        assert res.status_code == 201, res.text

    # Hit /clients concurrently under both tokens; each response must contain
    # exactly that broker's client and no leakage of the other's.
    async def list_for(token):
        res = await client.get(
            "/clients", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        return [c["full_name"] for c in res.json()]

    names_a, names_b = await asyncio.gather(list_for(token_a), list_for(token_b))

    assert names_a == ["A's client"], f"Broker A leaked: {names_a}"
    assert names_b == ["B's client"], f"Broker B leaked: {names_b}"
