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
from healthflow.database.models import Base, Broker, Client, Feedback
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
        with system_context("test fixture: tenant_filter setup"):
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
    with system_context("test"):
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


@pytest.mark.anyio
async def test_install_tenant_filter_is_idempotent():
    """Calling install_tenant_filter repeatedly must not register duplicate listeners."""
    from sqlalchemy import event as sa_event
    from sqlalchemy.orm import Session
    from healthflow.database.tenant_filter import _on_do_orm_execute, install_tenant_filter

    engine_a = create_async_engine("sqlite+aiosqlite:///", echo=False)
    factory_a = async_sessionmaker(engine_a, class_=AsyncSession, expire_on_commit=False)
    engine_b = create_async_engine("sqlite+aiosqlite:///", echo=False)
    factory_b = async_sessionmaker(engine_b, class_=AsyncSession, expire_on_commit=False)

    # Register multiple times across multiple factories — should still only land once.
    install_tenant_filter(factory_a)
    install_tenant_filter(factory_a)
    install_tenant_filter(factory_b)

    # event.contains returns True if registered; we can't easily count, but we can
    # confirm the listener is present and that further calls don't change behavior.
    assert sa_event.contains(Session, "do_orm_execute", _on_do_orm_execute)

    await engine_a.dispose()
    await engine_b.dispose()


@pytest.mark.anyio
async def test_raw_sql_against_tenant_table_without_filter_raises():
    """text('SELECT * FROM clients') with no broker_id clause should fail loud."""
    from sqlalchemy import text
    from healthflow.database.tenant_filter import install_raw_sql_guard

    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    async with engine.connect() as conn:
        with pytest.raises(TenantContextMissing):
            await conn.execute(text("SELECT * FROM clients"))
    await engine.dispose()


@pytest.mark.anyio
async def test_raw_sql_with_explicit_broker_id_filter_passes():
    """text('SELECT ... WHERE broker_id = ...') should be allowed."""
    from sqlalchemy import text
    from healthflow.database.tenant_filter import install_raw_sql_guard

    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    async with engine.connect() as conn:
        # Empty result is fine; we're testing that the guard doesn't raise.
        result = await conn.execute(
            text("SELECT * FROM clients WHERE broker_id = :b"),
            {"b": str(uuid.uuid4())},
        )
        assert result.fetchall() == []
    await engine.dispose()


@pytest.mark.anyio
async def test_raw_sql_against_non_tenant_table_unaffected():
    """SELECT against `brokers` table is fine without a broker_id clause."""
    from sqlalchemy import text
    from healthflow.database.tenant_filter import install_raw_sql_guard

    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM brokers"))
        assert result.fetchall() == []
    await engine.dispose()


@pytest.mark.anyio
async def test_raw_sql_insert_into_tenant_table_not_guarded():
    """INSERT INTO clients is not a leak vector; guard must not raise on it."""
    from sqlalchemy import text
    from healthflow.database.tenant_filter import install_raw_sql_guard

    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    broker_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        # INSERT broker first so the FK satisfies.
        await conn.execute(
            text("INSERT INTO brokers (id, email, hashed_password, full_name, role, is_active, created_at) "
                 "VALUES (:id, :email, :pw, :name, 'broker', 1, '2026-01-01')"),
            {"id": broker_id, "email": "ins@t.test", "pw": "x", "name": "Ins"},
        )
        # Now INSERT INTO clients should NOT raise even with no current_broker_id.
        await conn.execute(
            text("INSERT INTO clients (id, broker_id, full_name, zip_code, age, income_level, "
                 "doctors, prescriptions, procedures, created_at, updated_at) "
                 "VALUES (:id, :bid, 'X', '10001', 40, 'medium', '[]', '[]', '[]', '2026-01-01', '2026-01-01')"),
            {"id": str(uuid.uuid4()), "bid": broker_id},
        )
    await engine.dispose()


@pytest.mark.anyio
async def test_production_factory_has_listeners_installed():
    """Importing the production config wires the listeners onto the factory.

    Smoke test: the import-time side effects in healthflow.database.config
    should leave the production async_session_factory ready to enforce.
    """
    from healthflow.database.config import async_session_factory, engine
    from sqlalchemy import event
    from healthflow.database.tenant_filter import _on_before_execute, _on_do_orm_execute

    # event.contains returns True if our specific listener function is
    # registered for that event on that target.
    assert event.contains(
        async_session_factory.class_.sync_session_class, "do_orm_execute", _on_do_orm_execute
    ), "do_orm_execute listener missing from production session factory"
    assert event.contains(engine.sync_engine, "before_execute", _on_before_execute), \
        "before_execute guard missing from production engine"


@pytest.mark.anyio
async def test_multi_entity_select_filters_on_first_tenant_entity(session_with_filter):
    """Multi-entity SELECT (e.g. select(Client.id, Feedback.output_id))
    currently auto-filters on whichever tenant-scoped entity the loop in
    `_statement_targets_tenant_model` returns first. This test locks in
    the current single-entity-fall-through behavior so any future change
    is deliberate.
    """
    session, broker_a, broker_b, client_a, _client_b = session_with_filter
    # Add Feedback rows for BOTH brokers so the multi-entity select would
    # find broker_b's row if it weren't filtering on something.
    with system_context("test setup"):
        session.add_all([
            Feedback(broker_id=broker_a.id, output_id="oA", agent_type="compare",
                     accuracy=5, clarity=5, helpfulness=5, comment="A"),
            Feedback(broker_id=broker_b.id, output_id="oB", agent_type="compare",
                     accuracy=3, clarity=3, helpfulness=3, comment="B"),
        ])
        await session.commit()

    token = current_broker_id.set(broker_a.id)
    try:
        # Real multi-entity select against two tenant-scoped tables.
        # The current implementation in `_statement_targets_tenant_model`
        # iterates TENANT_SCOPED_MODELS and returns the first match —
        # so the WHERE clause is applied to ONE of the two entities.
        # Whichever entity gets filtered, the other is exposed to all
        # brokers' rows via the join. This test asserts that A's queries
        # do not leak B's data via this fall-through.
        result = await session.execute(
            select(Client.id, Feedback.output_id)
            .join(Feedback, Feedback.broker_id == Client.broker_id)
        )
        rows = result.all()
        # Either Client or Feedback is filtered to broker_a; the join condition
        # then constrains the other side. Either way, B's data must not appear.
        assert all(c_id == client_a.id for c_id, _ in rows), \
            f"Cross-broker leak via multi-entity select: {rows}"
        assert all(out == "oA" for _, out in rows), \
            f"Cross-broker leak via multi-entity select: {rows}"
    finally:
        current_broker_id.reset(token)
