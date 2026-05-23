"""Pure-function deadline math for the Temporal Awareness Agent.

Zero LLM calls, zero side effects, zero I/O. Every public function is a
direct function of its inputs — easy to test, easy to reason about, and
the same input always produces the same output.

The engine returns `DeadlineInfo` (event_type / trigger_date / deadline /
days_remaining / urgency). The agent layer composes this with Claude-
generated action steps to build the final `ActionPlan`.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from healthflow.agents.temporal_awareness.schemas import (
    EventType,
    PlanType,
    Urgency,
    is_sep_event,
)


# ── Constants ────────────────────────────────────────────────────────────────

# Open Enrollment runs Nov 1 → Jan 15 (next year); the engine only needs the end.
_OE_END_MONTH, _OE_END_DAY = 1, 15

# Medicare AEP runs Oct 15 → Dec 7; again only the end matters here.
_AEP_END_MONTH, _AEP_END_DAY = 12, 7

_SEP_WINDOW_DAYS = 60

# PA appeal windows by plan type. Real CMS rules vary; these are the
# canonical demo values. HMOs run the tightest, PPOs the most generous.
_PA_APPEAL_DAYS_BY_PLAN: dict[str, int] = {
    "HMO": 60,
    "MA": 60,
    "PPO": 180,
}
_PA_APPEAL_DEFAULT_DAYS = 120  # POS, EPO, unknown


# ── DeadlineInfo (structural slice of ActionPlan, sans actions) ──────────────


@dataclass(frozen=True)
class DeadlineInfo:
    event_type: EventType
    trigger_date: date
    deadline: date
    days_remaining: int
    urgency: Urgency


# ── Urgency ──────────────────────────────────────────────────────────────────


def compute_urgency(days_remaining: int) -> Urgency:
    """Map days_remaining → categorical urgency.

    ≤7 critical; ≤14 high; ≤30 medium; else low. Past-deadline (negative)
    is treated as critical — the caller decides whether to surface an
    "already expired" message.
    """
    if days_remaining <= 7:
        return "critical"
    if days_remaining <= 14:
        return "high"
    if days_remaining <= 30:
        return "medium"
    return "low"


# ── Deadline computation ─────────────────────────────────────────────────────


def compute_deadline(
    event_type: EventType,
    trigger_date: date,
    today: date,
    plan_type: PlanType | None = None,
) -> DeadlineInfo:
    """Compute the deadline + urgency for an event.

    `today` is explicit so callers (tests, the demo, the route) can
    inject the reference date deterministically. The route layer defaults
    `today=date.today()` at the boundary.
    """
    if event_type == EventType.OPEN_ENROLLMENT:
        deadline = _next_open_enrollment_deadline(today)
    elif event_type == EventType.MEDICARE_AEP:
        deadline = _next_aep_deadline(today)
    elif is_sep_event(event_type):
        deadline = trigger_date + timedelta(days=_SEP_WINDOW_DAYS)
    elif event_type == EventType.PA_APPEAL:
        window = _PA_APPEAL_DAYS_BY_PLAN.get(plan_type or "", _PA_APPEAL_DEFAULT_DAYS)
        deadline = trigger_date + timedelta(days=window)
    else:  # pragma: no cover — exhaustive over EventType today
        raise ValueError(f"Unsupported event_type: {event_type!r}")

    days_remaining = (deadline - today).days
    return DeadlineInfo(
        event_type=event_type,
        trigger_date=trigger_date,
        deadline=deadline,
        days_remaining=days_remaining,
        urgency=compute_urgency(days_remaining),
    )


# ── Enrollment-window helpers ────────────────────────────────────────────────


def _next_open_enrollment_deadline(today: date) -> date:
    """The next Jan 15 OE deadline that hasn't passed.

    OE runs Nov 1 → Jan 15 of the following year. If today is within the
    window (Nov 1 to Jan 15), return the Jan 15 of the in-progress window.
    Otherwise return the next Jan 15.
    """
    in_window_end_this_year = date(today.year, _OE_END_MONTH, _OE_END_DAY)
    if today <= in_window_end_this_year:
        # Jan 1 - Jan 15: in the tail of last year's window
        return in_window_end_this_year
    # Otherwise next OE deadline is Jan 15 of next year
    return date(today.year + 1, _OE_END_MONTH, _OE_END_DAY)


def _next_aep_deadline(today: date) -> date:
    """The next Dec 7 AEP deadline that hasn't passed.

    AEP runs Oct 15 → Dec 7. If today is on or before Dec 7 of the
    current year, return this year's Dec 7. Otherwise return next year's.
    """
    in_window_end_this_year = date(today.year, _AEP_END_MONTH, _AEP_END_DAY)
    if today <= in_window_end_this_year:
        return in_window_end_this_year
    return date(today.year + 1, _AEP_END_MONTH, _AEP_END_DAY)
