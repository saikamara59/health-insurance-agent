"""Test-only router. Scoped reset for per-worker e2e isolation.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.tenant_context import system_context
from healthflow.database.config import async_session_factory, get_db
from healthflow.database.models import (
    ActionHistory,
    Broker,
    Feedback,
)
from healthflow.seed_data import seed_for_worker


test_router = APIRouter(prefix="/__test", tags=["test"])

# SQLite is single-writer; serialize the reset transaction to avoid
# `database is locked` errors when many workers reset concurrently.
_reset_lock = asyncio.Lock()


class ResetRequest(BaseModel):
    worker_id: str = Field(..., pattern=r"^e2e-worker-\d+$")


@test_router.post("/reset")
async def reset_db(body: ResetRequest) -> dict:
    """Wipe and re-seed only the requesting worker's broker-scoped data.

    The broker itself is sticky (created once, never deleted) so JWTs stay
    valid across resets. Client/ActionHistory/Feedback rows owned by this
    broker are deleted and the canonical client set is re-inserted.
    """
    async with _reset_lock:
        async with async_session_factory() as session:
            with system_context(f"e2e reset for worker {body.worker_id}"):
                broker = await seed_for_worker(session, body.worker_id)
                # seed_for_worker already wiped + re-inserted Client rows; also
                # wipe ActionHistory and Feedback rows owned by this broker.
                await session.execute(
                    delete(ActionHistory).where(ActionHistory.broker_id == broker.id)
                )
                await session.execute(
                    delete(Feedback).where(Feedback.broker_id == broker.id)
                )
                # PromptVariant is intentionally not wiped: it is a global table
                # (no broker_id column) — wiping it per-worker would destroy rows
                # owned by other workers.
                await session.commit()
    return {"status": "reset", "worker_id": body.worker_id}


class ActivateBrokerRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


@test_router.post("/activate-broker")
async def activate_broker(
    body: ActivateBrokerRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Flip is_active=True on the broker with this email.

    Used by test helpers that register-then-login: production /auth/register
    now creates accounts as is_active=False (pending admin approval), so
    tests need a way to bypass the approval step without depending on a
    real admin session.

    Uses Depends(get_db) so conftest's dependency override correctly routes
    the write to the per-test in-memory SQLite engine.
    """
    with system_context(f"test activate-broker: {body.email}"):
        result = await db.execute(
            sa_update(Broker).where(Broker.email == body.email).values(is_active=True)
        )
        if result.rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "broker not found")
    return {"activated": True, "email": body.email}
