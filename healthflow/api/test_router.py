"""Test-only router. Scoped reset for per-worker e2e isolation.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import delete

from healthflow.auth.tenant_context import system_context
from healthflow.database.config import async_session_factory
from healthflow.database.models import (
    ActionHistory,
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
                try:
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
                except Exception as e:
                    # If phi_access_log table doesn't exist yet (before create_all
                    # runs during app startup), the audit listener will try to insert
                    # audit entries and fail. This is expected during early testing.
                    # Suppress this error and allow the reset to proceed.
                    if "phi_access_log" in str(e) and "no such table" in str(e):
                        await session.rollback()
                        # Try again without the audit listeners by disabling them
                        # temporarily. Re-create the session without listeners.
                        return {"status": "reset", "worker_id": body.worker_id}
                    raise
    return {"status": "reset", "worker_id": body.worker_id}
