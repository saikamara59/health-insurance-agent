"""Integrity checks for forensics timelines.

Four passes:
  1. Chronological gaps within a case scope — note any gap > 5 minutes.
  2. Error clusters — 3+ consecutive non-null errors → flag.
  3. Missing case_id under case scope — would mean a row matched the case
     filter but reports no case_id; should be impossible. Flag if seen.
  4. tamper_evidence — always "unknown" until a hash-chain ships.
"""
from datetime import timedelta

from healthflow.forensics.schemas import AgentInvocation, IntegrityCheck


_GAP_THRESHOLD = timedelta(minutes=5)
_ERROR_CLUSTER_MIN = 3


def check(
    invocations: list[AgentInvocation],
    *,
    scope: str,
    scope_key: str,
) -> IntegrityCheck:
    gaps: list[str] = []
    notes: list[str] = []

    # 1 — chronological gaps
    for i in range(1, len(invocations)):
        delta = invocations[i].timestamp - invocations[i - 1].timestamp
        if delta > _GAP_THRESHOLD:
            notes.append(
                f"{int(delta.total_seconds())}s gap between invocations "
                f"{i} and {i + 1} (over {int(_GAP_THRESHOLD.total_seconds())}s threshold)"
            )

    # 2 — error clusters
    run_start: int | None = None
    for i, inv in enumerate(invocations):
        if inv.error:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= _ERROR_CLUSTER_MIN:
                gaps.append(f"error cluster: invocations {run_start + 1}..{i} all failed")
            run_start = None
    # Flush trailing run.
    if run_start is not None and (len(invocations) - run_start) >= _ERROR_CLUSTER_MIN:
        gaps.append(
            f"error cluster: invocations {run_start + 1}..{len(invocations)} all failed"
        )

    # 3 — case scope: invocations with no case_id shouldn't have matched
    if scope == "case":
        for i, inv in enumerate(invocations):
            if inv.case_id is None:
                gaps.append(
                    f"invocation {i + 1} ({inv.invocation_id}) matched case scope "
                    f"but has no case_id"
                )

    # 4 — tamper evidence: future hash-chain work
    return IntegrityCheck(
        entries_found=len(invocations),
        gaps_detected=gaps,
        tamper_evidence="unknown",
        notes=notes,
    )
