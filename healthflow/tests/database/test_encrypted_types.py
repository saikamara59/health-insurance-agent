"""Unit tests for EncryptedString and EncryptedJSON TypeDecorators.

Uses a throwaway in-memory SQLite session with a real key — no mocking,
real encrypt + real decrypt round-trip.
"""
import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, MetaData, Table, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.encrypted_types import EncryptedJSON, EncryptedString


@pytest_asyncio.fixture
async def encrypted_session():
    """Throwaway engine + a one-off table with encrypted columns. No app DB."""
    metadata = MetaData()
    test_table = Table(
        "enc_test",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("secret_str", EncryptedString(2000)),
        Column("secret_json", EncryptedJSON()),
    )
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session, test_table
    await engine.dispose()


@pytest.mark.anyio
async def test_encrypted_string_roundtrips(encrypted_session):
    session, test_table = encrypted_session
    await session.execute(
        test_table.insert().values(id=1, secret_str="Eleanor Rigby", secret_json=None)
    )
    await session.commit()

    result = await session.execute(select(test_table).where(test_table.c.id == 1))
    row = result.first()
    assert row.secret_str == "Eleanor Rigby"


@pytest.mark.anyio
async def test_encrypted_json_roundtrips_list_of_dicts(encrypted_session):
    session, test_table = encrypted_session
    value = [{"name": "Dr. Aanur", "npi": "1234567890"}, {"name": "Dr. Aaron"}]
    await session.execute(
        test_table.insert().values(id=2, secret_str=None, secret_json=value)
    )
    await session.commit()

    result = await session.execute(select(test_table).where(test_table.c.id == 2))
    row = result.first()
    assert row.secret_json == value


@pytest.mark.anyio
async def test_encrypted_columns_store_ciphertext_on_disk(encrypted_session):
    """Raw SQL bypasses the TypeDecorator — proves the value is ciphertext at rest."""
    session, test_table = encrypted_session
    await session.execute(
        test_table.insert().values(id=3, secret_str="Walt Whitman", secret_json=["dx"])
    )
    await session.commit()

    raw = await session.execute(text("SELECT secret_str, secret_json FROM enc_test WHERE id = 3"))
    secret_str, secret_json = raw.first()
    # Both should be ciphertext-shaped: starts with vN: and has the three-part form
    assert secret_str.startswith("v1:") and secret_str.count(":") == 2
    assert "Walt Whitman" not in secret_str
    assert secret_json.startswith("v1:")
    assert "dx" not in secret_json


import uuid

from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import current_broker_id, current_endpoint, system_context
from healthflow.database.models import Base, Broker, Client, PhiAccessLog
from healthflow.database.phi_audit import install_phi_audit
from healthflow.database.tenant_filter import install_tenant_filter


@pytest_asyncio.fixture
async def app_db():
    """The real app's Base.metadata + tenant filter + audit listener installed.
    Mirrors the production session factory."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    install_phi_audit(factory)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.anyio
async def test_client_full_name_encrypted_at_rest_with_tenant_filter_and_audit_log(app_db):
    """Cross-sub-project sanity: encryption + tenant filter + PHI audit all work together."""
    session = app_db

    # Seed a broker + client under system_context
    with system_context("test setup"):
        broker = Broker(
            email="enc1@t.test", hashed_password=hash_password("xPass-1234!"), full_name="EncBroker",
        )
        session.add(broker)
        await session.flush()
        client_a = Client(
            broker_id=broker.id, full_name="Eleanor Rigby", zip_code="10001",
            age=67, income_level="low",
            doctors=[], prescriptions=[], procedures=[],
        )
        session.add(client_a)
        await session.commit()
        client_id = client_a.id

    # Read via the ORM under broker's context — full_name decrypts transparently
    token = current_broker_id.set(broker.id)
    ep = current_endpoint.set("GET /clients/{id}")
    try:
        result = await session.execute(select(Client).where(Client.id == client_id))
        client = result.scalar_one()
        assert client.full_name == "Eleanor Rigby"
        # Tenant filter still applied; zip_code (plaintext column) still readable
        assert client.zip_code == "10001"
    finally:
        current_endpoint.reset(ep)
        current_broker_id.reset(token)

    # Raw SELECT bypasses the TypeDecorator — confirms ciphertext on disk
    with system_context("test verify"):
        raw = await session.execute(text("SELECT full_name FROM clients WHERE id = :id"),
                                     {"id": str(client_id)})
        on_disk = raw.scalar_one()
    assert on_disk.startswith("v1:")
    assert "Eleanor Rigby" not in on_disk

    # Audit log row_ids capture still works (UUIDs are plaintext)
    with system_context("test verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients/{id}")
        )).scalars().all()
    assert len(log) == 1
    assert str(client_id) in log[0].row_ids
