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
