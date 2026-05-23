"""End-to-end demo for the Temporal Awareness Agent.

Run with:

    .venv/bin/python -m healthflow.agents.temporal_awareness.demo

Three synthetic scenarios are exercised against the real Anthropic API:
  1. Structured SEP event (job loss, 10 days into the 60-day window).
  2. Natural-language description: Medicare AEP shopping inside the window.
  3. Structured Prior-Authorization appeal for a PPO plan.

The demo passes `today=...` explicitly to each request so output stays
stable across runs.

PHI handling: scenario 2's description includes a fake patient label so
you can visually confirm the classifier strips it before the LLM call.
The audit log shows what the AuditLogger actually wrote — verify with
your eyes that no patient name or SSN ends up in those entries.
"""
from datetime import date

from dotenv import load_dotenv

# Standalone scripts don't go through main.py, so load .env explicitly so
# ANTHROPIC_API_KEY (and JWT_SECRET / PHI_ENCRYPTION_KEY for transitive imports)
# are visible. Existing process env wins.
load_dotenv(override=False)

from healthflow.agents.temporal_awareness.agent import TemporalAwarenessAgent  # noqa: E402
from healthflow.agents.temporal_awareness.schemas import (  # noqa: E402
    ActionPlan,
    ClassifiedEvent,
    EventType,
    TemporalRequest,
)


def _print_plan(scenario: str, plan: ActionPlan) -> None:
    bar = "─" * 70
    print(f"\n{bar}\n{scenario}\n{bar}")
    print(f"event_type:     {plan.event_type.value}")
    print(f"trigger_date:   {plan.trigger_date}")
    print(f"deadline:       {plan.deadline}")
    print(f"days_remaining: {plan.days_remaining}")
    print(f"urgency:        {plan.urgency}")
    print("actions:")
    for a in plan.actions:
        print(f"  {a.step}. [{a.target_date}] {a.description}")


def main() -> None:
    agent = TemporalAwarenessAgent()

    # ── Scenario 1: structured SEP event (job loss, 10 days into the window) ──
    plan1 = agent.generate_plan(TemporalRequest(
        event=ClassifiedEvent(
            event_type=EventType.SEP_JOB_LOSS,
            trigger_date=date(2026, 5, 1),
        ),
        today=date(2026, 5, 11),
    ))
    _print_plan("Scenario 1 — SEP: job loss, 10 days elapsed (50 days left)", plan1)

    # ── Scenario 2: natural-language during Medicare AEP ──────────────────────
    # Includes a fake patient label to exercise the PHI-redaction path.
    description = (
        "Patient: Margaret Wilson is looking for a Medicare Advantage plan "
        "for next year. She's currently on traditional Medicare and wants to "
        "switch before the deadline."
    )
    plan2 = agent.generate_plan(TemporalRequest(
        description=description,
        today=date(2026, 11, 15),
    ))
    _print_plan("Scenario 2 — Medicare AEP, natural language (PHI redacted)", plan2)

    # ── Scenario 3: PA appeal for a PPO plan (180-day window) ─────────────────
    plan3 = agent.generate_plan(TemporalRequest(
        event=ClassifiedEvent(
            event_type=EventType.PA_APPEAL,
            trigger_date=date(2026, 6, 1),
            plan_type="PPO",
        ),
        today=date(2026, 9, 1),
    ))
    _print_plan("Scenario 3 — PA appeal, PPO (180-day window, 92 days elapsed)", plan3)

    print("\nDemo complete. Tail healthflow.log to inspect the audit entries.")


if __name__ == "__main__":
    main()
