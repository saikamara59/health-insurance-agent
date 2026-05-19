"""Admin-only endpoints. Mounted under prefix /admin and gated by require_admin."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import require_admin
from healthflow.database.config import get_db
from healthflow.database.models import Broker
from healthflow.logs.audit import AuditLogger

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.post("/brokers/{broker_id}/unlock")
async def force_unlock_broker(
    broker_id: _uuid.UUID,
    admin: Broker = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin force-unlocks any broker's account.

    Clears failed_login_count and locked_until. Idempotent — unlocking an
    already-unlocked broker returns the same 200. The action is audit-logged
    with both ids (admin_force_unlock event).
    """
    target = (await db.execute(
        select(Broker).where(Broker.id == broker_id)
    )).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker not found",
        )

    target.failed_login_count = 0
    target.locked_until = None
    await db.commit()

    AuditLogger().log(
        "admin_force_unlock",
        {"admin_id": str(admin.id), "target_broker_id": str(broker_id)},
    )

    return {"unlocked": True}
