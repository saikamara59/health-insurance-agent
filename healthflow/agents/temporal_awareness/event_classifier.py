"""Natural-language → ClassifiedEvent via Claude Haiku, with PHI redaction.

PHI is stripped at the boundary BEFORE the LLM sees the text. The classifier
never logs the description; only the classification result reaches the
audit stream (and even that omits the trigger_date when it's a date — that's
the agent layer's call).
"""
import json
from datetime import date

import anthropic

from healthflow.agents.harness import CLAUDE_CLASSIFIER_MODEL, extract_text
from healthflow.agents.temporal_awareness.schemas import ClassifiedEvent, EventType
from healthflow.tools.phi_redactor import PHIRedactor


_SYSTEM_PROMPT = (
    "You classify health insurance events for a deadline-aware planning tool. "
    "Given a short description, output a single JSON object with keys: "
    "`event_type` (one of: open_enrollment, medicare_aep, sep_job_loss, "
    "sep_marriage, sep_birth, sep_move, sep_divorce, pa_appeal), "
    "`trigger_date` (ISO YYYY-MM-DD), and optionally `plan_type` "
    "(HMO/PPO/EPO/POS/MA) for PA appeals. "
    "If the description doesn't specify a date, use `today_iso` from the prompt. "
    "Output ONLY the JSON object — no prose, no markdown fences."
)


class EventClassifier:
    """Wraps the Claude Haiku call. PHI-redacted input; structured output."""

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic()
        self._redactor = PHIRedactor()

    def classify(self, description: str, today: date) -> ClassifiedEvent:
        redacted_text, _ = self._redactor.redact(description)

        user_message = (
            f"today_iso: {today.isoformat()}\n"
            f"description: {redacted_text}"
        )

        response = self._client.messages.create(
            model=CLAUDE_CLASSIFIER_MODEL,
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = extract_text(response).strip()
        if not raw:
            raise ValueError("Classifier returned empty text")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Classifier returned non-JSON output: {raw[:200]!r}") from e

        # Normalize event_type to the enum (the model returns the string value).
        if "event_type" in parsed and not isinstance(parsed["event_type"], EventType):
            try:
                parsed["event_type"] = EventType(parsed["event_type"])
            except ValueError as e:
                raise ValueError(f"Classifier returned unknown event_type: {parsed.get('event_type')!r}") from e

        return ClassifiedEvent.model_validate(parsed)
