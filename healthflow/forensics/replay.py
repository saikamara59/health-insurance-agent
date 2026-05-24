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
from datetime import datetime, timedelta, timezone

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
            timestamp=_ensure_utc(r.created_at),
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
    return (_ensure_utc(rows[0].created_at), _ensure_utc(rows[-1].created_at))


def _ensure_utc(ts: datetime) -> datetime:
    """SQLite strips tzinfo from `DateTime(timezone=True)` columns; reattach UTC
    so downstream consumers always see tz-aware timestamps (the column's contract)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


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


async def replay_member(
    client_id: uuid.UUID,
    *,
    time_range: tuple[datetime, datetime],
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> CaseTimeline:
    """Reconstruct the timeline of agent invocations that accessed this client.

    Two-step join: find phi_access_log rows containing this client_id within
    the time range, then pull agent_invocation_log rows ±PHI_JOIN_WINDOW
    around each PHI access (same broker = tenant_id).
    """
    from_ts, to_ts = time_range
    async with session_factory() as session:
        # Step 1: find PHI accesses that touched this client.
        # SQLAlchemy can't easily express "client_id_str in row_ids JSON list"
        # portably across SQLite/Postgres, so we scan candidate rows by
        # (broker_id, time_range) and filter in Python.
        client_id_str = str(client_id)
        phi_candidates = (await session.execute(
            select(PhiAccessLog).where(
                PhiAccessLog.broker_id == tenant_id,
                PhiAccessLog.created_at >= from_ts,
                PhiAccessLog.created_at <= to_ts,
            )
        )).scalars().all()
        matching_phi = [p for p in phi_candidates if client_id_str in (p.row_ids or [])]

        # Step 2: pull invocations within ±PHI_JOIN_WINDOW of each matching access.
        invocations_rows: list[AgentInvocationLog] = []
        seen_ids: set[uuid.UUID] = set()
        for phi in matching_phi:
            window_start = phi.created_at - PHI_JOIN_WINDOW
            window_end = phi.created_at + PHI_JOIN_WINDOW
            inv_rows = (await session.execute(
                select(AgentInvocationLog).where(
                    AgentInvocationLog.broker_id == tenant_id,
                    AgentInvocationLog.created_at >= window_start,
                    AgentInvocationLog.created_at <= window_end,
                ).order_by(AgentInvocationLog.created_at.asc())
            )).scalars().all()
            for row in inv_rows:
                if row.id not in seen_ids:
                    invocations_rows.append(row)
                    seen_ids.add(row.id)

        invocations_rows.sort(key=lambda r: r.created_at)

        invocations = await _enrich_with_phi(session, invocations_rows, tenant_id)
        integrity = integrity_mod.check(invocations, scope="member", scope_key=client_id_str)

        timeline = CaseTimeline(
            case_id=None,
            member_id_hash=_hash_client_id(client_id),
            tenant_id=tenant_id,
            time_range=(from_ts, to_ts),
            invocations=invocations,
            decision_chain=[i.event_type for i in invocations],
            integrity=integrity,
        )
        timeline = redaction_mod.redact(timeline)

        await _write_self_audit(
            session,
            operator_id=tenant_id,
            mode="member",
            scope_key=client_id_str,
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            result_count=len(invocations),
        )
        await session.commit()
        return timeline


async def replay_agent(
    agent: str,
    *,
    time_range: tuple[datetime, datetime],
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> list[AgentInvocation]:
    """Invocations of a specific agent within a time range, for one tenant."""
    from_ts, to_ts = time_range
    async with session_factory() as session:
        rows = (await session.execute(
            select(AgentInvocationLog).where(
                AgentInvocationLog.agent == agent,
                AgentInvocationLog.broker_id == tenant_id,
                AgentInvocationLog.created_at >= from_ts,
                AgentInvocationLog.created_at <= to_ts,
            ).order_by(AgentInvocationLog.created_at.asc())
        )).scalars().all()

        invocations = await _enrich_with_phi(session, rows, tenant_id)

        await _write_self_audit(
            session,
            operator_id=tenant_id,
            mode="agent",
            scope_key=agent,
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            result_count=len(invocations),
        )
        await session.commit()
        return invocations


def _hash_client_id(client_id: uuid.UUID) -> str:
    """SHA-256 prefix — sufficient for case correlation, not reversible."""
    import hashlib
    return hashlib.sha256(str(client_id).encode()).hexdigest()[:16]
