"""Tests for the do_orm_execute tenant filter against a real in-memory DB."""
import logging
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import (
    TenantContextMissing,
    current_broker_id,
    system_context,
)
from healthflow.database.models import Base, Broker, Client, PromptVariant
from healthflow.database.tenant_filter import (
    TENANT_SCOPED_MODELS,
    install_tenant_filter,
)


@pytest_asyncio.fixture
async def session_with_filter():
    """In-memory engine + session, with the tenant filter installed."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    async with factory() as session:
        # Seed two brokers + one client per broker, inside system_context so
        # the inserts/selects during setup don't trip the filter.
        with system_context():
            broker_a = Broker(email="a@t.test", hashed_password=hash_password("x"), full_name="A")
            broker_b = Broker(email="b@t.test", hashed_password=hash_password("x"), full_name="B")
            session.add_all([broker_a, broker_b])
            await session.flush()
            client_a = Client(
                broker_id=broker_a.id, full_name="A's client", zip_code="10001",
                age=40, income_level="medium", doctors=[], prescriptions=[], procedures=[],
            )
            client_b = Client(
                broker_id=broker_b.id, full_name="B's client", zip_code="10002",
                age=50, income_level="high", doctors=[], prescriptions=[], procedures=[],
            )
            session.add_all([client_a, client_b])
            await session.commit()
        yield session, broker_a, broker_b, client_a, client_b
    await engine.dispose()


def test_registry_lists_phi_tables_only():
    names = {m.__tablename__ for m in TENANT_SCOPED_MODELS}
    assert names == {"clients", "action_history", "feedback"}


@pytest.mark.anyio
async def test_query_with_no_context_raises(session_with_filter):
    session, _, _, _, _ = session_with_filter
    # current_broker_id is unset here.
    with pytest.raises(TenantContextMissing):
        await session.execute(select(Client))


@pytest.mark.anyio
async def test_query_with_context_filters_to_that_broker(session_with_filter):
    session, broker_a, broker_b, client_a, client_b = session_with_filter
    token = current_broker_id.set(broker_a.id)
    try:
        result = await session.execute(select(Client))
        rows = result.scalars().all()
        assert [r.id for r in rows] == [client_a.id]
    finally:
        current_broker_id.reset(token)


@pytest.mark.anyio
async def test_query_inside_system_context_returns_all(session_with_filter):
    session, _, _, client_a, client_b = session_with_filter
    with system_context():
        result = await session.execute(select(Client))
        ids = sorted(r.id for r in result.scalars().all())
    assert ids == sorted([client_a.id, client_b.id])


@pytest.mark.anyio
async def test_non_tenant_scoped_query_unaffected(session_with_filter):
    session, _, _, _, _ = session_with_filter
    # Broker is NOT tenant-scoped — query must work without context.
    assert current_broker_id.get() is None
    result = await session.execute(select(Broker))
    rows = result.scalars().all()
    assert len(rows) == 2  # both brokers visible


@pytest.mark.anyio
async def test_filter_logs_at_debug(session_with_filter, caplog):
    session, broker_a, _, _, _ = session_with_filter
    token = current_broker_id.set(broker_a.id)
    try:
        with caplog.at_level(logging.DEBUG, logger="healthflow.database.tenant_filter"):
            await session.execute(select(Client))
        assert any("tenant_filter: scoped" in r.getMessage() for r in caplog.records)
    finally:
        current_broker_id.reset(token)
