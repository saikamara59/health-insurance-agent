"""Unit tests for the pure-function deadline engine. No network, no LLM.

Coverage: every event type, urgency thresholds, edge cases (boundaries,
leap years, wrap-around to next year's enrollment window).
"""
from datetime import date

import pytest

from healthflow.agents.temporal_awareness.deadline_engine import (
    compute_deadline,
    compute_urgency,
)
from healthflow.agents.temporal_awareness.schemas import EventType


# ── Urgency thresholds ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "days_remaining,expected",
    [
        (-1, "critical"),    # past deadline still reports critical (caller decides what to do)
        (0, "critical"),
        (3, "critical"),
        (7, "critical"),
        (8, "high"),
        (14, "high"),
        (15, "medium"),
        (30, "medium"),
        (31, "low"),
        (365, "low"),
    ],
)
def test_urgency_thresholds(days_remaining, expected):
    assert compute_urgency(days_remaining) == expected


# ── Open Enrollment (Nov 1 – Jan 15) ─────────────────────────────────────────


def test_oe_during_window_returns_current_year_deadline():
    info = compute_deadline(
        EventType.OPEN_ENROLLMENT, trigger_date=date(2026, 11, 15), today=date(2026, 11, 15)
    )
    assert info.deadline == date(2027, 1, 15)
    assert info.days_remaining == 61


def test_oe_in_december_uses_jan_15_of_next_year():
    info = compute_deadline(
        EventType.OPEN_ENROLLMENT, trigger_date=date(2026, 12, 20), today=date(2026, 12, 20)
    )
    assert info.deadline == date(2027, 1, 15)
    assert info.days_remaining == 26


def test_oe_in_early_january_inside_window():
    info = compute_deadline(
        EventType.OPEN_ENROLLMENT, trigger_date=date(2027, 1, 10), today=date(2027, 1, 10)
    )
    assert info.deadline == date(2027, 1, 15)
    assert info.days_remaining == 5
    assert info.urgency == "critical"


def test_oe_outside_window_targets_next_open_enrollment():
    # Mid-summer: next OE deadline is Jan 15 of the following year.
    info = compute_deadline(
        EventType.OPEN_ENROLLMENT, trigger_date=date(2026, 7, 1), today=date(2026, 7, 1)
    )
    assert info.deadline == date(2027, 1, 15)
    assert info.days_remaining == 198
    assert info.urgency == "low"


# ── Medicare AEP (Oct 15 – Dec 7) ────────────────────────────────────────────


def test_aep_during_window():
    info = compute_deadline(
        EventType.MEDICARE_AEP, trigger_date=date(2026, 10, 20), today=date(2026, 10, 20)
    )
    assert info.deadline == date(2026, 12, 7)
    assert info.days_remaining == 48


def test_aep_outside_window_targets_next_aep():
    info = compute_deadline(
        EventType.MEDICARE_AEP, trigger_date=date(2026, 3, 1), today=date(2026, 3, 1)
    )
    assert info.deadline == date(2026, 12, 7)
    assert info.days_remaining == 281


def test_aep_after_dec_7_targets_next_year():
    info = compute_deadline(
        EventType.MEDICARE_AEP, trigger_date=date(2026, 12, 8), today=date(2026, 12, 8)
    )
    assert info.deadline == date(2027, 12, 7)
    assert info.days_remaining == 364


# ── Special Enrollment Period (60-day window) ────────────────────────────────


@pytest.mark.parametrize(
    "event_type",
    [
        EventType.SEP_JOB_LOSS,
        EventType.SEP_MARRIAGE,
        EventType.SEP_BIRTH,
        EventType.SEP_MOVE,
        EventType.SEP_DIVORCE,
    ],
)
def test_sep_deadline_is_60_days_from_trigger(event_type):
    info = compute_deadline(
        event_type, trigger_date=date(2026, 5, 1), today=date(2026, 5, 1)
    )
    assert info.deadline == date(2026, 6, 30)
    assert info.days_remaining == 60
    assert info.urgency == "low"


def test_sep_with_recent_trigger_is_high_urgency():
    info = compute_deadline(
        EventType.SEP_JOB_LOSS, trigger_date=date(2026, 5, 1), today=date(2026, 6, 20)
    )
    assert info.deadline == date(2026, 6, 30)
    assert info.days_remaining == 10
    assert info.urgency == "high"


def test_sep_past_deadline_reports_negative_days():
    info = compute_deadline(
        EventType.SEP_MARRIAGE, trigger_date=date(2026, 1, 1), today=date(2026, 4, 1)
    )
    assert info.deadline == date(2026, 3, 2)
    assert info.days_remaining < 0
    assert info.urgency == "critical"


# ── Prior Authorization appeal windows (plan-type dependent) ─────────────────


def test_pa_appeal_hmo_is_60_days():
    info = compute_deadline(
        EventType.PA_APPEAL,
        trigger_date=date(2026, 5, 1),
        today=date(2026, 5, 1),
        plan_type="HMO",
    )
    assert info.deadline == date(2026, 6, 30)
    assert info.days_remaining == 60


def test_pa_appeal_ppo_is_180_days():
    info = compute_deadline(
        EventType.PA_APPEAL,
        trigger_date=date(2026, 5, 1),
        today=date(2026, 5, 1),
        plan_type="PPO",
    )
    assert info.deadline == date(2026, 10, 28)
    assert info.days_remaining == 180


def test_pa_appeal_epo_pos_use_default_window():
    """EPO and POS aren't in the canonical {HMO, PPO, MA} buckets; default to 120."""
    info = compute_deadline(
        EventType.PA_APPEAL,
        trigger_date=date(2026, 5, 1),
        today=date(2026, 5, 1),
        plan_type="EPO",
    )
    assert info.deadline == date(2026, 8, 29)
    assert info.days_remaining == 120


def test_pa_appeal_without_plan_type_falls_back_to_default():
    info = compute_deadline(
        EventType.PA_APPEAL, trigger_date=date(2026, 5, 1), today=date(2026, 5, 1)
    )
    assert info.days_remaining == 120


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_leap_year_sep_window_includes_feb_29():
    info = compute_deadline(
        EventType.SEP_MOVE, trigger_date=date(2028, 1, 1), today=date(2028, 1, 1)
    )
    # 2028 is a leap year — 60 days from Jan 1 is March 1 (Feb has 29 days).
    assert info.deadline == date(2028, 3, 1)
    assert info.days_remaining == 60


def test_oe_on_first_day_of_window():
    """Nov 1 is the first day of OE — deadline should be Jan 15 of next year."""
    info = compute_deadline(
        EventType.OPEN_ENROLLMENT, trigger_date=date(2026, 11, 1), today=date(2026, 11, 1)
    )
    assert info.deadline == date(2027, 1, 15)


def test_oe_on_last_day_of_window():
    """Jan 15 is the last day — days_remaining is 0; urgency critical."""
    info = compute_deadline(
        EventType.OPEN_ENROLLMENT, trigger_date=date(2027, 1, 15), today=date(2027, 1, 15)
    )
    assert info.deadline == date(2027, 1, 15)
    assert info.days_remaining == 0
    assert info.urgency == "critical"


def test_compute_deadline_returns_event_type_unchanged():
    info = compute_deadline(
        EventType.SEP_BIRTH, trigger_date=date(2026, 5, 1), today=date(2026, 5, 1)
    )
    assert info.event_type == EventType.SEP_BIRTH
    assert info.trigger_date == date(2026, 5, 1)
