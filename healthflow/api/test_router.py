"""Test-only router. Wipes and re-seeds the DB.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter
from sqlalchemy import delete

from healthflow.database.config import async_session_factory
from healthflow.database.models import (
    ActionHistory,
    Broker,
    Client,
    Feedback,
    PromptVariant,
)
from healthflow.seed_data import seed_db


test_router = APIRouter(prefix="/__test", tags=["test"])

# Serialize concurrent resets — Playwright fires them in parallel across browsers,
# and SQLite doesn't tolerate concurrent writes well.
_reset_lock = asyncio.Lock()

# Tables in dependency order (children before parents) for safe DELETE.
_TABLES_TO_CLEAR = [Feedback, ActionHistory, PromptVariant, Client, Broker]


@test_router.post("/reset")
async def reset_db() -> dict:
    """Delete all rows from app tables, then re-seed with TEST_BROKER + TEST_CLIENTS.

    Uses DELETE rather than DROP/CREATE so we don't fight SQLite connection
    pool state or transaction isolation around DDL.
    """
    async with _reset_lock:
        async with async_session_factory() as session:
            for table in _TABLES_TO_CLEAR:
                await session.execute(delete(table))
            await session.commit()

            await seed_db(session)
            await session.commit()
    return {"status": "reset"}
