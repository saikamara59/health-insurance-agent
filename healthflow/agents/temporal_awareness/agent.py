"""TemporalAwarenessAgent — the orchestrator.

Flow:
  1. If the caller provided a structured `event`, use it.
     Otherwise hand the `description` to the Haiku classifier.
  2. Pass the (event_type, trigger_date, plan_type) into the pure-function
     deadline engine to compute deadline + days_remaining + urgency.
  3. Call Sonnet to generate a list of dated `Action` steps appropriate to
     the event type and urgency.
  4. Emit ONE audit entry. Zero PHI in the entry — only event metadata,
     timestamps, and agent id.

Matches the shape of `comparison_agent.py` (no base class; each agent owns
its own `anthropic.Anthropic()` and `AuditLogger`).
"""
import json
from datetime import date

import anthropic

from healthflow.agents.harness import CLAUDE_MODEL, extract_text, strip_code_fence
from healthflow.agents.temporal_awareness.deadline_engine import (
    DeadlineInfo,
    compute_deadline,
)
from healthflow.agents.temporal_awareness.event_classifier import EventClassifier
from healthflow.agents.temporal_awareness.schemas import (
    Action,
    ActionPlan,
    TemporalRequest,
)
from healthflow.logs.audit import AuditLogger


_AGENT_ID = "temporal_awareness"

_ACTION_SYSTEM_PROMPT = (
    "You generate concrete, dated action steps for a health insurance "
    "deadline. Given the event type, the deadline date, and how many days "
    "remain, output a JSON array of 3-6 action objects. Each object has: "
    "`step` (1-indexed int), `description` (one short imperative sentence, "
    "no second person you/yours), and `target_date` (ISO YYYY-MM-DD between "
    "today and the deadline). Output ONLY the JSON array, no prose."
)


class TemporalAwarenessAgent:
    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        classifier: EventClassifier | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic()
        # Re-use the same Anthropic client for the classifier so tests only
        # need to mock one object.
        self._classifier = classifier or EventClassifier(client=self._client)
        self.audit = AuditLogger()

    def generate_plan(self, request: TemporalRequest) -> ActionPlan:
        today = request.today or date.today()

        if request.event is not None:
            event = request.event
        else:
            assert request.description is not None  # model_validator guarantees this
            event = self._classifier.classify(request.description, today=today)

        info = compute_deadline(
            event_type=event.event_type,
            trigger_date=event.trigger_date,
            today=today,
            plan_type=event.plan_type,
        )
        actions = self._generate_actions(info, today)

        plan = ActionPlan(
            event_type=info.event_type,
            trigger_date=info.trigger_date,
            deadline=info.deadline,
            days_remaining=info.days_remaining,
            urgency=info.urgency,
            actions=actions,
        )
        self._audit(plan, today, source="structured" if request.event else "natural_language")
        return plan

    def _generate_actions(self, info: DeadlineInfo, today: date) -> list[Action]:
        user_message = (
            f"event_type: {info.event_type.value}\n"
            f"today: {today.isoformat()}\n"
            f"deadline: {info.deadline.isoformat()}\n"
            f"days_remaining: {info.days_remaining}\n"
            f"urgency: {info.urgency}\n"
        )

        response = self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=_ACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = strip_code_fence(extract_text(response))
        if not raw:
            raise ValueError("Action-plan generator returned empty text")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Action-plan generator returned non-JSON: {raw[:200]!r}") from e

        if not isinstance(parsed, list):
            raise ValueError(f"Action-plan generator returned non-array: {type(parsed).__name__}")

        return [Action.model_validate(a) for a in parsed]

    def _audit(self, plan: ActionPlan, today: date, *, source: str) -> None:
        """One entry per invocation. Zero PHI — event metadata only."""
        self.audit.log("temporal_plan_generated", {
            "agent": _AGENT_ID,
            "event_type": plan.event_type.value,
            "trigger_date": plan.trigger_date.isoformat(),
            "deadline": plan.deadline.isoformat(),
            "days_remaining": plan.days_remaining,
            "urgency": plan.urgency,
            "action_count": len(plan.actions),
            "today": today.isoformat(),
            "input_source": source,
        })
