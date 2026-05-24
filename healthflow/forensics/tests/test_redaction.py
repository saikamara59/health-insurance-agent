"""Defense-in-depth: redact PHI patterns from forensics output before return."""
import uuid
from datetime import datetime, timezone

from healthflow.forensics.redaction import redact
from healthflow.forensics.schemas import (
    AgentInvocation,
    CaseTimeline,
    IntegrityCheck,
)


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _timeline_with_details(details_summary: str) -> CaseTimeline:
    inv = AgentInvocation(
        agent="appeal",
        invocation_id=uuid.uuid4(),
        timestamp=_T0,
        case_id=uuid.uuid4(),
        endpoint="/appeal",
        event_type="process_appeal",
        details_summary=details_summary,
    )
    return CaseTimeline(
        tenant_id=uuid.uuid4(),
        invocations=[inv],
        integrity=IntegrityCheck(entries_found=1),
    )


def test_redacts_ssn_pattern_in_details_summary():
    raw = "Patient: John Doe SSN 123-45-6789 visited"
    timeline = _timeline_with_details(raw)
    out = redact(timeline)
    summary = out.invocations[0].details_summary
    assert "123-45-6789" not in summary
    assert "[SSN]" in summary or "[REDACTED]" in summary.upper()


def test_redacts_patient_name_label():
    raw = "Patient: Jane Smith was treated for"
    timeline = _timeline_with_details(raw)
    out = redact(timeline)
    summary = out.invocations[0].details_summary
    assert "Jane Smith" not in summary


def test_truncates_details_summary_to_200_chars():
    raw = "x" * 500
    timeline = _timeline_with_details(raw)
    out = redact(timeline)
    assert len(out.invocations[0].details_summary) <= 200
