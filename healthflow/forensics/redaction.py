"""Output redaction for forensics timelines.

Defense-in-depth: agents should never write PHI to `details` in the first
place (that's the contract documented in healthflow-security skill). But
forensics is a high-trust read surface, so we run every string-valued
output field through PHIRedactor before returning.
"""
from healthflow.forensics.schemas import AgentInvocation, CaseTimeline
from healthflow.tools.phi_redactor import PHIRedactor

_DETAILS_SUMMARY_MAX = 200
_redactor = PHIRedactor()


def _redact_text(text: str) -> str:
    redacted, _ = _redactor.redact(text)
    return redacted


def _redact_invocation(inv: AgentInvocation) -> AgentInvocation:
    summary = _redact_text(inv.details_summary)[:_DETAILS_SUMMARY_MAX]
    error = _redact_text(inv.error) if inv.error else None
    return inv.model_copy(update={"details_summary": summary, "error": error})


def redact(timeline: CaseTimeline) -> CaseTimeline:
    """Walk the timeline, redact PHI patterns from every string field, truncate
    long summaries. Returns a NEW CaseTimeline; does not mutate the input."""
    redacted_invocations = [_redact_invocation(i) for i in timeline.invocations]
    return timeline.model_copy(update={"invocations": redacted_invocations})
