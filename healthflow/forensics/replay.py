"""Read-only forensics query functions over agent_invocation_log + phi_access_log.

Each function:
  1. Opens a session via the passed-in async_sessionmaker.
  2. Filters by `broker_id = tenant_id` (cross-tenant isolation).
  3. Joins to phi_access_log on (broker_id, created_at ± PHI_JOIN_WINDOW).
  4. Runs integrity.check() → IntegrityCheck.
  5. Passes the output through redaction.redact().
  6. Writes exactly one ForensicsAccessLog row.
  7. Returns the timeline (or empty for cross-tenant / no-data cases).
"""
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.database.models import (
    AgentInvocationLog,
    ForensicsAccessLog,
    PhiAccessLog,
)
from healthflow.forensics import integrity as integrity_mod
from healthflow.forensics import redaction as redaction_mod
from healthflow.forensics.schemas import (
    AgentInvocation,
    CaseTimeline,
    IntegrityCheck,
)

# Window for joining agent invocations to PHI access records. Empirically,
# an agent's invocation_log row and its first DB read land within ~1s.
PHI_JOIN_WINDOW = timedelta(seconds=2)

# `details_summary` max chars after redaction.
DETAILS_SUMMARY_MAX = 200


async def replay_case(
    case_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> CaseTimeline:
    async with session_factory() as session:
        rows = (await session.execute(
            select(AgentInvocationLog)
            .where(
                AgentInvocationLog.case_id == case_id,
                AgentInvocationLog.broker_id == tenant_id,
            )
            .order_by(AgentInvocationLog.created_at.asc())
        )).scalars().all()

        invocations = await _enrich_with_phi(session, rows, tenant_id)
        time_range = _time_range(rows)

        integrity = integrity_mod.check(invocations, scope="case", scope_key=str(case_id))
        timeline = CaseTimeline(
            case_id=case_id,
            tenant_id=tenant_id,
            time_range=time_range,
            invocations=invocations,
            decision_chain=[i.event_type for i in invocations],
            integrity=integrity,
        )
        timeline = redaction_mod.redact(timeline)

        await _write_self_audit(
            session,
            operator_id=tenant_id,
            mode="case",
            scope_key=str(case_id),
            tenant_id=tenant_id,
            from_ts=None,
            to_ts=None,
            result_count=len(invocations),
        )
        await session.commit()
        return timeline


# ── helpers ───────────────────────────────────────────────────────────────


async def _enrich_with_phi(
    session, rows: list[AgentInvocationLog], tenant_id: uuid.UUID
) -> list[AgentInvocation]:
    """For each invocation, attach phi_tables_touched + phi_row_count from
    PhiAccessLog rows within PHI_JOIN_WINDOW for the same broker."""
    out: list[AgentInvocation] = []
    for r in rows:
        window_start = r.created_at - PHI_JOIN_WINDOW
        window_end = r.created_at + PHI_JOIN_WINDOW
        phi_rows = (await session.execute(
            select(PhiAccessLog).where(
                PhiAccessLog.broker_id == tenant_id,
                PhiAccessLog.created_at >= window_start,
                PhiAccessLog.created_at <= window_end,
            )
        )).scalars().all()

        tables = sorted({p.table_name for p in phi_rows})
        row_count = sum(p.row_count for p in phi_rows)

        details_summary = json.dumps(r.details or {})[:DETAILS_SUMMARY_MAX]

        out.append(AgentInvocation(
            agent=r.agent,
            invocation_id=r.id,
            timestamp=r.created_at,
            case_id=r.case_id,
            endpoint=r.endpoint,
            event_type=r.event_type,
            model_used=r.model_used,
            duration_ms=r.duration_ms,
            details_summary=details_summary,
            error=r.error,
            phi_tables_touched=tables,
            phi_row_count=row_count,
        ))
    return out


def _time_range(rows: list[AgentInvocationLog]) -> tuple[datetime, datetime] | None:
    if not rows:
        return None
    return (rows[0].created_at, rows[-1].created_at)


async def _write_self_audit(
    session,
    *,
    operator_id: uuid.UUID,
    mode: str,
    scope_key: str,
    tenant_id: uuid.UUID | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
    result_count: int,
) -> None:
    session.add(ForensicsAccessLog(
        operator_id=operator_id,
        mode=mode,
        scope_key=scope_key,
        tenant_id=tenant_id,
        from_ts=from_ts,
        to_ts=to_ts,
        result_count=result_count,
    ))
