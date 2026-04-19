"""Test-only router. Wipes and re-seeds the DB.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter

from healthflow.database.config import async_session_factory, engine
from healthflow.database.models import Base
from healthflow.seed_data import seed_db


test_router = APIRouter(prefix="/__test", tags=["test"])

# Serialize concurrent resets — Playwright fires them in parallel across browsers,
# and SQLite DDL is not safe under contention.
_reset_lock = asyncio.Lock()


@test_router.post("/reset")
async def reset_db() -> dict:
    """Drop all tables, recreate schema, re-seed with TEST_BROKER + TEST_CLIENTS.

    Uses a fresh session_factory() session inside the handler instead of
    Depends(get_db), because the request-scoped session would have been acquired
    before drop_all and would carry stale connection state.
    """
    async with _reset_lock:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_factory() as session:
            await seed_db(session)
            await session.commit()
    return {"status": "reset"}
