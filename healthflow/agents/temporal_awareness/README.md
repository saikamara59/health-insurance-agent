# Temporal Awareness Agent

A deadline-aware planning agent for time-sensitive health-insurance events.
Lives at `healthflow/agents/temporal_awareness/` and ships behind one FastAPI
route, `POST /temporal/plan`.

## What it does

Given either a structured event payload or a natural-language description,
the agent:

1. Classifies the event (Claude Haiku) into one of the supported types.
2. Computes the regulatory deadline via pure-function deadline math.
3. Generates 3–6 concrete action steps with target dates (Claude Sonnet).
4. Writes ONE audit-log entry per invocation. Zero PHI in the entry.

## Supported event types

| Event type | Window |
|---|---|
| `open_enrollment` | Nov 1 → Jan 15 (deadline = next Jan 15) |
| `medicare_aep` | Oct 15 → Dec 7 (deadline = next Dec 7) |
| `sep_job_loss` / `sep_marriage` / `sep_birth` / `sep_move` / `sep_divorce` | 60 days from the qualifying event |
| `pa_appeal` | 60 days (HMO/MA), 180 days (PPO), 120 days (default) |

Urgency thresholds: `≤7d → critical`, `≤14d → high`, `≤30d → medium`, else `low`.

## Endpoint

```
POST /temporal/plan
Authorization: Bearer <broker-token>
Content-Type: application/json

# Structured input
{
  "event": {
    "event_type": "sep_job_loss",
    "trigger_date": "2026-05-01",
    "plan_type": null
  },
  "today": "2026-05-11"   // optional; defaults to date.today()
}

# OR natural-language input
{
  "description": "I just got married last week — what do I need to do?",
  "today": "2026-05-11"
}
```

Provide **exactly one** of `event` or `description`. Sending both, or
neither, returns 422.

Response (`ActionPlan`):

```json
{
  "event_type": "sep_job_loss",
  "trigger_date": "2026-05-01",
  "deadline": "2026-06-30",
  "days_remaining": 50,
  "urgency": "low",
  "actions": [
    {"step": 1, "description": "Compare available SEP plans for the ZIP", "target_date": "2026-05-25", "completed": false},
    {"step": 2, "description": "Submit application before the window closes", "target_date": "2026-06-20", "completed": false}
  ]
}
```

## Package layout

```
healthflow/agents/temporal_awareness/
├── __init__.py
├── agent.py              # TemporalAwarenessAgent — orchestrator
├── event_classifier.py   # Claude Haiku classifier + PHI redaction
├── deadline_engine.py    # Pure-function deadline math, zero LLM calls
├── schemas.py            # Pydantic models (EventType, Action, ActionPlan, TemporalRequest)
├── routes.py             # FastAPI router (POST /temporal/plan)
├── demo.py               # 3 end-to-end scenarios against the real API
├── README.md             # this file
└── tests/
    ├── conftest.py            # re-uses healthflow/tests fixtures
    ├── test_deadline_engine.py    # 32 unit tests, no network
    ├── test_agent.py              # 10 agent tests, mocked Anthropic client
    └── test_routes.py             # 5 endpoint tests via httpx + mocked agent
```

## Model selection

This is the first agent to introduce a second Claude model in the codebase:

- `CLAUDE_MODEL = "claude-sonnet-4-6"` (existing) — generates action steps.
- `CLAUDE_CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"` (new in `healthflow/agents/harness.py`) — classifies the natural-language path.

Haiku is fast and cheap for structured-extraction work. Sonnet handles the
free-form action generation. This is the **only** structural change to
`harness.py`; other agents are unaffected.

## PHI handling

- Natural-language input is passed through `PHIRedactor` (from
  `healthflow.tools.phi_redactor`) BEFORE the Haiku call. Patient names,
  SSNs, DOBs, and member IDs are replaced with placeholders.
- The Sonnet action-generation call sees ONLY structured metadata (event
  type, dates, urgency). No raw description is ever forwarded to it.
- The audit log records `event_type`, `trigger_date`, `deadline`,
  `days_remaining`, `urgency`, `action_count`, `today`, `input_source`,
  and a fixed `agent: "temporal_awareness"`. No description, no patient
  identifiers, no free text from the user.
- The agent does NOT read or write any PHI columns. It performs zero
  database I/O of its own.

See `.claude/skills/healthflow-security/SKILL.md` for the broader PHI
posture; this agent follows the existing rules and does not add a new
PHI surface.

## Running

```bash
# Unit + agent + route tests (no network)
.venv/bin/python -m pytest healthflow/agents/temporal_awareness/tests/ -v

# End-to-end demo against the real Anthropic API (requires ANTHROPIC_API_KEY)
.venv/bin/python -m healthflow.agents.temporal_awareness.demo
```

The endpoint is mounted automatically in `healthflow/main.py`; `make dev`
exposes it at `http://localhost:8000/temporal/plan`.

## Integration with the rest of HealthFlow

| Concern | This agent's behavior |
|---|---|
| Auth | Same `get_current_broker` dependency as every other authenticated endpoint. No new auth surface. |
| Database | Read-only — never touches the schema. Holds no state between requests. |
| Audit | One `AuditLogger.log("temporal_plan_generated", {...})` per invocation, no PHI. |
| Tenant isolation | The agent doesn't read tenant-scoped tables, so it's not affected by the tenant filter. |
| Encryption at rest | N/A — no DB writes. |
| Code-review skill | This agent's PHI posture is documented above; the `healthflow-security` skill does not need a new rule. |
