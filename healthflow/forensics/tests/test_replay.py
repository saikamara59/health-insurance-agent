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


@pytest.mark.asyncio
async def test_replay_member_joins_through_phi_access_log(db_session, db_session_factory):
    """A member-scope query finds invocations whose ±2s PHI access includes the client_id."""
    tenant = uuid.uuid4()
    client = uuid.uuid4()
    other_client = uuid.uuid4()

    inv = make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0)
    # PHI access for `client` at the same timestamp — matches.
    phi_hit = make_phi_access(broker_id=tenant, row_ids=[str(client), str(other_client)], timestamp=_T0)
    # Unrelated invocation (no PHI access for `client`).
    unrelated = make_invocation(broker_id=tenant, agent="translation", timestamp=_T0 + timedelta(minutes=10))
    await _seed(db_session, [inv, phi_hit, unrelated])

    from healthflow.forensics.replay import replay_member
    timeline = await replay_member(
        client,
        time_range=(_T0 - timedelta(seconds=10), _T0 + timedelta(minutes=20)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    assert len(timeline.invocations) == 1
    assert timeline.invocations[0].agent == "comparison"
    assert timeline.member_id_hash is not None  # SHA-256 prefix
    assert str(client) not in timeline.member_id_hash  # never the raw value


@pytest.mark.asyncio
async def test_replay_member_honors_time_range(db_session, db_session_factory):
    tenant = uuid.uuid4()
    client = uuid.uuid4()
    inv_in = make_invocation(broker_id=tenant, timestamp=_T0)
    phi_in = make_phi_access(broker_id=tenant, row_ids=[str(client)], timestamp=_T0)
    inv_out = make_invocation(broker_id=tenant, timestamp=_T0 + timedelta(days=5))
    phi_out = make_phi_access(broker_id=tenant, row_ids=[str(client)], timestamp=_T0 + timedelta(days=5))
    await _seed(db_session, [inv_in, phi_in, inv_out, phi_out])

    from healthflow.forensics.replay import replay_member
    timeline = await replay_member(
        client,
        time_range=(_T0 - timedelta(hours=1), _T0 + timedelta(hours=1)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    assert len(timeline.invocations) == 1
    assert timeline.invocations[0].timestamp == _T0


@pytest.mark.asyncio
async def test_replay_agent_filters_by_agent_and_time(db_session, db_session_factory):
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0),
        make_invocation(broker_id=tenant, agent="network", timestamp=_T0 + timedelta(seconds=10)),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(seconds=20)),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(days=10)),  # out of range
    ])

    from healthflow.forensics.replay import replay_agent
    invocations = await replay_agent(
        "comparison",
        time_range=(_T0 - timedelta(seconds=1), _T0 + timedelta(hours=1)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    assert len(invocations) == 2
    assert all(i.agent == "comparison" for i in invocations)


@pytest.mark.asyncio
async def test_replay_agent_returns_chronological_order(db_session, db_session_factory):
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(seconds=30)),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(seconds=15)),
    ])

    from healthflow.forensics.replay import replay_agent
    invocations = await replay_agent(
        "comparison",
        time_range=(_T0 - timedelta(seconds=1), _T0 + timedelta(hours=1)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    timestamps = [i.timestamp for i in invocations]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_all_three_functions_write_one_self_audit_row_each(db_session, db_session_factory):
    """Sanity check: every replay call writes exactly one ForensicsAccessLog row."""
    tenant = uuid.uuid4()
    client = uuid.uuid4()
    case = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(broker_id=tenant, case_id=case, timestamp=_T0),
        make_phi_access(broker_id=tenant, row_ids=[str(client)], timestamp=_T0),
    ])

    from healthflow.forensics.replay import replay_case, replay_member, replay_agent
    await replay_case(case, tenant_id=tenant, session_factory=db_session_factory)
    await replay_member(client, time_range=(_T0 - timedelta(hours=1), _T0 + timedelta(hours=1)), tenant_id=tenant, session_factory=db_session_factory)
    await replay_agent("comparison", time_range=(_T0 - timedelta(hours=1), _T0 + timedelta(hours=1)), tenant_id=tenant, session_factory=db_session_factory)

    rows = (await db_session.execute(select(ForensicsAccessLog))).scalars().all()
    assert {r.mode for r in rows} == {"case", "member", "agent"}
    assert len(rows) == 3
