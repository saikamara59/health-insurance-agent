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
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients/{id}")
        )).scalars().all()
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
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients")
        )).scalars().all()
    assert len(log) == 1
    assert log[0].operation == "read"
    assert log[0].row_count == 2
    assert set(log[0].row_ids) == {str(c1.id), str(c2.id)}


@pytest.mark.anyio
async def test_read_listener_uses_system_endpoint_under_system_context(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("nightly recompute"):
        await session.execute(select(Client))
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "system:nightly recompute")
        )).scalars().all()
    # one entry for the Client read; the PhiAccessLog read itself is self-excluded
    assert len(log) == 1
    assert log[0].broker_id is None
    assert log[0].endpoint == "system:nightly recompute"


@pytest.mark.anyio
async def test_read_listener_ignores_non_phi_tables(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("verify"):
        # Broker is not a PHI table — querying it must not create an audit entry.
        await session.execute(select(Broker))
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "system:verify")
        )).scalars().all()
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


@pytest.mark.anyio
async def test_insert_listener_logs_created_phi_rows(audited_session):
    session, broker, _c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("POST /clients")
    try:
        new_client = Client(
            broker_id=broker.id, full_name="Created Client", zip_code="33101",
            age=70, income_level="low", doctors=[], prescriptions=[], procedures=[],
        )
        session.add(new_client)
        await session.flush()
        created_id = new_client.id
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(
                (PhiAccessLog.operation == "create") & (PhiAccessLog.endpoint == "POST /clients")
            )
        )).scalars().all()
    assert len(log) == 1
    assert log[0].table_name == "clients"
    assert log[0].row_ids == [str(created_id)]
    assert log[0].operation == "create"
    assert log[0].endpoint == "POST /clients"


@pytest.mark.anyio
async def test_insert_listener_ignores_non_phi_inserts(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("verify"):
        # Inserting a Broker (not a PHI table) must not create a 'create' entry.
        b = Broker(email="ignored@t.test", hashed_password=hash_password("x"), full_name="X")
        session.add(b)
        await session.flush()
        await session.commit()
        log = (await session.execute(
            select(PhiAccessLog).where(
                (PhiAccessLog.operation == "create") & (PhiAccessLog.endpoint == "system:verify")
            )
        )).scalars().all()
    assert log == []


@pytest.mark.anyio
async def test_phi_access_log_is_self_excluded_no_recursion(audited_session):
    """Writing and reading phi_access_log must not generate audit entries
    about phi_access_log itself."""
    session, broker, _c1, _c2 = audited_session
    # Trigger one real audit entry (a Client read) with a recognizable endpoint.
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients (self-excl)")
    try:
        await session.execute(select(Client))
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    # Now read phi_access_log many times. If it were audited, each read would
    # append more entries about phi_access_log itself and the count would grow.
    with system_context("self-excl verify"):
        first = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients (self-excl)")
        )).scalars().all()
        second = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients (self-excl)")
        )).scalars().all()
        third = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients (self-excl)")
        )).scalars().all()
    assert len(first) == len(second) == len(third) == 1

    # Belt-and-suspenders: no entry anywhere should describe phi_access_log itself.
    with system_context("self-excl verify all"):
        any_self_entry = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.table_name == "phi_access_log")
        )).scalars().all()
    assert any_self_entry == []


@pytest.mark.anyio
async def test_audit_listener_sees_tenant_scoped_results(audited_session):
    """The audit listener runs AFTER the tenant filter, so row_ids reflect the
    tenant-scoped result, not the unscoped table."""
    session, broker, c1, c2 = audited_session
    # Add a second broker with a client that should NOT appear in broker A's
    # audit entry.
    with system_context("coexist test setup"):
        broker_b = Broker(email="rb@t.test", hashed_password=hash_password("x"), full_name="RB")
        session.add(broker_b)
        await session.flush()
        cb = Client(
            broker_id=broker_b.id, full_name="B Client", zip_code="90210",
            age=33, income_level="high", doctors=[], prescriptions=[], procedures=[],
        )
        session.add(cb)
        await session.commit()

    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients (coexist)")
    try:
        result = await session.execute(select(Client))
        rows = result.scalars().all()
        assert len(rows) == 2  # tenant filter scoped to broker A
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("coexist verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients (coexist)")
        )).scalars().all()
    assert len(log) == 1
    assert set(log[0].row_ids) == {str(c1.id), str(c2.id)}
    assert str(cb.id) not in log[0].row_ids  # broker B's client was filtered out


from healthflow.database.phi_audit import query_by_broker, query_by_patient


@pytest.mark.anyio
async def test_query_by_patient_finds_entries_mentioning_that_patient(audited_session):
    session, broker, c1, c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients (qbp)")
    try:
        await session.execute(select(Client))  # logs c1 + c2
        await session.execute(select(Client).where(Client.id == c1.id))  # logs c1
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("audit query"):
        c1_hits = await query_by_patient(session, str(c1.id))
        c2_hits = await query_by_patient(session, str(c2.id))
    # Filter to entries from this test (other tests may share the audited_session
    # fixture-scope semantics in some pytest configs); use endpoint to scope.
    c1_test_hits = [e for e in c1_hits if e.endpoint == "GET /clients (qbp)"]
    c2_test_hits = [e for e in c2_hits if e.endpoint == "GET /clients (qbp)"]
    # c1 appears in both the list read and the single read; c2 only in the list.
    assert len(c1_test_hits) == 2
    assert len(c2_test_hits) == 1
    assert all(str(c1.id) in e.row_ids for e in c1_test_hits)


@pytest.mark.anyio
async def test_query_by_broker_finds_that_brokers_entries(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients/{id} (qbb)")
    try:
        await session.execute(select(Client).where(Client.id == c1.id))
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("audit query"):
        hits = await query_by_broker(session, str(broker.id))
    # Filter to this test's entries by endpoint.
    test_hits = [e for e in hits if e.endpoint == "GET /clients/{id} (qbb)"]
    assert len(test_hits) >= 1
    assert all(e.broker_id == broker.id for e in test_hits)
