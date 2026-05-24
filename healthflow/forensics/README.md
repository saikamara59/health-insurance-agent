# Audit Replay & Forensics Tool

Read-only reconstruction of agent timelines from `agent_invocation_log`
(shipped in PR #18) + `phi_access_log`. Three surfaces sharing one query
layer: Python API, CLI, and FastAPI endpoint.

## Vocabulary mapping

The original spec used industry-standard health-insurance vocabulary;
HealthFlow's column names differ. The user-facing API uses the spec's
vocabulary; the underlying queries use the codebase's columns.

| Spec term | HealthFlow column |
|---|---|
| `member_id` (the patient) | `client_id` |
| `tenant_id` (the data-owning principal) | `broker_id` |
| `agent_id` | `agent` (e.g. `"comparison"`, `"temporal_awareness"`) |

## Surfaces

### Python API

```python
from healthflow.forensics import replay_case, replay_member, replay_agent

timeline = await replay_case(case_id, tenant_id=admin.id, session_factory=factory)
timeline = await replay_member(client_id, time_range=(start, end), tenant_id=admin.id, session_factory=factory)
invocations = await replay_agent("comparison", time_range=(start, end), tenant_id=admin.id, session_factory=factory)
```

### CLI

```bash
python -m healthflow.forensics replay case <case_id> --tenant-id <uuid> [--format json|text]
python -m healthflow.forensics replay member <client_id> --tenant-id <uuid> --from <iso> --to <iso> [--format json|text]
python -m healthflow.forensics replay agent <agent> --tenant-id <uuid> --from <iso> --to <iso> [--format json|text]
```

`--format text` (default) is human-readable. `--format json` emits the full
`CaseTimeline` for piping to `jq` or other tools.

Operator identity in the self-audit row defaults to the supplied
`--tenant-id`. The CLI does not infer a separate operator — operators are
expected to run from a trusted shell.

### HTTP

```http
POST /forensics/replay
Authorization: Bearer <admin-token>

{"mode": "case", "case_id": "..."}
# OR
{"mode": "member", "client_id": "...", "from_ts": "...", "to_ts": "..."}
# OR
{"mode": "agent", "agent": "comparison", "from_ts": "...", "to_ts": "..."}
```

Admin-only via `require_admin`. The route reads `tenant_id` from the
authenticated admin's `broker_id` — request body cannot override.

## Integrity checks

Every replay runs four passes:

1. **Chronological gaps** > 5 minutes between consecutive invocations → note.
2. **Error clusters** of 3+ consecutive non-null `error` rows → `gaps_detected`.
3. **Case scope with missing case_id** (impossible-by-construction) → `gaps_detected`.
4. **`tamper_evidence`** — always `"unknown"` until the hash-chain follow-up ships.

## Self-audit

Every query writes exactly one row to `forensics_access_log` capturing
`(operator_id, mode, scope_key, tenant_id, from_ts, to_ts, result_count,
created_at)`. Fail-loud — if the self-audit write fails, the query
fails too. Unaudited admin queries are not acceptable.

## What this tool does NOT do

- **Modify any existing audit data.** Read-only on the foundation tables.
- **Cross-tenant queries.** Even for admins. Cross-tenant lookups return
  an empty timeline (not 404, not 403 — no information leak).
- **Hash-chain tamper evidence.** Future sub-project; `tamper_evidence` is
  always `"unknown"` until that ships.
- **`Handoff` modeling.** Agent-to-agent handoffs aren't recorded as a
  distinct event type. `decision_chain` (chronological event_types under
  one case_id) is the truthful equivalent.
- **Field-level PHI granularity.** `phi_access_log` records at table+row-id
  granularity. Output reports `phi_tables_touched` + `phi_row_count`,
  never specific column names.
- **Backfilled history.** Anything before PR #18 (`agent_invocation_log`
  ship date) isn't reconstructable as `CaseTimeline`. The text log
  remains the only source for older events.
- **Real-time log tailing or streaming.** Batch queries only.
- **Visual UI.** The React frontend has no forensics page; CLI + JSON is
  the entire surface.
- **ML / anomaly detection.** Raw timelines + structural integrity only.

## Files

```
healthflow/forensics/
├── __init__.py
├── __main__.py
├── replay.py        — three query functions
├── schemas.py       — Pydantic models
├── integrity.py     — gap detection + error clusters
├── redaction.py     — defense-in-depth PHI scrub
├── cli.py           — click CLI
├── routes.py        — FastAPI router
├── README.md        — this file
└── tests/
    ├── conftest.py        — re-exports shared fixtures
    ├── fixtures.py        — synthetic row builders
    ├── test_replay.py     — 8 tests
    ├── test_integrity.py  — 5 tests
    ├── test_redaction.py  — 3 tests
    ├── test_routes.py     — 4 tests
    └── test_cli.py        — 2 tests
```

## Running

```bash
# Unit + route + CLI tests (no network)
make test  # full suite

# Or just the forensics package (requires the root conftest to fire first):
.venv/bin/python -m pytest healthflow/tests/ healthflow/forensics/tests/ -k forensics -v
```
