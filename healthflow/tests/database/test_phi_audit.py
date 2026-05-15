"""Tests for the PHI access audit log — model, listeners, self-exclusion."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
