"""Tests for replay_case / replay_member / replay_agent.

Tests pass in db_session_factory (the shared in-memory SQLite from conftest)
so the forensics functions can open their own sessions to seed + query.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from healthflow.database.models import ForensicsAccessLog
from healthflow.forensics.replay import replay_case
from healthflow.forensics.tests.fixtures import make_invocation, make_phi_access


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _seed(db_session, rows):
    for r in rows:
        db_session.add(r)
    await db_session.commit()


@pytest.mark.asyncio
async def test_replay_case_returns_chronological_invocations(db_session, db_session_factory):
    """Invocations for a case_id come back in created_at order."""
    case = uuid.uuid4()
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(case_id=case, broker_id=tenant, agent="comparison", event_type="recommend", timestamp=_T0 + timedelta(seconds=20)),
        make_invocation(case_id=case, broker_id=tenant, agent="harness", event_type="input_validated", timestamp=_T0),
        make_invocation(case_id=case, broker_id=tenant, agent="network", event_type="verify", timestamp=_T0 + timedelta(seconds=40)),
    ])

    timeline = await replay_case(case, tenant_id=tenant, session_factory=db_session_factory)

    assert timeline.case_id == case
    assert timeline.tenant_id == tenant
    assert len(timeline.invocations) == 3
    assert [i.agent for i in timeline.invocations] == ["harness", "comparison", "network"]
    assert timeline.decision_chain == ["input_validated", "recommend", "verify"]


@pytest.mark.asyncio
async def test_replay_case_cross_tenant_returns_empty(db_session, db_session_factory):
    """A case belonging to tenant A queried as tenant B → empty timeline (no info leak)."""
    case = uuid.uuid4()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(case_id=case, broker_id=tenant_a, timestamp=_T0),
    ])

    timeline = await replay_case(case, tenant_id=tenant_b, session_factory=db_session_factory)

    assert timeline.invocations == []
    assert timeline.decision_chain == []


@pytest.mark.asyncio
async def test_replay_case_writes_one_self_audit_row(db_session, db_session_factory):
    case = uuid.uuid4()
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(case_id=case, broker_id=tenant, timestamp=_T0),
    ])

    await replay_case(case, tenant_id=tenant, session_factory=db_session_factory)

    rows = (await db_session.execute(select(ForensicsAccessLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].mode == "case"
    assert rows[0].scope_key == str(case)
    assert rows[0].tenant_id == tenant
    assert rows[0].result_count == 1
    assert rows[0].operator_id == tenant  # operator defaults to the calling tenant_id
