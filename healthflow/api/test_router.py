"""Test-only router. Wipes and re-seeds the DB.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.config import engine, get_db
from healthflow.database.models import Base
from healthflow.seed_data import seed_db


test_router = APIRouter(prefix="/__test", tags=["test"])

# Serialize concurrent resets — Playwright fires them in parallel across browsers,
# and SQLite DDL is not safe under contention (drop_all of one reset can race
# create_all of another).
_reset_lock = asyncio.Lock()


@test_router.post("/reset")
async def reset_db(db: AsyncSession = Depends(get_db)) -> dict:
    """Drop all tables, recreate schema, re-seed with TEST_BROKER + TEST_CLIENTS."""
    async with _reset_lock:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        await seed_db(db)
        await db.commit()
    return {"status": "reset"}
