"""Tests for the PHI access audit log — model, listeners, self-exclusion."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.auth.tenant_context import current_endpoint, system_context
from healthflow.database.models import Base, PhiAccessLog


@pytest_asyncio.fixture
async def raw_engine():
    """In-memory engine + tables, NO listeners installed (for model-only tests)."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.anyio
async def test_phi_access_log_table_exists_with_expected_columns(raw_engine):
    async with raw_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("phi_access_log")}
        )
    assert columns == {
        "id", "broker_id", "table_name", "operation",
        "row_ids", "row_count", "endpoint", "created_at",
    }


@pytest.mark.anyio
async def test_phi_access_log_row_roundtrips(raw_engine):
    factory = async_sessionmaker(raw_engine, class_=AsyncSession, expire_on_commit=False)
    broker_id = uuid.uuid4()
    client_id = uuid.uuid4()
    async with factory() as session:
        entry = PhiAccessLog(
            broker_id=broker_id,
            table_name="clients",
            operation="read",
            row_ids=[str(client_id)],
            row_count=1,
            endpoint="GET /clients",
        )
        session.add(entry)
        await session.commit()

    async with factory() as session:
        result = await session.execute(select(PhiAccessLog))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].broker_id == broker_id
    assert rows[0].table_name == "clients"
    assert rows[0].operation == "read"
    assert rows[0].row_ids == [str(client_id)]
    assert rows[0].row_count == 1
    assert rows[0].endpoint == "GET /clients"
    assert rows[0].created_at is not None


def test_current_endpoint_default_is_none():
    assert current_endpoint.get() is None


def test_system_context_sets_endpoint_to_system_reason():
    assert current_endpoint.get() is None
    with system_context("RLHF reward scoring"):
        assert current_endpoint.get() == "system:RLHF reward scoring"
    # restored on exit
    assert current_endpoint.get() is None


def test_system_context_restores_prior_endpoint():
    token = current_endpoint.set("GET /clients")
    try:
        with system_context("nested system work"):
            assert current_endpoint.get() == "system:nested system work"
        assert current_endpoint.get() == "GET /clients"
    finally:
        current_endpoint.reset(token)


from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import current_broker_id
from healthflow.database.models import Broker, Client
from healthflow.database.phi_audit import install_phi_audit
from healthflow.database.tenant_filter import install_tenant_filter


@pytest_asyncio.fixture
async def audited_session():
    """In-memory engine + session with BOTH the tenant filter and the audit
    listeners installed, in the required order (tenant filter first)."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)   # MUST be installed before the audit listener
    install_phi_audit(factory)
    async with factory() as session:
        with system_context("test setup"):
            broker = Broker(email="ra@t.test", hashed_password=hash_password("x"), full_name="RA")
            session.add(broker)
            await session.flush()
            c1 = Client(
                broker_id=broker.id, full_name="C One", zip_code="10001",
                age=40, income_level="medium", doctors=[], prescriptions=[], procedures=[],
            )
            c2 = Client(
                broker_id=broker.id, full_name="C Two", zip_code="10002",
                age=50, income_level="high", doctors=[], prescriptions=[], procedures=[],
            )
            session.add_all([c1, c2])
            await session.commit()
        yield session, broker, c1, c2
    await engine.dispose()


@pytest.mark.anyio
async def test_read_listener_logs_single_row_select(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients/{id}")
    try:
        result = await session.execute(select(Client).where(Client.id == c1.id))
        rows = result.scalars().all()
        assert len(rows) == 1  # result still usable after the listener observed it
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert len(log) == 1
    assert log[0].broker_id == broker.id
    assert log[0].table_name == "clients"
    assert log[0].operation == "read"
    assert log[0].row_ids == [str(c1.id)]
    assert log[0].row_count == 1
    assert log[0].endpoint == "GET /clients/{id}"


@pytest.mark.anyio
async def test_read_listener_logs_all_ids_for_a_list_query(audited_session):
    session, broker, c1, c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients")
    try:
        result = await session.execute(select(Client))
        rows = result.scalars().all()
        assert len(rows) == 2
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert len(log) == 1
    assert log[0].operation == "read"
    assert log[0].row_count == 2
    assert set(log[0].row_ids) == {str(c1.id), str(c2.id)}


@pytest.mark.anyio
async def test_read_listener_uses_system_endpoint_under_system_context(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("nightly recompute"):
        await session.execute(select(Client))
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    # one entry for the Client read; the PhiAccessLog read itself is self-excluded
    client_entries = [e for e in log if e.table_name == "clients"]
    assert len(client_entries) == 1
    assert client_entries[0].broker_id is None
    assert client_entries[0].endpoint == "system:nightly recompute"


@pytest.mark.anyio
async def test_read_listener_ignores_non_phi_tables(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("verify"):
        # Broker is not a PHI table — querying it must not create an audit entry.
        await session.execute(select(Broker))
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert log == []


from sqlalchemy import delete as sa_delete, update as sa_update


@pytest.mark.anyio
async def test_delete_listener_logs_affected_id(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("DELETE /clients/{id}")
    try:
        await session.execute(sa_delete(Client).where(Client.id == c1.id))
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.operation == "delete")
        )).scalars().all()
    assert len(log) == 1
    assert log[0].table_name == "clients"
    assert log[0].row_ids == [str(c1.id)]
    assert log[0].row_count == 1
    assert log[0].endpoint == "DELETE /clients/{id}"


@pytest.mark.anyio
async def test_update_listener_logs_affected_id(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("PUT /clients/{id}")
    try:
        await session.execute(
            sa_update(Client).where(Client.id == c1.id).values(age=99)
        )
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.operation == "update")
        )).scalars().all()
    assert len(log) == 1
    assert log[0].table_name == "clients"
    assert log[0].row_ids == [str(c1.id)]
    assert log[0].operation == "update"
