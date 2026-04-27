"""Tests for the env-gated /__test/reset endpoint.

Each test reloads healthflow.main after setting the env var, then builds
a fresh AsyncClient against the reloaded app. We can't reuse the shared
`client` fixture from conftest.py because it captures `app` at import time.

Note: this suite covers env-gating and that the endpoint returns 200.
The actual seeding correctness is covered by:
  - healthflow/tests/test_seed_data.py (seed_db unit tests)
  - the e2e test stack (frontend/tests/e2e/) which exercises the seeded
    broker via real login

We don't assert post-reset DB state here because the endpoint uses the
production async_session_factory directly (so DDL and DML stay on the
same engine inside docker), while pytest fixtures use a separate
in-memory engine — the two diverge in tests.
"""
from importlib import reload

import pytest
from httpx import ASGITransport, AsyncClient


def _build_client(db_session_factory):
    """Reload healthflow.main and return an AsyncClient against the fresh app."""
    import healthflow.database.config as db_config
    reload(db_config)
    import healthflow.api.test_router as test_router_module
    reload(test_router_module)
    import healthflow.main as main_module
    reload(main_module)
    app = main_module.app

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test"), app


@pytest.mark.anyio
async def test_reset_endpoint_returns_404_when_test_mode_off(monkeypatch, db_session_factory):
    monkeypatch.delenv("HEALTHFLOW_TEST_MODE", raising=False)
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset", json={"worker_id": "e2e-worker-0"})
        assert response.status_code == 404
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_returns_200_with_valid_worker_id(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset", json={"worker_id": "e2e-worker-0"})
        assert response.status_code == 200
        assert response.json() == {"status": "reset", "worker_id": "e2e-worker-0"}
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_rejects_missing_body(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset")
        assert response.status_code == 422
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_rejects_malformed_worker_id(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset", json={"worker_id": "not-a-worker"})
        assert response.status_code == 422
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()
