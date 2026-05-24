# Agent Invocation Logging (foundation for forensics tooling)

A structured per-call audit row written by every HealthFlow agent.
Sibling of the legacy text-rotating `AuditLogger`; the text log keeps
running unchanged for now, so this is purely additive.

## Why

The legacy `AuditLogger` writes JSON lines to `healthflow.log` (text
file with rotation). That works for human spot-checking but is
unsuitable for compliance/forensics workflows that need:

- SQL queries by `case_id` / `broker_id` / `agent` / `time window`
- A correlation ID that propagates across an agent chain
- Per-call `duration_ms` and `model_used`
- Failure capture (exceptions are the most forensics-relevant events)

This module fills that gap. A planned follow-up sub-project — the
"forensics replay" tool — will read `agent_invocation_log` to
reconstruct timelines for compliance review.

## Components

| Piece | File | Role |
|---|---|---|
| `case_id` ContextVar | `healthflow/auth/case_context.py` | Request-scoped correlation ID. Mirrors `current_broker_id` / `current_endpoint`. |
| `CaseContextMiddleware` | `healthflow/api/case_middleware.py` | Reads `X-Case-Id` header (validates as UUID; generates fresh if absent/invalid). Echoes back in the response header so callers can correlate logs across systems. |
| `AgentInvocationLog` | `healthflow/database/models.py` | System table — not tenant-scoped, not in `_AUDITED_MODELS`. Columns: `id`, `case_id`, `broker_id`, `endpoint`, `agent`, `event_type`, `model_used`, `duration_ms`, `details` (JSON), `error`, `created_at`. |
| `InvocationLogger` | `healthflow/logs/invocation.py` | Sync context manager. Writes one row per wrapped operation, on success **and on exception**. |
| Module-level singleton `invocation` | same file | What agents import: `from healthflow.logs.invocation import invocation`. |

## Usage in agents

Each agent's top-level method is wrapped once:

```python
from healthflow.logs.invocation import invocation

def recommend(self, ...) -> str:
    with invocation(agent="comparison", event_type="recommend", model=CLAUDE_MODEL) as inv:
        # ... existing work ...
        recommendation = self._call_claude(...)
        inv.details = {"length": len(recommendation), "plans": len(plans)}
        return recommendation
```

`duration_ms` is captured automatically (monotonic start at `__enter__`
to monotonic end at `__exit__`). `case_id`, `broker_id`, and `endpoint`
are read from the request-scoped ContextVars at `__enter__`. `details`
is whatever the caller assigned during the body.

The existing `self.audit.log(...)` calls remain alongside — the text
log is the source of granular sub-events; the invocation row is the
holistic "this agent ran" record.

## Five design properties

1. **DB-write failure is swallowed.** Any exception writing the row →
   falls back to the legacy text `AuditLogger` with event_type
   `agent_invocation_log_write_failed` and the full row payload. The
   wrapped operation NEVER blocks on audit infrastructure.

2. **Exception path writes a row.** If the body raises, the row is
   still written before the exception propagates. The `error` field
   captures `"{type}: {msg}"[:512]`. Failed invocations are the most
   important to capture for forensics.

3. **Sync engine, sync session.** Writes use a parallel sync
   SQLAlchemy engine (the URL is derived from `DATABASE_URL` via
   `_sync_url()`). This keeps the request's async transaction
   independent of the audit write.

4. **try/finally session disposal.** No engine connection leaks on
   exception paths.

5. **ContextVars captured at `__enter__`.** Even if `case_id` is reset
   mid-body, the recorded row uses the value that was live when the
   context manager opened — matches the timing of the operation, not
   the state at exit.

## X-Case-Id contract

```
POST /compare
X-Case-Id: 550e8400-e29b-41d4-a716-446655440000
```

If the header is supplied and valid, it propagates through every agent
call this request makes. If absent/malformed, the middleware generates
a fresh `uuid4()` and logs a WARN for the invalid case. The response
always echoes the resolved `X-Case-Id` so the caller can correlate.

A future broker workflow can tie together several `/compare`, `/verify`,
`/temporal/plan` calls under the same case by reusing the header value.

## Migration

`Base.metadata.create_all` picks up the `agent_invocation_log` table
on startup. No alembic.

For dev databases that already exist: `create_all` is idempotent and
creates only the missing table on next startup.

## What this does NOT do (yet)

- **Tamper-evidence / hash chain** — out of scope. The forensics tool
  will report `tamper_evidence: "unknown"` until a separate sub-project
  hash-chains the rows.
- **The forensics replay tool itself** — separate sub-project. This
  module is the foundation it reads.
- **Backfilling old audit data** — only new invocations get rows. The
  text log remains the source for anything before this PR shipped.
- **Async writes / background queue** — the write is synchronous from
  the request's thread. At HealthFlow's scale (≤ a few req/s) this is
  fine; at higher scale, consider a queue+worker.
