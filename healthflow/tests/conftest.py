import os

# Set JWT_SECRET before any healthflow.* module imports it. Required because
# healthflow.auth.security raises at import time if JWT_SECRET is unset or set
# to the known-bad legacy value — see docs/superpowers/specs/2026-05-16-auth-hardening-design.md.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import base64 as _base64

# Set PHI_ENCRYPTION_KEY before any healthflow.* module imports it. Required because
# healthflow.auth.phi_crypto raises at import time if PHI_ENCRYPTION_KEY is unset.
# A deterministic test key — safe to commit because it's only used in tests.
os.environ.setdefault(
    "PHI_ENCRYPTION_KEY",
    _base64.b64encode(b"\x00" * 32).decode(),
)

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.models import Base
from healthflow.database.config import get_db
from healthflow.main import app
from healthflow.logs import server as server_log_module


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_engine():
    from healthflow.database.tenant_filter import install_raw_sql_guard

    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    install_raw_sql_guard(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    from healthflow.database.tenant_filter import install_tenant_filter
    from healthflow.database.phi_audit import install_phi_audit

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    install_phi_audit(factory)  # MUST come after install_tenant_filter
    return factory


@pytest_asyncio.fixture
async def db_session(db_session_factory):
    """Direct DB session for tests that bypass the auth flow.

    Enters system_context() by default so test setup can insert/query
    tenant-scoped tables without raising. Tests that want to assert
    tenancy behavior should use the `client` fixture (which routes
    through real auth) or explicitly set `current_broker_id` after
    `system_context` exits.
    """
    from healthflow.auth.tenant_context import system_context

    async with db_session_factory() as session:
        with system_context("test fixture: direct db_session"):
            yield session


@pytest_asyncio.fixture
async def client(db_session_factory):
    """FastAPI TestClient with the database dependency overridden to use SQLite."""

    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_server_log(tmp_path):
    """Point ServerLogger at a per-test tmp_path so tests don't write to real logs/server.log.

    Pre-populates the module-level cache so get_server_logger() returns this
    instance. This preserves singleton semantics (two calls return the same object)
    while redirecting file writes to tmp_path.
    """
    server_log_module.reset_server_logger_for_tests()
    server_log_module._cached_logger = server_log_module.ServerLogger(
        log_dir=str(tmp_path / "logs")
    )
    yield
    server_log_module.reset_server_logger_for_tests()
