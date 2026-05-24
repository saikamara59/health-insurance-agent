"""Tests for integrity.check — gap detection, error clusters, tamper evidence."""
import uuid
from datetime import datetime, timedelta, timezone

from healthflow.forensics.integrity import check
from healthflow.forensics.schemas import AgentInvocation


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _inv(*, ts: datetime, case_id=None, error=None, agent="comparison", event_type="recommend") -> AgentInvocation:
    return AgentInvocation(
        agent=agent,
        invocation_id=uuid.uuid4(),
        timestamp=ts,
        case_id=case_id,
        endpoint="/compare",
        event_type=event_type,
        model_used="claude-sonnet-4-6",
        duration_ms=200,
        details_summary="{}",
        error=error,
    )


def test_clean_timeline_has_no_gaps_or_notes():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case),
        _inv(ts=_T0 + timedelta(seconds=30), case_id=case),
        _inv(ts=_T0 + timedelta(seconds=60), case_id=case),
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert result.entries_found == 3
    assert result.gaps_detected == []
    assert result.notes == []
    assert result.tamper_evidence == "unknown"


def test_chronological_gap_over_5_minutes_is_noted():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case),
        _inv(ts=_T0 + timedelta(minutes=10), case_id=case),  # 10-minute gap
        _inv(ts=_T0 + timedelta(minutes=11), case_id=case),
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert any("gap" in n.lower() for n in result.notes)


def test_three_consecutive_errors_flagged_as_error_cluster():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case, error="RuntimeError: boom"),
        _inv(ts=_T0 + timedelta(seconds=10), case_id=case, error="RuntimeError: boom"),
        _inv(ts=_T0 + timedelta(seconds=20), case_id=case, error="RuntimeError: boom"),
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert any("error cluster" in g.lower() for g in result.gaps_detected)


def test_case_scope_with_invocation_missing_case_id_is_flagged():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case),
        _inv(ts=_T0 + timedelta(seconds=10), case_id=None),  # should be impossible
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert any("no case_id" in g.lower() for g in result.gaps_detected)


def test_tamper_evidence_is_always_unknown_for_now():
    """Until hash-chain ships, this PR returns 'unknown'."""
    result = check([], scope="case", scope_key=str(uuid.uuid4()))
    assert result.tamper_evidence == "unknown"
