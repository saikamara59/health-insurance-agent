"""Synthetic AgentInvocationLog + PhiAccessLog row builders for forensics tests.

No live PHI. Every helper accepts overrides for the fields that matter to a
given test; defaults are deterministic so test output is stable.
"""
import uuid
from datetime import datetime, timezone

from healthflow.database.models import AgentInvocationLog, PhiAccessLog


_BASE = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_invocation(
    *,
    agent: str = "comparison",
    event_type: str = "recommend",
    broker_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None = None,
    endpoint: str = "/compare",
    timestamp: datetime | None = None,
    model_used: str | None = "claude-sonnet-4-6",
    duration_ms: int | None = 250,
    details: dict | None = None,
    error: str | None = None,
) -> AgentInvocationLog:
    return AgentInvocationLog(
        id=uuid.uuid4(),
        case_id=case_id,
        broker_id=broker_id,
        endpoint=endpoint,
        agent=agent,
        event_type=event_type,
        model_used=model_used,
        duration_ms=duration_ms,
        details=details if details is not None else {"length": 42},
        error=error,
        created_at=timestamp or _BASE,
    )


def make_phi_access(
    *,
    broker_id: uuid.UUID | None = None,
    table_name: str = "clients",
    operation: str = "select",
    row_ids: list[str] | None = None,
    endpoint: str = "/compare",
    timestamp: datetime | None = None,
) -> PhiAccessLog:
    return PhiAccessLog(
        id=uuid.uuid4(),
        broker_id=broker_id,
        table_name=table_name,
        operation=operation,
        row_ids=row_ids or [],
        row_count=len(row_ids) if row_ids else 0,
        endpoint=endpoint,
        created_at=timestamp or _BASE,
    )
