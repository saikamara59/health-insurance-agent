"""Tests for OptionalBrokerContextMiddleware.

Verifies the middleware opportunistically sets current_broker_id from
a valid bearer, leaves it unset for missing/invalid tokens, and never
401s a route on its own. The InvocationLogger captures the broker_id
at agent-call time via the same ContextVar, so this middleware is
what makes forensics work for the agent routes that don't
auth-depend on get_current_broker.
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from healthflow.api.optional_broker_middleware import OptionalBrokerContextMiddleware
from healthflow.auth.security import create_access_token
from healthflow.auth.tenant_context import current_broker_id


def _make_probe_app() -> FastAPI:
    """A tiny app whose only route reports the current ContextVar value."""
    app = FastAPI()
    app.add_middleware(OptionalBrokerContextMiddleware)

    @app.get("/whoami")
    def whoami():
        value = current_broker_id.get()
        return {"broker_id": str(value) if value else None}

    return app


def test_no_bearer_leaves_context_unset():
    client = TestClient(_make_probe_app())
    resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json() == {"broker_id": None}


def test_valid_bearer_sets_context():
    broker_id = uuid.uuid4()
    token = create_access_token({"sub": str(broker_id), "role": "broker"})
    client = TestClient(_make_probe_app())
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"broker_id": str(broker_id)}


def test_malformed_bearer_is_silently_ignored():
    """Bad token → route still 200, ContextVar stays None. Auth requirements
    on protected routes are enforced by their own Depends, not here."""
    client = TestClient(_make_probe_app())
    resp = client.get("/whoami", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 200
    assert resp.json() == {"broker_id": None}


def test_non_access_token_does_not_set_context():
    """Only `type=access` tokens count — a hand-rolled token of any other
    type should leave the ContextVar untouched."""
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from healthflow.auth.security import JWT_ALGORITHM, JWT_SECRET

    broker_id = uuid.uuid4()
    payload = {
        "sub": str(broker_id),
        "role": "broker",
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    client = TestClient(_make_probe_app())
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"broker_id": None}


def test_context_is_reset_between_requests():
    """No bleed: two consecutive requests with different tokens see only
    their own token's broker_id."""
    a = uuid.uuid4()
    b = uuid.uuid4()
    t_a = create_access_token({"sub": str(a), "role": "broker"})
    t_b = create_access_token({"sub": str(b), "role": "broker"})

    client = TestClient(_make_probe_app())
    r_a = client.get("/whoami", headers={"Authorization": f"Bearer {t_a}"})
    r_b = client.get("/whoami", headers={"Authorization": f"Bearer {t_b}"})
    r_none = client.get("/whoami")

    assert r_a.json()["broker_id"] == str(a)
    assert r_b.json()["broker_id"] == str(b)
    assert r_none.json()["broker_id"] is None
