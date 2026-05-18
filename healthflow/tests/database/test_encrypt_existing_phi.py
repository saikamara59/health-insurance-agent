"""Test the encrypt_existing_phi.py one-time migration script."""
import json

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Base, Broker, Client


@pytest_asyncio.fixture
async def db_with_plaintext_rows(monkeypatch):
    """Build a DB with rows whose encrypted columns contain plaintext (legacy state).

    Done by inserting via raw SQL, bypassing the TypeDecorator.
    """
    monkeypatch.setenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", "1")
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        with system_context("test setup"):
            broker = Broker(
                email="mig@t.test", hashed_password=hash_password("xPass-1234!"), full_name="Mig",
            )
            session.add(broker)
            await session.flush()
            # Insert client with PLAINTEXT in encrypted columns via raw SQL
            await session.execute(
                text("""
                    INSERT INTO clients (id, broker_id, full_name, zip_code, age, income_level,
                                         doctors, prescriptions, procedures, created_at, updated_at)
                    VALUES (:id, :bid, :name, :zip, :age, :inc, :docs, :rx, :proc,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "bid": str(broker.id),
                    "name": "Plain Patient",
                    "zip": "10001", "age": 50, "inc": "low",
                    "docs": json.dumps([{"name": "Dr. Plain"}]),
                    "rx": json.dumps(["Metformin"]),
                    "proc": json.dumps([]),
                },
            )
            await session.commit()
    yield engine, factory
    await engine.dispose()


@pytest.mark.anyio
async def test_encrypt_existing_phi_encrypts_plaintext_rows(db_with_plaintext_rows, monkeypatch):
    engine, factory = db_with_plaintext_rows

    from scripts.encrypt_existing_phi import encrypt_all
    await encrypt_all(factory)

    # After the script: rows should be ciphertext on disk
    async with factory() as session:
        with system_context("verify"):
            raw = await session.execute(text("SELECT full_name, doctors FROM clients"))
            row = raw.first()
            assert row.full_name.startswith("v1:")
            assert "Plain Patient" not in row.full_name
            assert row.doctors.startswith("v1:")

    # Reads via ORM should still return plaintext (with toggle off — strict mode)
    monkeypatch.delenv("PHI_ENCRYPTION_ALLOW_PLAINTEXT_READ", raising=False)
    async with factory() as session:
        with system_context("verify"):
            client = (await session.execute(select(Client))).scalar_one()
            assert client.full_name == "Plain Patient"
            assert client.doctors == [{"name": "Dr. Plain"}]
