"""Agent + classifier tests with a fully mocked Anthropic client. No network."""
import json
import logging
from datetime import date
from unittest.mock import MagicMock

import pytest

from healthflow.agents.temporal_awareness.agent import TemporalAwarenessAgent
from healthflow.agents.temporal_awareness.event_classifier import EventClassifier
from healthflow.agents.temporal_awareness.schemas import (
    ClassifiedEvent,
    EventType,
    TemporalRequest,
)


def _stub_response(text: str) -> MagicMock:
    """Build a fake anthropic response whose .content[0].text is `text`."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def _classifier_payload(event_type: str, trigger_date: str, plan_type: str | None = None) -> str:
    payload = {"event_type": event_type, "trigger_date": trigger_date}
    if plan_type:
        payload["plan_type"] = plan_type
    return json.dumps(payload)


def _actions_payload(target_dates: list[str]) -> str:
    return json.dumps([
        {"step": i + 1, "description": f"Step {i + 1} description", "target_date": d}
        for i, d in enumerate(target_dates)
    ])


# ── Agent: structured input path (no classifier call) ───────────────────────


def test_structured_input_skips_classifier_and_returns_plan():
    client = MagicMock()
    # Only ONE call — the action generator. Classifier shouldn't be invoked.
    client.messages.create.return_value = _stub_response(
        _actions_payload(["2026-06-15", "2026-06-25"])
    )

    agent = TemporalAwarenessAgent(client=client)
    plan = agent.generate_plan(TemporalRequest(
        event=ClassifiedEvent(event_type=EventType.SEP_JOB_LOSS, trigger_date=date(2026, 5, 1)),
        today=date(2026, 5, 1),
    ))

    assert plan.event_type == EventType.SEP_JOB_LOSS
    assert plan.deadline == date(2026, 6, 30)
    assert plan.days_remaining == 60
    assert plan.urgency == "low"
    assert len(plan.actions) == 2
    assert client.messages.create.call_count == 1, "structured input should not invoke the classifier"


def test_structured_input_passes_plan_type_to_pa_appeal():
    client = MagicMock()
    client.messages.create.return_value = _stub_response(_actions_payload(["2026-06-01"]))

    agent = TemporalAwarenessAgent(client=client)
    plan = agent.generate_plan(TemporalRequest(
        event=ClassifiedEvent(
            event_type=EventType.PA_APPEAL,
            trigger_date=date(2026, 5, 1),
            plan_type="PPO",
        ),
        today=date(2026, 5, 1),
    ))
    # PPO PA-appeal window is 180 days
    assert plan.deadline == date(2026, 10, 28)
    assert plan.days_remaining == 180


# ── Agent: natural-language path (classifier IS invoked) ────────────────────


def test_natural_language_invokes_classifier_then_action_generator():
    client = MagicMock()
    # First call: classifier (returns the classified event JSON)
    # Second call: action generator (returns the actions array)
    client.messages.create.side_effect = [
        _stub_response(_classifier_payload("sep_marriage", "2026-04-01")),
        _stub_response(_actions_payload(["2026-04-15", "2026-05-15"])),
    ]

    agent = TemporalAwarenessAgent(client=client)
    plan = agent.generate_plan(TemporalRequest(
        description="I just got married last month — what do I need to do for insurance?",
        today=date(2026, 4, 10),
    ))

    assert plan.event_type == EventType.SEP_MARRIAGE
    assert plan.trigger_date == date(2026, 4, 1)
    assert plan.deadline == date(2026, 5, 31)
    assert client.messages.create.call_count == 2


# ── PHI redaction at the classifier boundary ────────────────────────────────


def test_classifier_redacts_phi_before_calling_llm():
    client = MagicMock()
    client.messages.create.return_value = _stub_response(
        _classifier_payload("sep_birth", "2026-04-15")
    )

    classifier = EventClassifier(client=client)
    classifier.classify(
        "Patient: John Smith, SSN 123-45-6789, just had a baby on 4/15.",
        today=date(2026, 4, 20),
    )

    # Inspect what was actually sent to the LLM.
    sent = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "John Smith" not in sent, "raw patient name reached the LLM"
    assert "123-45-6789" not in sent, "raw SSN reached the LLM"
    assert "[PATIENT_NAME]" in sent or "[SSN]" in sent, \
        f"expected at least one redaction marker in: {sent[:300]!r}"


# ── Audit log: one entry per invocation, no PHI ─────────────────────────────


def test_audit_log_emits_one_entry_with_no_phi(caplog):
    client = MagicMock()
    client.messages.create.side_effect = [
        _stub_response(_classifier_payload("sep_job_loss", "2026-04-01")),
        _stub_response(_actions_payload(["2026-04-15"])),
    ]

    agent = TemporalAwarenessAgent(client=client)
    description_with_phi = "Patient: Jane Doe lost her job on 4/1. SSN 999-88-7777."

    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        agent.generate_plan(TemporalRequest(
            description=description_with_phi,
            today=date(2026, 4, 10),
        ))

    entries = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.getMessage().startswith("{")
    ]
    temporal_entries = [e for e in entries if e.get("event_type") == "temporal_plan_generated"]
    assert len(temporal_entries) == 1, f"expected exactly one audit entry, got {len(temporal_entries)}"

    blob = json.dumps(temporal_entries[0])
    # Hard-block: no PHI from the input must appear ANYWHERE in the audit record.
    assert "Jane Doe" not in blob
    assert "999-88-7777" not in blob
    assert "patient" not in blob.lower()

    details = temporal_entries[0]["details"]
    assert details["agent"] == "temporal_awareness"
    assert details["event_type"] == "sep_job_loss"
    assert details["input_source"] == "natural_language"


def test_audit_log_marks_structured_input_source():
    client = MagicMock()
    client.messages.create.return_value = _stub_response(_actions_payload(["2026-06-01"]))
    agent = TemporalAwarenessAgent(client=client)

    with pytest.MonkeyPatch.context() as mp:
        # Make the AuditLogger record what it sees so the test doesn't depend
        # on caplog ordering against the autouse fixtures.
        seen: list[tuple[str, dict]] = []
        mp.setattr(agent.audit, "log", lambda et, det: seen.append((et, det)))

        agent.generate_plan(TemporalRequest(
            event=ClassifiedEvent(event_type=EventType.OPEN_ENROLLMENT, trigger_date=date(2026, 11, 1)),
            today=date(2026, 11, 1),
        ))

    assert len(seen) == 1
    assert seen[0][0] == "temporal_plan_generated"
    assert seen[0][1]["input_source"] == "structured"


# ── Failure modes ───────────────────────────────────────────────────────────


def test_classifier_raises_on_non_json_output():
    client = MagicMock()
    client.messages.create.return_value = _stub_response("Sorry, I couldn't parse that.")

    classifier = EventClassifier(client=client)
    with pytest.raises(ValueError, match="non-JSON"):
        classifier.classify("anything", today=date(2026, 5, 1))


def test_classifier_raises_on_unknown_event_type():
    client = MagicMock()
    client.messages.create.return_value = _stub_response(
        json.dumps({"event_type": "totally_made_up", "trigger_date": "2026-05-01"})
    )

    classifier = EventClassifier(client=client)
    with pytest.raises(ValueError, match="unknown event_type"):
        classifier.classify("anything", today=date(2026, 5, 1))


def test_request_rejects_both_event_and_description():
    with pytest.raises(ValueError, match="exactly one"):
        TemporalRequest(
            event=ClassifiedEvent(event_type=EventType.SEP_BIRTH, trigger_date=date(2026, 5, 1)),
            description="and also some text",
        )


def test_request_rejects_neither_event_nor_description():
    with pytest.raises(ValueError, match="exactly one"):
        TemporalRequest(today=date(2026, 5, 1))
