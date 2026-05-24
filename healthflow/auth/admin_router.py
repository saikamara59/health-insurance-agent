"""Admin-only endpoints. Mounted under prefix /admin and gated by require_admin."""
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import require_admin
from healthflow.auth.tenant_context import system_context
from healthflow.database.config import get_db
from healthflow.database.models import AgentInvocationLog, Broker, Client
from healthflow.logs.audit import AuditLogger

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/brokers")
async def list_brokers(
    _admin: Broker = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List every broker in the workspace with lock + book-size info.

    Admin-only. Used by the admin UI to render the team table + lock
    actions. Returns one row per broker; client_count is a LEFT JOIN
    so brokers with zero clients still appear.
    """
    stmt = (
        select(
            Broker.id,
            Broker.email,
            Broker.full_name,
            Broker.role,
            Broker.is_active,
            Broker.failed_login_count,
            Broker.locked_until,
            Broker.created_at,
            func.count(Client.id).label("client_count"),
        )
        .outerjoin(Client, Client.broker_id == Broker.id)
        .group_by(Broker.id)
        .order_by(Broker.created_at)
    )
    # Joining Client (tenant-scoped) would otherwise be auto-filtered to the
    # admin's own broker_id and drop everyone else. The whole point of this
    # listing is cross-broker visibility.
    with system_context("admin: list workspace brokers"):
        rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(r.id),
            "email": r.email,
            "full_name": r.full_name,
            "role": r.role,
            "is_active": r.is_active,
            "failed_login_count": r.failed_login_count,
            "locked_until": r.locked_until.isoformat() if r.locked_until else None,
            "created_at": r.created_at.isoformat(),
            "client_count": r.client_count,
        }
        for r in rows
    ]


@admin_router.get("/audit/recent")
async def recent_audit(
    limit: int = Query(20, ge=1, le=100),
    _admin: Broker = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Recent agent-invocation log entries enriched with broker email.

    Backs the admin page's audit-log panel. Read-only; no PHI is
    surfaced — the log row's `details` JSON contains operational
    metadata only (model, duration, endpoint).
    """
    stmt = (
        select(AgentInvocationLog, Broker.email)
        .outerjoin(Broker, Broker.id == AgentInvocationLog.broker_id)
        .order_by(desc(AgentInvocationLog.created_at))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(log.id),
            "agent": log.agent,
            "endpoint": log.endpoint,
            "event_type": log.event_type,
            "model_used": log.model_used,
            "duration_ms": log.duration_ms,
            "broker_email": email,
            "broker_id": str(log.broker_id) if log.broker_id else None,
            "case_id": str(log.case_id) if log.case_id else None,
            "error": log.error,
            "created_at": log.created_at.isoformat(),
        }
        for log, email in rows
    ]


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
