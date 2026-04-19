"""Tests for the env-gated /__test/reset endpoint.

Each test reloads healthflow.main after setting the env var, then builds
a fresh AsyncClient against the reloaded app. We can't reuse the shared
`client` fixture from conftest.py because it captures `app` at import time.

Note: this suite covers env-gating and basic seeding behavior. The
"reset wipes pre-existing data" property is validated against the real
docker stack in the T4 smoke test (not here), because the production
endpoint uses the module-level engine for DDL while pytest fixtures
override only the per-request session — the two diverge in tests.
"""
from importlib import reload

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from healthflow.database.config import get_db
from healthflow.database.models import Broker
from healthflow.seed_data import TEST_BROKER


def _build_client(db_session_factory):
    """Reload healthflow.main and return an AsyncClient against the fresh app."""
    # Re-import database.config and test_router fresh in case a prior test
    # (e.g. test_database_config) reloaded database.config — otherwise
    # test_router holds a stale `get_db` reference that won't match our
    # dependency override, and seed writes would leak to the real DB.
    import healthflow.database.config as db_config
    reload(db_config)
    import healthflow.api.test_router as test_router_module
    reload(test_router_module)
    import healthflow.main as main_module
    reload(main_module)
    app = main_module.app

    # Use the freshly-reloaded get_db as the override key so it matches the
    # Depends(get_db) inside the freshly-reloaded test_router.
    current_get_db = db_config.get_db

    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[current_get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test"), app


@pytest.mark.anyio
async def test_reset_endpoint_returns_404_when_test_mode_off(monkeypatch, db_session_factory):
    monkeypatch.delenv("HEALTHFLOW_TEST_MODE", raising=False)
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset")
        assert response.status_code == 404
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_works_when_test_mode_on(monkeypatch, db_session_factory):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        response = await client_.post("/__test/reset")
        assert response.status_code == 200
        assert response.json() == {"status": "reset"}
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reset_endpoint_seeds_test_broker(monkeypatch, db_session_factory, db_session):
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    client_, app = _build_client(db_session_factory)
    try:
        await client_.post("/__test/reset")
    finally:
        await client_.aclose()
        app.dependency_overrides.clear()

    result = await db_session.execute(select(Broker).where(Broker.email == TEST_BROKER["email"]))
    broker = result.scalar_one_or_none()
    assert broker is not None
    assert broker.full_name == TEST_BROKER["full_name"]
