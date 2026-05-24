# Audit Replay & Forensics Tool

**Date:** 2026-05-24
**Status:** Approved (design)
**Part of:** Compliance/forensics tooling. PR #2 of 2 — built on the foundation shipped in PR #18 (`agent_invocation_log` + `case_id` ContextVar + `InvocationLogger`).

## Problem

HealthFlow's audit data is now structured (PR #18) but there's no way to read it back. A compliance reviewer needs to answer questions like:

- "What did agents do for case `<uuid>`?"
- "Which clients did broker X touch between Mar 1 and Mar 31?"
- "How many times did the `network` agent fire last week, with what error rate?"

Today this requires raw SQL plus knowing where the foundation tables live. That's not a forensics workflow — it's just database querying. The tool turns it into a single Python API + CLI + HTTP endpoint that produces a chronological timeline with integrity checks.

## Goal

A read-only forensics tool exposing three surfaces over the existing `agent_invocation_log` and `phi_access_log` tables. Every query writes one row to a new `forensics_access_log` (self-audit). Tenant isolation is enforced at the query layer; cross-tenant queries return empty (not error — no information leak).

## Non-Goals

Each is a deliberate deferral:

- **Modifying the foundation tables.** This is a read-only consumer.
- **Hash-chain tamper evidence.** `IntegrityCheck.tamper_evidence` reports `"unknown"` until a separate sub-project hash-chains the rows.
- **Anomaly detection / ML.** Out of scope; the tool reports raw timelines.
- **Real-time streaming or log tailing.** Batch queries only.
- **Visual UI.** CLI text + JSON is the entire surface; the React frontend doesn't need a forensics page.
- **Cross-tenant queries (even for admin roles).** Tenant boundary is absolute. Admin RBAC may inspect *their own* tenant in detail; that's all.
- **Backfilling pre-PR-#18 history.** Anything before the foundation shipped lives only in the legacy `healthflow.log` text file and isn't reconstructable as `CaseTimeline`. The tool reports an explicit "data start" date.

## Design

### Architecture

A single package `healthflow/forensics/` with one core query module + thin CLI/route adapters + integrity + redaction + tests + README. No new database connection — reuses the existing async session factory via a dependency-injected pattern (production) or test factory (tests).

**File layout:**

- `healthflow/forensics/__init__.py` — re-exports `replay_case`, `replay_member`, `replay_agent`, `CaseTimeline`.
- `healthflow/forensics/schemas.py` — Pydantic models (AgentInvocation, IntegrityCheck, CaseTimeline, MemberRange, AgentRange, etc.).
- `healthflow/forensics/replay.py` — core async query functions. Operates on a passed-in `AsyncSession` factory.
- `healthflow/forensics/integrity.py` — gap detection (chronology gaps, missing case_id, error-clustered windows).
- `healthflow/forensics/redaction.py` — final output redaction pass (hashes member IDs, passes any free-text fields through `PHIRedactor`).
- `healthflow/forensics/cli.py` — `click` group, mirrors existing CLI conventions (`scripts/promote_admin.py`, `healthflow/cli.py`).
- `healthflow/forensics/routes.py` — FastAPI router exposing `POST /forensics/replay`. Auth-gated by `get_current_broker`; admin role check via `require_admin`.
- `healthflow/database/models.py` *(modify)* — append `ForensicsAccessLog` (system table; self-audit).
- `healthflow/forensics/tests/test_replay.py` — replay-function tests against an in-memory SQLite seeded with synthetic invocations.
- `healthflow/forensics/tests/test_integrity.py` — gap detection: synthetic timelines with known gaps → flagged.
- `healthflow/forensics/tests/test_redaction.py` — PHI patterns in `details` JSON → redacted in output.
- `healthflow/forensics/tests/test_routes.py` — `POST /forensics/replay` end-to-end (auth, tenant isolation, self-audit).
- `healthflow/forensics/tests/test_cli.py` — click `CliRunner` against the three replay verbs.
- `healthflow/forensics/tests/fixtures.py` — synthetic `AgentInvocationLog` + `PhiAccessLog` fixtures (no live PHI).
- `healthflow/forensics/README.md` — endpoint contract, CLI usage, integrity-check rules, explicit "what this does NOT do" list.

### Data sources (post-foundation)

| Source | Role | Joinable by |
|---|---|---|
| `agent_invocation_log` (new in PR #18) | Primary timeline source | `case_id` (real, propagated), `broker_id`, `agent`, `created_at` |
| `phi_access_log` (existing) | Which PHI rows the broker touched | `broker_id`, `endpoint`, `created_at`, `row_ids` (JSON list of client UUIDs) |
| `healthflow.log` (legacy text) | NOT read by this tool | — |

Joining `agent_invocation_log` to `phi_access_log` is done on `(broker_id, created_at ± 2s)` — same broker, near-simultaneous timestamps. The 2-second window matches the gap between an agent's invocation start and its first DB read in practice.

### Output schemas

```python
class AgentInvocation(BaseModel):
    agent: str                          # "comparison", "temporal_awareness", "harness"
    invocation_id: uuid.UUID            # AgentInvocationLog.id
    timestamp: datetime                 # AgentInvocationLog.created_at
    case_id: uuid.UUID | None
    endpoint: str
    event_type: str                     # "recommend", "translate", "verify", etc.
    model_used: str | None              # CLAUDE_MODEL value when known
    duration_ms: int | None
    details_summary: str                # redacted JSON, short, no PHI
    error: str | None                   # populated for failed invocations
    phi_tables_touched: list[str]       # honest naming: tables, not fields
    phi_row_count: int                  # number of PHI rows accessed in the join window

class IntegrityCheck(BaseModel):
    entries_found: int
    gaps_detected: list[str]            # e.g. "27-second gap between invocations 3 and 4 — unusual for this agent"
    tamper_evidence: Literal["clean", "suspect", "unknown"]  # "unknown" until hash-chain ships
    notes: list[str]

class CaseTimeline(BaseModel):
    case_id: uuid.UUID | None           # None for replay_member / replay_agent
    member_id_hash: str | None          # SHA-256 prefix; None when not member-scoped
    time_range: tuple[datetime, datetime]
    tenant_id: uuid.UUID                # broker_id (HealthFlow's tenant unit)
    invocations: list[AgentInvocation]  # chronological asc
    decision_chain: list[str]           # ordered event_types ("recommend → verify → temporal_plan")
    integrity: IntegrityCheck
```

**Vocabulary note:** the original spec used "member_id" and "tenant_id"; HealthFlow's vocabulary is "client_id" (member) and "broker_id" (tenant). The schemas use the user-facing field names from the spec but the underlying joins use the codebase's actual columns. The `member_id_hash` is `sha256(str(client_id))[:16]` — sufficient for case correlation, never reversible to a raw UUID.

**Spec deviations from the original prompt (documented honestly):**

- `phi_fields_accessed: list[str]` → `phi_tables_touched: list[str]` + `phi_row_count: int`. The audit listener records at table+row-id granularity, not column granularity. Promising field names would be a lie; promising tables + count is truthful.
- `Handoff` model dropped. The codebase doesn't model agent-to-agent handoffs; you can read sequential invocations under one `case_id` as implied handoffs, which is what `decision_chain` already gives you. A real `Handoff` would need a new audit event type that doesn't exist — out of scope.
- `model_used` is now real per row (was a gap in the original recon).
- `duration_ms` is now real per row (was a gap in the original recon).
- `case_id` is now real (was a flagged gap; resolved by PR #18).

### Python API

```python
async def replay_case(
    case_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> CaseTimeline: ...

async def replay_member(
    client_id: uuid.UUID,             # the prompt's "member_id"
    time_range: tuple[datetime, datetime],
    *,
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> CaseTimeline: ...

async def replay_agent(
    agent: str,                       # e.g. "comparison"
    time_range: tuple[datetime, datetime],
    *,
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> list[AgentInvocation]: ...
```

Each function:
1. Filters `agent_invocation_log` by the scope key (`case_id`, joined `client_id` via `phi_access_log`, or `agent`) AND by `broker_id = tenant_id`.
2. For each invocation, fetches matching `phi_access_log` rows in a `±2s` window for the same broker, attaches `phi_tables_touched` and `phi_row_count`.
3. Runs `integrity.check(invocations)` → IntegrityCheck.
4. Passes the full output through `redaction.redact(...)` so free-text `details.*` are scrubbed.
5. Writes one self-audit row to `forensics_access_log` (see below).
6. Returns the timeline (or empty timeline for cross-tenant / no-data cases).

### CLI

```bash
python -m healthflow.forensics replay case <case_id> [--format json|text]
python -m healthflow.forensics replay member <client_uuid> --from 2026-04-01 --to 2026-04-30 [--format json|text]
python -m healthflow.forensics replay agent comparison --from 2026-04-01 --to 2026-04-30 [--format json|text]
```

- `--format text` (default): human-readable summary — chronological list, durations, error markers, integrity notes.
- `--format json`: emits the full `CaseTimeline` JSON for piping to `jq` / further analysis.

Auth in the CLI: reads `tenant_id` from a `--tenant-id <uuid>` flag (required). The CLI does not infer the current operator — operator identity is captured in the self-audit row via the existing process user. Production usage requires the operator to set their tenant flag explicitly; running against the wrong tenant returns empty (no leak).

### `POST /forensics/replay` endpoint

**Auth:** `Depends(require_admin)` — only admins call this. Tenant_id is taken from the authenticated admin's `broker_id` (not from request body — prevents tenant-id spoofing).

**Request:**
```json
{
  "mode": "case",
  "case_id": "550e8400-e29b-41d4-a716-446655440000"
}
// OR
{
  "mode": "member",
  "client_id": "...",
  "from_ts": "2026-04-01T00:00:00Z",
  "to_ts": "2026-04-30T23:59:59Z"
}
// OR
{
  "mode": "agent",
  "agent": "comparison",
  "from_ts": "2026-04-01T00:00:00Z",
  "to_ts": "2026-04-30T23:59:59Z"
}
```

**Response:** the appropriate `CaseTimeline` (or `list[AgentInvocation]` for `mode: agent`).

**Self-audit:** every call writes one `ForensicsAccessLog` row regardless of result count.

### Self-audit: `ForensicsAccessLog`

New system table (appended to `models.py`):

```python
class ForensicsAccessLog(Base):
    """One row per forensics query. Records who queried what, when, with what
    result count. Not tenant-scoped (it records cross-broker admin activity);
    not in _AUDITED_MODELS (forensics queries are not PHI access).
    """
    __tablename__ = "forensics_access_log"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    operator_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # "case" | "member" | "agent"
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)  # the case_id / client_id / agent
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    from_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    to_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
```

Picked up by `Base.metadata.create_all` on startup. No alembic.

### Integrity checks (gap detection)

`integrity.check(invocations)` runs four passes:

1. **Chronological gaps within a case.** Compute interval between consecutive `created_at` for the same `case_id`. If any gap > 5 minutes, note it (humans rarely pause that long inside one workflow). Add to `notes`.
2. **Error clusters.** Three or more consecutive invocations with non-null `error` → `gaps_detected: ["error cluster: invocations N..M all failed"]`.
3. **Missing `case_id`.** Any invocation in the result set with `case_id=None` for a query scoped to a specific case → impossible-by-construction, flag as `gaps_detected: ["invocation X has no case_id but matched the scope"]`.
4. **`tamper_evidence`.** Always `"unknown"` until the hash-chain follow-up ships. Documented in the IntegrityCheck schema + README.

### PHI redaction in output

The `details` JSON column on `agent_invocation_log` shouldn't contain PHI (agents write structural metadata only — counts, lengths, event types). But forensics is a defense-in-depth surface; we run output through `PHIRedactor` anyway:

- `redaction.redact(timeline)` walks every string value in the JSON-serializable timeline.
- Each string passes through `PHIRedactor().redact(value)`; PHI patterns get replaced with placeholders.
- The redacted timeline is what gets returned to the caller.
- The `details_summary` field is the redacted JSON of the row's `details`, truncated to 200 chars.

### Error handling matrix

| Endpoint | Failure mode | Response |
|---|---|---|
| Python API | Invalid input (bad UUID, missing required arg) | `ValueError` |
| Python API | Cross-tenant query (case_id exists but for a different tenant) | Empty `CaseTimeline` (no info leak) |
| CLI | Invalid flag combination | `click.UsageError` (non-zero exit) |
| CLI | Empty result | Prints "No invocations found" + exits 0 |
| `POST /forensics/replay` | Not admin | `403` |
| `POST /forensics/replay` | No bearer | `401` |
| `POST /forensics/replay` | Bad request body (mode unknown, missing required field) | `422` |
| `POST /forensics/replay` | Cross-tenant / no data | `200` with empty timeline |
| `POST /forensics/replay` | DB unavailable | `503` (let it surface — forensics IS the operability check) |

### Test plan (~22 tests)

**`test_replay.py` (8 tests)**
- `replay_case` returns chronologically-ordered invocations for a case.
- `replay_case` populates `phi_tables_touched` via the ±2s join.
- `replay_case` returns empty for a case in another tenant (cross-tenant isolation).
- `replay_member` joins through `phi_access_log.row_ids` correctly.
- `replay_member` honors `time_range`.
- `replay_agent` filters by agent string + time_range.
- `replay_agent` returns invocations in chronological order.
- All three functions write exactly one `ForensicsAccessLog` row per call.

**`test_integrity.py` (5 tests)**
- Synthetic timeline with a 10-minute gap → flagged in `notes`.
- Three consecutive errors → flagged in `gaps_detected` as an error cluster.
- Case-scoped query with an invocation missing `case_id` (synthetic broken data) → flagged.
- `tamper_evidence` is always `"unknown"` for this PR.
- Clean timeline → empty `gaps_detected`, `notes=[]`.

**`test_redaction.py` (3 tests)**
- `details` containing a fake SSN → redacted in `details_summary`.
- `details` containing a patient-label name → redacted.
- Long `details` truncated to 200 chars after redaction.

**`test_routes.py` (4 tests)**
- Admin POSTs `case` mode → 200 with timeline.
- Non-admin POSTs → 403.
- Unauthenticated POST → 401.
- Cross-tenant case_id → 200 with empty timeline (not 404 — no info leak).

**`test_cli.py` (2 tests)**
- `replay case <uuid> --format json` emits parseable JSON.
- `replay agent comparison --from ... --to ...` runs and exits 0.

Total: 22 new tests, no network, no LLM. Fixtures live in `forensics/tests/fixtures.py` — synthetic `AgentInvocationLog` + `PhiAccessLog` rows seeded into an in-memory SQLite per test.

### Rollout (per-task, each commit green)

1. **Baseline + branch.** Confirm `make test` green (678 from PR #18). Create `forensics-replay-tool` branch.
2. **Schemas + ForensicsAccessLog model + migration (create_all picks it up).** Tests: model loads, columns correct.
3. **Synthetic fixtures + `replay_case` + 3 tests.** Build the simplest query first.
4. **`replay_member` + `replay_agent` + 5 tests.**
5. **`integrity.py` + 5 tests.**
6. **`redaction.py` + 3 tests.**
7. **`cli.py` + 2 tests.**
8. **`routes.py` + mount in `main.py` + 4 tests.**
9. **README** — endpoint contract, CLI usage, integrity rules, explicit "does NOT" list.
10. **Final verification.** `make test` + `make smoke-external` + push + PR.

### Risks

| Risk | Mitigation |
|---|---|
| ±2s join window misses PHI accesses from slow requests | Tunable constant in `replay.py`. Document the default + how to override. Track via a metrics counter in a follow-up. |
| Synthetic-membership in PHI access log can be huge for broad time-range queries | Add a configurable `limit` parameter (default 1000); errors above unless explicitly raised. |
| `PHIRedactor` doesn't catch every pattern | Defense-in-depth — agents shouldn't write PHI to `details` in the first place. Document the contract in `healthflow-security` skill. |
| Admin RBAC granularity | Out of scope. All admins can run forensics today. Per-broker forensics scoping is a follow-up if needed. |
| Self-audit row write fails | If `forensics_access_log` write raises, the query fails too (fail-loud — better than silently un-audited admin queries). |
| `case_id` was None for invocations before the middleware shipped | Document: "Timelines before YYYY-MM-DD (foundation ship date) won't have case_id correlation; member/agent scopes still work." |

## Acceptance

This sub-project is done when:

1. `pytest healthflow/forensics/tests/` passes (~22 tests), no network, no LLM.
2. `python -m healthflow.forensics replay case <synthetic_uuid>` prints a chronological timeline.
3. `POST /forensics/replay` returns valid `CaseTimeline` for an admin call on a synthetic case.
4. Cross-tenant query test: a case belonging to tenant A queried as tenant B returns empty (not 404, not error).
5. Gap-detection test: a synthetic log with a 10-minute gap is flagged in `IntegrityCheck.notes`.
6. PHI-redaction test: free-text containing PHI patterns is redacted in every output field, asserted by direct content match (no PHI string appears in the output).
7. `forensics_access_log` records exactly one row per query.
8. README documents the three surfaces, example queries, vocabulary mapping (member_id→client_id, tenant_id→broker_id), and the explicit list of what this tool does NOT do.

## Out of Scope

Each is a deliberate deferral:

- Hash-chain tamper-evidence (`tamper_evidence` stays `"unknown"` until a separate sub-project hash-chains `agent_invocation_log`).
- `Handoff` modeling (no agent-to-agent audit events exist; `decision_chain` covers what's truthfully reconstructable today).
- `phi_fields_accessed: list[str]` (audit is row-level, not field-level; output truthfully reports `phi_tables_touched` + `phi_row_count` instead).
- Real-time log streaming.
- Anomaly / ML detection on timelines.
- Frontend UI for forensics.
- Cross-tenant queries — even for admin roles.
- Backfilling pre-PR-#18 history.
