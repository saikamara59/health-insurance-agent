"""Test-only router. Scoped reset for per-worker e2e isolation.

Only registered when HEALTHFLOW_TEST_MODE=1. Never expose in production.
"""
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from healthflow.database.config import async_session_factory
from healthflow.database.models import (
    ActionHistory,
    Broker,
    Feedback,
)
from healthflow.seed_data import seed_for_worker, worker_email


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
            # Look up the broker first so we can delete dependent rows before
            # seed_for_worker deletes Client rows.  On Postgres (FK enforcement
            # on) ActionHistory.client_id → Client.id would raise if we deleted
            # clients while action_history rows still referenced them.
            existing_broker = (
                await session.execute(
                    select(Broker).where(Broker.email == worker_email(body.worker_id))
                )
            ).scalar_one_or_none()

            if existing_broker is not None:
                await session.execute(
                    delete(ActionHistory).where(
                        ActionHistory.broker_id == existing_broker.id
                    )
                )
                await session.execute(
                    delete(Feedback).where(Feedback.broker_id == existing_broker.id)
                )

            # seed_for_worker: get-or-create broker, wipe + re-seed clients.
            # PromptVariant is intentionally not wiped: it is a global table
            # (no broker_id column) — wiping it per-worker would destroy rows
            # owned by other workers.
            await seed_for_worker(session, body.worker_id)
            await session.commit()
    return {"status": "reset", "worker_id": body.worker_id}
