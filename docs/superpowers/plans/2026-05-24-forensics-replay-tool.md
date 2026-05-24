# Audit Replay & Forensics Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only forensics tool — Python API + CLI + FastAPI endpoint — that reconstructs chronological timelines of agent activity from the `agent_invocation_log` table (shipped in PR #18) and joins them to `phi_access_log` for PHI-access context. Cross-tenant isolation, output redaction, self-audit, integrity checks.

**Architecture:** Single package `healthflow/forensics/` with three thin surface adapters (`cli.py`, `routes.py`, Python API in `replay.py`) all calling the same async query functions. Synthetic in-memory SQLite fixtures for tests. New `ForensicsAccessLog` system table for self-auditing every query.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x async (`select`, `async_sessionmaker`), Pydantic 2, FastAPI, `click` for CLI. Tests use the existing `db_session_factory` / `db_session` fixtures from `healthflow/tests/conftest.py`.

**Spec:** `docs/superpowers/specs/2026-05-24-forensics-replay-tool-design.md`

---

## File Structure

**New files (under `healthflow/forensics/`):**
- `__init__.py` — re-exports `replay_case`, `replay_member`, `replay_agent`, `CaseTimeline`.
- `schemas.py` — `AgentInvocation`, `IntegrityCheck`, `CaseTimeline`, `ReplayCaseRequest`, `ReplayMemberRequest`, `ReplayAgentRequest`.
- `replay.py` — three core async query functions.
- `integrity.py` — `check(invocations, scope)` returning `IntegrityCheck`.
- `redaction.py` — `redact(timeline)` walks the model, passes string fields through `PHIRedactor`.
- `cli.py` — `click` group with three replay verbs.
- `routes.py` — FastAPI `forensics_router` with `POST /forensics/replay`.
- `tests/__init__.py`, `tests/conftest.py` — re-export shared fixtures.
- `tests/fixtures.py` — synthetic-row helpers (`make_invocation`, `make_phi_access`).
- `tests/test_replay.py` — 8 tests (`replay_case`, `replay_member`, `replay_agent`, isolation, self-audit).
- `tests/test_integrity.py` — 5 tests (gap, error cluster, missing case_id, tamper, clean).
- `tests/test_redaction.py` — 3 tests (SSN / name / truncation).
- `tests/test_routes.py` — 4 tests (admin, non-admin 403, no-bearer 401, cross-tenant empty).
- `tests/test_cli.py` — 2 tests (JSON format, agent verb).
- `README.md` — endpoint contract, CLI usage, vocabulary mapping, integrity rules, explicit "does NOT" list.

**Modified files:**
- `healthflow/database/models.py` — append `ForensicsAccessLog` model.
- `healthflow/main.py` — mount `forensics_router`.
- `Makefile` — extend `test` / `test-quick` / `test-cov` paths to include `healthflow/forensics/tests/`.

**Untouched:** the foundation tables (`agent_invocation_log`, `phi_access_log`), `InvocationLogger`, all agents, the `AuditLogger` text logger, all other routes.

---

## Task 0: Baseline + branch

**Files:** none (operations only).

- [ ] **Step 1: Confirm clean baseline**

Run: `git status`
Expected: `nothing to commit, working tree clean` on branch `main`.

- [ ] **Step 2: Capture baseline test count**

Run: `make test 2>&1 | tail -3`
Expected: `678 passed, 3 skipped` (PR #18 baseline).

- [ ] **Step 3: Create the feature branch**

Run: `git checkout -b forensics-replay-tool`
Expected: switched to a new branch.

---

## Task 1: Schemas + `ForensicsAccessLog` model + smoke import

**Files:**
- Create: `healthflow/forensics/__init__.py`
- Create: `healthflow/forensics/schemas.py`
- Create: `healthflow/forensics/tests/__init__.py`
- Modify: `healthflow/database/models.py` (append `ForensicsAccessLog`)
- Modify: `Makefile` (add forensics test path)

- [ ] **Step 1: Create the package + tests subpackage**

```bash
mkdir -p healthflow/forensics/tests
touch healthflow/forensics/__init__.py healthflow/forensics/tests/__init__.py
```

- [ ] **Step 2: Add `ForensicsAccessLog` to `healthflow/database/models.py`**

Open `healthflow/database/models.py`. After the `AgentInvocationLog` class (end of file), append:

```python


class ForensicsAccessLog(Base):
    """One row per forensics query — self-audit for admin reads of the audit tables.

    System table — not tenant-scoped (records cross-broker admin activity),
    not in `_AUDITED_MODELS` (forensics queries are not PHI access).
    """
    __tablename__ = "forensics_access_log"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    operator_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    from_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    to_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
```

- [ ] **Step 3: Add `healthflow/forensics/schemas.py`**

Create `healthflow/forensics/schemas.py`:

```python
"""Pydantic schemas for the forensics replay tool.

Vocabulary mapping vs. the codebase:
  * member_id (spec)  → client_id (codebase) — the patient
  * tenant_id (spec)  → broker_id (codebase) — the user/owner
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentInvocation(BaseModel):
    agent: str
    invocation_id: uuid.UUID
    timestamp: datetime
    case_id: uuid.UUID | None = None
    endpoint: str
    event_type: str
    model_used: str | None = None
    duration_ms: int | None = None
    details_summary: str
    error: str | None = None
    phi_tables_touched: list[str] = Field(default_factory=list)
    phi_row_count: int = 0


class IntegrityCheck(BaseModel):
    entries_found: int
    gaps_detected: list[str] = Field(default_factory=list)
    tamper_evidence: Literal["clean", "suspect", "unknown"] = "unknown"
    notes: list[str] = Field(default_factory=list)


class CaseTimeline(BaseModel):
    case_id: uuid.UUID | None = None
    member_id_hash: str | None = None
    time_range: tuple[datetime, datetime] | None = None
    tenant_id: uuid.UUID
    invocations: list[AgentInvocation] = Field(default_factory=list)
    decision_chain: list[str] = Field(default_factory=list)
    integrity: IntegrityCheck


# Route request models — discriminated by `mode`.

class ReplayCaseRequest(BaseModel):
    mode: Literal["case"] = "case"
    case_id: uuid.UUID


class ReplayMemberRequest(BaseModel):
    mode: Literal["member"] = "member"
    client_id: uuid.UUID
    from_ts: datetime
    to_ts: datetime


class ReplayAgentRequest(BaseModel):
    mode: Literal["agent"] = "agent"
    agent: str
    from_ts: datetime
    to_ts: datetime
```

- [ ] **Step 4: Add `healthflow/forensics/__init__.py` re-exports**

Create `healthflow/forensics/__init__.py`:

```python
"""Audit replay & forensics tool — read-only views over agent_invocation_log
and phi_access_log. See README.md for the contract."""
from healthflow.forensics.schemas import (
    AgentInvocation,
    CaseTimeline,
    IntegrityCheck,
)

__all__ = ["AgentInvocation", "CaseTimeline", "IntegrityCheck"]
```

- [ ] **Step 5: Extend the Makefile test target**

Open `Makefile`. Find the `test:` target (around line 34). Replace the three test targets:

```makefile
test: ## Run all backend tests
	.venv/bin/python -m pytest healthflow/tests/ healthflow/agents/temporal_awareness/tests/ healthflow/forensics/tests/ -v --tb=short

test-quick: ## Run tests without verbose output
	.venv/bin/python -m pytest healthflow/tests/ healthflow/agents/temporal_awareness/tests/ healthflow/forensics/tests/ -q --tb=short

test-cov: ## Run tests with coverage report
	.venv/bin/pip install coverage -q
	.venv/bin/python -m coverage run -m pytest healthflow/tests/ healthflow/agents/temporal_awareness/tests/ healthflow/forensics/tests/ -q --tb=short
	.venv/bin/python -m coverage report --include="healthflow/**" --omit="healthflow/tests/**"
```

- [ ] **Step 6: Smoke test imports**

Run:
```bash
JWT_SECRET="test" PHI_ENCRYPTION_KEY="$(python -c 'import base64; print(base64.b64encode(b"\x00"*32).decode())')" .venv/bin/python -c "from healthflow.database.models import ForensicsAccessLog; from healthflow.forensics.schemas import CaseTimeline, AgentInvocation, IntegrityCheck; from healthflow.forensics import CaseTimeline as Reexport; print('ok:', ForensicsAccessLog.__tablename__)"
```
Expected: `ok: forensics_access_log`

- [ ] **Step 7: Full suite still green**

Run: `make test 2>&1 | tail -3`
Expected: `678 passed, 3 skipped` (no new tests yet; existing suite unaffected).

- [ ] **Step 8: Commit**

```bash
git add healthflow/forensics/ healthflow/database/models.py Makefile
git commit -m "Forensics: package skeleton + ForensicsAccessLog model + schemas"
```

---

## Task 2: Synthetic fixtures

**Files:**
- Create: `healthflow/forensics/tests/conftest.py`
- Create: `healthflow/forensics/tests/fixtures.py`

- [ ] **Step 1: Re-export shared fixtures (same pattern as temporal_awareness/tests/conftest.py)**

Create `healthflow/forensics/tests/conftest.py`:

```python
"""Re-use the shared HealthFlow test fixtures (client, db_session, etc.).

Forensics tests sit outside `healthflow/tests/`, so they don't inherit
that directory's conftest via pytest's normal discovery. Importing the
shared conftest as a module gets both the env-var bootstrap and the
fixtures.
"""
from healthflow.tests.conftest import *  # noqa: F401, F403
```

- [ ] **Step 2: Add synthetic-row helpers**

Create `healthflow/forensics/tests/fixtures.py`:

```python
"""Synthetic AgentInvocationLog + PhiAccessLog row builders for forensics tests.

No live PHI. Every helper accepts overrides for the fields that matter to a
given test; defaults are deterministic so test output is stable.
"""
import uuid
from datetime import datetime, timezone

from healthflow.database.models import AgentInvocationLog, PhiAccessLog


_BASE = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_invocation(
    *,
    agent: str = "comparison",
    event_type: str = "recommend",
    broker_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None = None,
    endpoint: str = "/compare",
    timestamp: datetime | None = None,
    model_used: str | None = "claude-sonnet-4-6",
    duration_ms: int | None = 250,
    details: dict | None = None,
    error: str | None = None,
) -> AgentInvocationLog:
    return AgentInvocationLog(
        id=uuid.uuid4(),
        case_id=case_id,
        broker_id=broker_id,
        endpoint=endpoint,
        agent=agent,
        event_type=event_type,
        model_used=model_used,
        duration_ms=duration_ms,
        details=details if details is not None else {"length": 42},
        error=error,
        created_at=timestamp or _BASE,
    )


def make_phi_access(
    *,
    broker_id: uuid.UUID | None = None,
    table_name: str = "clients",
    operation: str = "select",
    row_ids: list[str] | None = None,
    endpoint: str = "/compare",
    timestamp: datetime | None = None,
) -> PhiAccessLog:
    return PhiAccessLog(
        id=uuid.uuid4(),
        broker_id=broker_id,
        table_name=table_name,
        operation=operation,
        row_ids=row_ids or [],
        row_count=len(row_ids) if row_ids else 0,
        endpoint=endpoint,
        created_at=timestamp or _BASE,
    )
```

- [ ] **Step 3: Commit**

```bash
git add healthflow/forensics/tests/conftest.py healthflow/forensics/tests/fixtures.py
git commit -m "Forensics: test fixtures (synthetic AgentInvocationLog / PhiAccessLog)"
```

---

## Task 3: `replay_case` + 3 tests

**Files:**
- Create: `healthflow/forensics/replay.py` (with `replay_case` only at this stage)
- Create: `healthflow/forensics/tests/test_replay.py` (3 tests)

- [ ] **Step 1: Write the failing tests**

Create `healthflow/forensics/tests/test_replay.py`:

```python
"""Tests for replay_case / replay_member / replay_agent.

Tests pass in db_session_factory (the shared in-memory SQLite from conftest)
so the forensics functions can open their own sessions to seed + query.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from healthflow.database.models import ForensicsAccessLog
from healthflow.forensics.replay import replay_case
from healthflow.forensics.tests.fixtures import make_invocation, make_phi_access


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _seed(db_session, rows):
    for r in rows:
        db_session.add(r)
    await db_session.commit()


@pytest.mark.asyncio
async def test_replay_case_returns_chronological_invocations(db_session, db_session_factory):
    """Invocations for a case_id come back in created_at order."""
    case = uuid.uuid4()
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(case_id=case, broker_id=tenant, agent="comparison", event_type="recommend", timestamp=_T0 + timedelta(seconds=20)),
        make_invocation(case_id=case, broker_id=tenant, agent="harness", event_type="input_validated", timestamp=_T0),
        make_invocation(case_id=case, broker_id=tenant, agent="network", event_type="verify", timestamp=_T0 + timedelta(seconds=40)),
    ])

    timeline = await replay_case(case, tenant_id=tenant, session_factory=db_session_factory)

    assert timeline.case_id == case
    assert timeline.tenant_id == tenant
    assert len(timeline.invocations) == 3
    assert [i.agent for i in timeline.invocations] == ["harness", "comparison", "network"]
    assert timeline.decision_chain == ["input_validated", "recommend", "verify"]


@pytest.mark.asyncio
async def test_replay_case_cross_tenant_returns_empty(db_session, db_session_factory):
    """A case belonging to tenant A queried as tenant B → empty timeline (no info leak)."""
    case = uuid.uuid4()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(case_id=case, broker_id=tenant_a, timestamp=_T0),
    ])

    timeline = await replay_case(case, tenant_id=tenant_b, session_factory=db_session_factory)

    assert timeline.invocations == []
    assert timeline.decision_chain == []


@pytest.mark.asyncio
async def test_replay_case_writes_one_self_audit_row(db_session, db_session_factory):
    case = uuid.uuid4()
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(case_id=case, broker_id=tenant, timestamp=_T0),
    ])

    await replay_case(case, tenant_id=tenant, session_factory=db_session_factory)

    rows = (await db_session.execute(select(ForensicsAccessLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].mode == "case"
    assert rows[0].scope_key == str(case)
    assert rows[0].tenant_id == tenant
    assert rows[0].result_count == 1
    assert rows[0].operator_id == tenant  # operator defaults to the calling tenant_id
```

- [ ] **Step 2: Run tests — they fail (module not found)**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_replay.py -v`
Expected: ImportError / ModuleNotFoundError on `healthflow.forensics.replay`.

- [ ] **Step 3: Implement `replay_case`**

Create `healthflow/forensics/replay.py`:

```python
"""Read-only forensics query functions over agent_invocation_log + phi_access_log.

Each function:
  1. Opens a session via the passed-in async_sessionmaker.
  2. Filters by `broker_id = tenant_id` (cross-tenant isolation).
  3. Joins to phi_access_log on (broker_id, created_at ± PHI_JOIN_WINDOW).
  4. Runs integrity.check() → IntegrityCheck.
  5. Passes the output through redaction.redact().
  6. Writes exactly one ForensicsAccessLog row.
  7. Returns the timeline (or empty for cross-tenant / no-data cases).
"""
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.database.models import (
    AgentInvocationLog,
    ForensicsAccessLog,
    PhiAccessLog,
)
from healthflow.forensics import integrity as integrity_mod
from healthflow.forensics import redaction as redaction_mod
from healthflow.forensics.schemas import (
    AgentInvocation,
    CaseTimeline,
    IntegrityCheck,
)

# Window for joining agent invocations to PHI access records. Empirically,
# an agent's invocation_log row and its first DB read land within ~1s.
PHI_JOIN_WINDOW = timedelta(seconds=2)

# `details_summary` max chars after redaction.
DETAILS_SUMMARY_MAX = 200


async def replay_case(
    case_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> CaseTimeline:
    async with session_factory() as session:
        rows = (await session.execute(
            select(AgentInvocationLog)
            .where(
                AgentInvocationLog.case_id == case_id,
                AgentInvocationLog.broker_id == tenant_id,
            )
            .order_by(AgentInvocationLog.created_at.asc())
        )).scalars().all()

        invocations = await _enrich_with_phi(session, rows, tenant_id)
        time_range = _time_range(rows)

        integrity = integrity_mod.check(invocations, scope="case", scope_key=str(case_id))
        timeline = CaseTimeline(
            case_id=case_id,
            tenant_id=tenant_id,
            time_range=time_range,
            invocations=invocations,
            decision_chain=[i.event_type for i in invocations],
            integrity=integrity,
        )
        timeline = redaction_mod.redact(timeline)

        await _write_self_audit(
            session,
            operator_id=tenant_id,
            mode="case",
            scope_key=str(case_id),
            tenant_id=tenant_id,
            from_ts=None,
            to_ts=None,
            result_count=len(invocations),
        )
        await session.commit()
        return timeline


# ── helpers ───────────────────────────────────────────────────────────────


async def _enrich_with_phi(
    session, rows: list[AgentInvocationLog], tenant_id: uuid.UUID
) -> list[AgentInvocation]:
    """For each invocation, attach phi_tables_touched + phi_row_count from
    PhiAccessLog rows within PHI_JOIN_WINDOW for the same broker."""
    out: list[AgentInvocation] = []
    for r in rows:
        window_start = r.created_at - PHI_JOIN_WINDOW
        window_end = r.created_at + PHI_JOIN_WINDOW
        phi_rows = (await session.execute(
            select(PhiAccessLog).where(
                PhiAccessLog.broker_id == tenant_id,
                PhiAccessLog.created_at >= window_start,
                PhiAccessLog.created_at <= window_end,
            )
        )).scalars().all()

        tables = sorted({p.table_name for p in phi_rows})
        row_count = sum(p.row_count for p in phi_rows)

        details_summary = json.dumps(r.details or {})[:DETAILS_SUMMARY_MAX]

        out.append(AgentInvocation(
            agent=r.agent,
            invocation_id=r.id,
            timestamp=r.created_at,
            case_id=r.case_id,
            endpoint=r.endpoint,
            event_type=r.event_type,
            model_used=r.model_used,
            duration_ms=r.duration_ms,
            details_summary=details_summary,
            error=r.error,
            phi_tables_touched=tables,
            phi_row_count=row_count,
        ))
    return out


def _time_range(rows: list[AgentInvocationLog]) -> tuple[datetime, datetime] | None:
    if not rows:
        return None
    return (rows[0].created_at, rows[-1].created_at)


async def _write_self_audit(
    session,
    *,
    operator_id: uuid.UUID,
    mode: str,
    scope_key: str,
    tenant_id: uuid.UUID | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
    result_count: int,
) -> None:
    session.add(ForensicsAccessLog(
        operator_id=operator_id,
        mode=mode,
        scope_key=scope_key,
        tenant_id=tenant_id,
        from_ts=from_ts,
        to_ts=to_ts,
        result_count=result_count,
    ))
```

- [ ] **Step 4: Create stub `integrity.py` + `redaction.py` so imports resolve**

Create `healthflow/forensics/integrity.py`:

```python
"""Integrity checks for forensics timelines. Detailed implementation in Task 5."""
from healthflow.forensics.schemas import AgentInvocation, IntegrityCheck


def check(invocations: list[AgentInvocation], *, scope: str, scope_key: str) -> IntegrityCheck:
    """Stub — replaced with the full implementation in Task 5."""
    return IntegrityCheck(entries_found=len(invocations))
```

Create `healthflow/forensics/redaction.py`:

```python
"""Output redaction. Detailed implementation in Task 6."""
from healthflow.forensics.schemas import CaseTimeline


def redact(timeline: CaseTimeline) -> CaseTimeline:
    """Stub — replaced with the full implementation in Task 6."""
    return timeline
```

- [ ] **Step 5: Run tests — they pass**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_replay.py -v`
Expected: 3 passed.

- [ ] **Step 6: Full suite still green**

Run: `make test 2>&1 | tail -3`
Expected: 681 passed, 3 skipped (678 + 3 new).

- [ ] **Step 7: Commit**

```bash
git add healthflow/forensics/replay.py healthflow/forensics/integrity.py healthflow/forensics/redaction.py healthflow/forensics/tests/test_replay.py
git commit -m "Forensics: replay_case + self-audit + cross-tenant isolation (3 tests)"
```

---

## Task 4: `replay_member` + `replay_agent` + 5 more tests

**Files:**
- Modify: `healthflow/forensics/replay.py` (add `replay_member`, `replay_agent`)
- Modify: `healthflow/forensics/tests/test_replay.py` (append 5 tests)
- Modify: `healthflow/forensics/__init__.py` (export the new functions)

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/forensics/tests/test_replay.py`:

```python
@pytest.mark.asyncio
async def test_replay_member_joins_through_phi_access_log(db_session, db_session_factory):
    """A member-scope query finds invocations whose ±2s PHI access includes the client_id."""
    tenant = uuid.uuid4()
    client = uuid.uuid4()
    other_client = uuid.uuid4()

    inv = make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0)
    # PHI access for `client` at the same timestamp — matches.
    phi_hit = make_phi_access(broker_id=tenant, row_ids=[str(client), str(other_client)], timestamp=_T0)
    # Unrelated invocation (no PHI access for `client`).
    unrelated = make_invocation(broker_id=tenant, agent="translation", timestamp=_T0 + timedelta(minutes=10))
    await _seed(db_session, [inv, phi_hit, unrelated])

    from healthflow.forensics.replay import replay_member
    timeline = await replay_member(
        client,
        time_range=(_T0 - timedelta(seconds=10), _T0 + timedelta(minutes=20)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    assert len(timeline.invocations) == 1
    assert timeline.invocations[0].agent == "comparison"
    assert timeline.member_id_hash is not None  # SHA-256 prefix
    assert str(client) not in timeline.member_id_hash  # never the raw value


@pytest.mark.asyncio
async def test_replay_member_honors_time_range(db_session, db_session_factory):
    tenant = uuid.uuid4()
    client = uuid.uuid4()
    inv_in = make_invocation(broker_id=tenant, timestamp=_T0)
    phi_in = make_phi_access(broker_id=tenant, row_ids=[str(client)], timestamp=_T0)
    inv_out = make_invocation(broker_id=tenant, timestamp=_T0 + timedelta(days=5))
    phi_out = make_phi_access(broker_id=tenant, row_ids=[str(client)], timestamp=_T0 + timedelta(days=5))
    await _seed(db_session, [inv_in, phi_in, inv_out, phi_out])

    from healthflow.forensics.replay import replay_member
    timeline = await replay_member(
        client,
        time_range=(_T0 - timedelta(hours=1), _T0 + timedelta(hours=1)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    assert len(timeline.invocations) == 1
    assert timeline.invocations[0].timestamp == _T0


@pytest.mark.asyncio
async def test_replay_agent_filters_by_agent_and_time(db_session, db_session_factory):
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0),
        make_invocation(broker_id=tenant, agent="network", timestamp=_T0 + timedelta(seconds=10)),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(seconds=20)),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(days=10)),  # out of range
    ])

    from healthflow.forensics.replay import replay_agent
    invocations = await replay_agent(
        "comparison",
        time_range=(_T0 - timedelta(seconds=1), _T0 + timedelta(hours=1)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    assert len(invocations) == 2
    assert all(i.agent == "comparison" for i in invocations)


@pytest.mark.asyncio
async def test_replay_agent_returns_chronological_order(db_session, db_session_factory):
    tenant = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(seconds=30)),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0),
        make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0 + timedelta(seconds=15)),
    ])

    from healthflow.forensics.replay import replay_agent
    invocations = await replay_agent(
        "comparison",
        time_range=(_T0 - timedelta(seconds=1), _T0 + timedelta(hours=1)),
        tenant_id=tenant,
        session_factory=db_session_factory,
    )

    timestamps = [i.timestamp for i in invocations]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_all_three_functions_write_one_self_audit_row_each(db_session, db_session_factory):
    """Sanity check: every replay call writes exactly one ForensicsAccessLog row."""
    tenant = uuid.uuid4()
    client = uuid.uuid4()
    case = uuid.uuid4()
    await _seed(db_session, [
        make_invocation(broker_id=tenant, case_id=case, timestamp=_T0),
        make_phi_access(broker_id=tenant, row_ids=[str(client)], timestamp=_T0),
    ])

    from healthflow.forensics.replay import replay_case, replay_member, replay_agent
    await replay_case(case, tenant_id=tenant, session_factory=db_session_factory)
    await replay_member(client, time_range=(_T0 - timedelta(hours=1), _T0 + timedelta(hours=1)), tenant_id=tenant, session_factory=db_session_factory)
    await replay_agent("comparison", time_range=(_T0 - timedelta(hours=1), _T0 + timedelta(hours=1)), tenant_id=tenant, session_factory=db_session_factory)

    rows = (await db_session.execute(select(ForensicsAccessLog))).scalars().all()
    assert {r.mode for r in rows} == {"case", "member", "agent"}
    assert len(rows) == 3
```

- [ ] **Step 2: Run tests — they fail**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_replay.py -v 2>&1 | tail -10`
Expected: 5 failures (ImportError on `replay_member` / `replay_agent`).

- [ ] **Step 3: Implement `replay_member` + `replay_agent`**

Open `healthflow/forensics/replay.py`. Append at the end:

```python


async def replay_member(
    client_id: uuid.UUID,
    *,
    time_range: tuple[datetime, datetime],
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> CaseTimeline:
    """Reconstruct the timeline of agent invocations that accessed this client.

    Two-step join: find phi_access_log rows containing this client_id within
    the time range, then pull agent_invocation_log rows ±PHI_JOIN_WINDOW
    around each PHI access (same broker = tenant_id).
    """
    from_ts, to_ts = time_range
    async with session_factory() as session:
        # Step 1: find PHI accesses that touched this client.
        # SQLAlchemy can't easily express "client_id_str in row_ids JSON list"
        # portably across SQLite/Postgres, so we scan candidate rows by
        # (broker_id, time_range) and filter in Python.
        client_id_str = str(client_id)
        phi_candidates = (await session.execute(
            select(PhiAccessLog).where(
                PhiAccessLog.broker_id == tenant_id,
                PhiAccessLog.created_at >= from_ts,
                PhiAccessLog.created_at <= to_ts,
            )
        )).scalars().all()
        matching_phi = [p for p in phi_candidates if client_id_str in (p.row_ids or [])]

        # Step 2: pull invocations within ±PHI_JOIN_WINDOW of each matching access.
        invocations_rows: list[AgentInvocationLog] = []
        seen_ids: set[uuid.UUID] = set()
        for phi in matching_phi:
            window_start = phi.created_at - PHI_JOIN_WINDOW
            window_end = phi.created_at + PHI_JOIN_WINDOW
            inv_rows = (await session.execute(
                select(AgentInvocationLog).where(
                    AgentInvocationLog.broker_id == tenant_id,
                    AgentInvocationLog.created_at >= window_start,
                    AgentInvocationLog.created_at <= window_end,
                ).order_by(AgentInvocationLog.created_at.asc())
            )).scalars().all()
            for row in inv_rows:
                if row.id not in seen_ids:
                    invocations_rows.append(row)
                    seen_ids.add(row.id)

        invocations_rows.sort(key=lambda r: r.created_at)

        invocations = await _enrich_with_phi(session, invocations_rows, tenant_id)
        integrity = integrity_mod.check(invocations, scope="member", scope_key=client_id_str)

        timeline = CaseTimeline(
            case_id=None,
            member_id_hash=_hash_client_id(client_id),
            tenant_id=tenant_id,
            time_range=(from_ts, to_ts),
            invocations=invocations,
            decision_chain=[i.event_type for i in invocations],
            integrity=integrity,
        )
        timeline = redaction_mod.redact(timeline)

        await _write_self_audit(
            session,
            operator_id=tenant_id,
            mode="member",
            scope_key=client_id_str,
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            result_count=len(invocations),
        )
        await session.commit()
        return timeline


async def replay_agent(
    agent: str,
    *,
    time_range: tuple[datetime, datetime],
    tenant_id: uuid.UUID,
    session_factory: async_sessionmaker,
) -> list[AgentInvocation]:
    """Invocations of a specific agent within a time range, for one tenant."""
    from_ts, to_ts = time_range
    async with session_factory() as session:
        rows = (await session.execute(
            select(AgentInvocationLog).where(
                AgentInvocationLog.agent == agent,
                AgentInvocationLog.broker_id == tenant_id,
                AgentInvocationLog.created_at >= from_ts,
                AgentInvocationLog.created_at <= to_ts,
            ).order_by(AgentInvocationLog.created_at.asc())
        )).scalars().all()

        invocations = await _enrich_with_phi(session, rows, tenant_id)

        await _write_self_audit(
            session,
            operator_id=tenant_id,
            mode="agent",
            scope_key=agent,
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            result_count=len(invocations),
        )
        await session.commit()
        return invocations


def _hash_client_id(client_id: uuid.UUID) -> str:
    """SHA-256 prefix — sufficient for case correlation, not reversible."""
    import hashlib
    return hashlib.sha256(str(client_id).encode()).hexdigest()[:16]
```

- [ ] **Step 4: Update `healthflow/forensics/__init__.py` to re-export**

Open `healthflow/forensics/__init__.py`. Replace the contents:

```python
"""Audit replay & forensics tool — read-only views over agent_invocation_log
and phi_access_log. See README.md for the contract."""
from healthflow.forensics.replay import replay_agent, replay_case, replay_member
from healthflow.forensics.schemas import (
    AgentInvocation,
    CaseTimeline,
    IntegrityCheck,
)

__all__ = [
    "AgentInvocation",
    "CaseTimeline",
    "IntegrityCheck",
    "replay_agent",
    "replay_case",
    "replay_member",
]
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_replay.py -v`
Expected: 8 passed.

- [ ] **Step 6: Full suite green**

Run: `make test 2>&1 | tail -3`
Expected: 686 passed, 3 skipped.

- [ ] **Step 7: Commit**

```bash
git add healthflow/forensics/replay.py healthflow/forensics/__init__.py healthflow/forensics/tests/test_replay.py
git commit -m "Forensics: replay_member + replay_agent + 5 more tests"
```

---

## Task 5: `integrity.check` — gap detection + error clusters + 5 tests

**Files:**
- Modify: `healthflow/forensics/integrity.py` (full implementation)
- Create: `healthflow/forensics/tests/test_integrity.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/forensics/tests/test_integrity.py`:

```python
"""Tests for integrity.check — gap detection, error clusters, tamper evidence."""
import uuid
from datetime import datetime, timedelta, timezone

from healthflow.forensics.integrity import check
from healthflow.forensics.schemas import AgentInvocation


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _inv(*, ts: datetime, case_id=None, error=None, agent="comparison", event_type="recommend") -> AgentInvocation:
    return AgentInvocation(
        agent=agent,
        invocation_id=uuid.uuid4(),
        timestamp=ts,
        case_id=case_id,
        endpoint="/compare",
        event_type=event_type,
        model_used="claude-sonnet-4-6",
        duration_ms=200,
        details_summary="{}",
        error=error,
    )


def test_clean_timeline_has_no_gaps_or_notes():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case),
        _inv(ts=_T0 + timedelta(seconds=30), case_id=case),
        _inv(ts=_T0 + timedelta(seconds=60), case_id=case),
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert result.entries_found == 3
    assert result.gaps_detected == []
    assert result.notes == []
    assert result.tamper_evidence == "unknown"


def test_chronological_gap_over_5_minutes_is_noted():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case),
        _inv(ts=_T0 + timedelta(minutes=10), case_id=case),  # 10-minute gap
        _inv(ts=_T0 + timedelta(minutes=11), case_id=case),
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert any("gap" in n.lower() for n in result.notes)


def test_three_consecutive_errors_flagged_as_error_cluster():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case, error="RuntimeError: boom"),
        _inv(ts=_T0 + timedelta(seconds=10), case_id=case, error="RuntimeError: boom"),
        _inv(ts=_T0 + timedelta(seconds=20), case_id=case, error="RuntimeError: boom"),
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert any("error cluster" in g.lower() for g in result.gaps_detected)


def test_case_scope_with_invocation_missing_case_id_is_flagged():
    case = uuid.uuid4()
    invs = [
        _inv(ts=_T0, case_id=case),
        _inv(ts=_T0 + timedelta(seconds=10), case_id=None),  # should be impossible
    ]
    result = check(invs, scope="case", scope_key=str(case))
    assert any("no case_id" in g.lower() for g in result.gaps_detected)


def test_tamper_evidence_is_always_unknown_for_now():
    """Until hash-chain ships, this PR returns 'unknown'."""
    result = check([], scope="case", scope_key=str(uuid.uuid4()))
    assert result.tamper_evidence == "unknown"
```

- [ ] **Step 2: Run tests — they fail (stub returns empty)**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_integrity.py -v 2>&1 | tail -10`
Expected: 4 failures (clean test passes by accident on stub).

- [ ] **Step 3: Implement `integrity.check`**

Replace `healthflow/forensics/integrity.py`:

```python
"""Integrity checks for forensics timelines.

Four passes:
  1. Chronological gaps within a case scope — note any gap > 5 minutes.
  2. Error clusters — 3+ consecutive non-null errors → flag.
  3. Missing case_id under case scope — would mean a row matched the case
     filter but reports no case_id; should be impossible. Flag if seen.
  4. tamper_evidence — always "unknown" until a hash-chain ships.
"""
from datetime import timedelta

from healthflow.forensics.schemas import AgentInvocation, IntegrityCheck


_GAP_THRESHOLD = timedelta(minutes=5)
_ERROR_CLUSTER_MIN = 3


def check(
    invocations: list[AgentInvocation],
    *,
    scope: str,
    scope_key: str,
) -> IntegrityCheck:
    gaps: list[str] = []
    notes: list[str] = []

    # 1 — chronological gaps
    for i in range(1, len(invocations)):
        delta = invocations[i].timestamp - invocations[i - 1].timestamp
        if delta > _GAP_THRESHOLD:
            notes.append(
                f"{int(delta.total_seconds())}s gap between invocations "
                f"{i} and {i + 1} (over {int(_GAP_THRESHOLD.total_seconds())}s threshold)"
            )

    # 2 — error clusters
    run_start: int | None = None
    for i, inv in enumerate(invocations):
        if inv.error:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= _ERROR_CLUSTER_MIN:
                gaps.append(f"error cluster: invocations {run_start + 1}..{i} all failed")
            run_start = None
    # Flush trailing run.
    if run_start is not None and (len(invocations) - run_start) >= _ERROR_CLUSTER_MIN:
        gaps.append(
            f"error cluster: invocations {run_start + 1}..{len(invocations)} all failed"
        )

    # 3 — case scope: invocations with no case_id shouldn't have matched
    if scope == "case":
        for i, inv in enumerate(invocations):
            if inv.case_id is None:
                gaps.append(
                    f"invocation {i + 1} ({inv.invocation_id}) matched case scope "
                    f"but has no case_id"
                )

    # 4 — tamper evidence: future hash-chain work
    return IntegrityCheck(
        entries_found=len(invocations),
        gaps_detected=gaps,
        tamper_evidence="unknown",
        notes=notes,
    )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_integrity.py -v`
Expected: 5 passed.

- [ ] **Step 5: Full suite green**

Run: `make test 2>&1 | tail -3`
Expected: 691 passed, 3 skipped.

- [ ] **Step 6: Commit**

```bash
git add healthflow/forensics/integrity.py healthflow/forensics/tests/test_integrity.py
git commit -m "Forensics: integrity.check (gap detection + error clusters + 5 tests)"
```

---

## Task 6: `redaction.redact` + 3 tests

**Files:**
- Modify: `healthflow/forensics/redaction.py` (full implementation)
- Create: `healthflow/forensics/tests/test_redaction.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/forensics/tests/test_redaction.py`:

```python
"""Defense-in-depth: redact PHI patterns from forensics output before return."""
import uuid
from datetime import datetime, timezone

from healthflow.forensics.redaction import redact
from healthflow.forensics.schemas import (
    AgentInvocation,
    CaseTimeline,
    IntegrityCheck,
)


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _timeline_with_details(details_summary: str) -> CaseTimeline:
    inv = AgentInvocation(
        agent="appeal",
        invocation_id=uuid.uuid4(),
        timestamp=_T0,
        case_id=uuid.uuid4(),
        endpoint="/appeal",
        event_type="process_appeal",
        details_summary=details_summary,
    )
    return CaseTimeline(
        tenant_id=uuid.uuid4(),
        invocations=[inv],
        integrity=IntegrityCheck(entries_found=1),
    )


def test_redacts_ssn_pattern_in_details_summary():
    raw = "Patient: John Doe SSN 123-45-6789 visited"
    timeline = _timeline_with_details(raw)
    out = redact(timeline)
    summary = out.invocations[0].details_summary
    assert "123-45-6789" not in summary
    assert "[SSN]" in summary or "[REDACTED]" in summary.upper()


def test_redacts_patient_name_label():
    raw = "Patient: Jane Smith was treated for"
    timeline = _timeline_with_details(raw)
    out = redact(timeline)
    summary = out.invocations[0].details_summary
    assert "Jane Smith" not in summary


def test_truncates_details_summary_to_200_chars():
    raw = "x" * 500
    timeline = _timeline_with_details(raw)
    out = redact(timeline)
    assert len(out.invocations[0].details_summary) <= 200
```

- [ ] **Step 2: Run tests — they fail (stub returns input unchanged)**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_redaction.py -v 2>&1 | tail -10`
Expected: 3 failures.

- [ ] **Step 3: Implement `redaction.redact`**

Replace `healthflow/forensics/redaction.py`:

```python
"""Output redaction for forensics timelines.

Defense-in-depth: agents should never write PHI to `details` in the first
place (that's the contract documented in healthflow-security skill). But
forensics is a high-trust read surface, so we run every string-valued
output field through PHIRedactor before returning.
"""
from healthflow.forensics.schemas import AgentInvocation, CaseTimeline
from healthflow.tools.phi_redactor import PHIRedactor

_DETAILS_SUMMARY_MAX = 200
_redactor = PHIRedactor()


def _redact_text(text: str) -> str:
    redacted, _ = _redactor.redact(text)
    return redacted


def _redact_invocation(inv: AgentInvocation) -> AgentInvocation:
    summary = _redact_text(inv.details_summary)[:_DETAILS_SUMMARY_MAX]
    error = _redact_text(inv.error) if inv.error else None
    return inv.model_copy(update={"details_summary": summary, "error": error})


def redact(timeline: CaseTimeline) -> CaseTimeline:
    """Walk the timeline, redact PHI patterns from every string field, truncate
    long summaries. Returns a NEW CaseTimeline; does not mutate the input."""
    redacted_invocations = [_redact_invocation(i) for i in timeline.invocations]
    return timeline.model_copy(update={"invocations": redacted_invocations})
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_redaction.py -v`
Expected: 3 passed.

- [ ] **Step 5: Full suite green**

Run: `make test 2>&1 | tail -3`
Expected: 694 passed, 3 skipped.

- [ ] **Step 6: Commit**

```bash
git add healthflow/forensics/redaction.py healthflow/forensics/tests/test_redaction.py
git commit -m "Forensics: redaction.redact (PHI patterns + 200-char truncation + 3 tests)"
```

---

## Task 7: `POST /forensics/replay` route + mount + 4 tests

**Files:**
- Create: `healthflow/forensics/routes.py`
- Modify: `healthflow/main.py` (mount the router)
- Create: `healthflow/forensics/tests/test_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/forensics/tests/test_routes.py`:

```python
"""End-to-end tests for POST /forensics/replay.

Uses the `client` fixture from the shared conftest. Auth is admin-only.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update as sa_update

from healthflow.database.models import Broker
from healthflow.forensics.tests.fixtures import make_invocation


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _make_admin(client, db_session, email="admin@example.com", password="Cromulent42!"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Admin"},
    )
    assert reg.status_code == 201
    await db_session.execute(
        sa_update(Broker).where(Broker.email == email).values(role="admin")
    )
    await db_session.commit()
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    body = login.json()
    broker = (await db_session.execute(select(Broker).where(Broker.email == email))).scalar_one()
    return body["access_token"], broker.id


@pytest.mark.asyncio
async def test_admin_case_replay_returns_200_with_timeline(client, db_session):
    access, broker_id = await _make_admin(client, db_session)
    case = uuid.uuid4()
    db_session.add(make_invocation(case_id=case, broker_id=broker_id, agent="comparison", timestamp=_T0))
    await db_session.commit()

    resp = await client.post(
        "/forensics/replay",
        headers={"Authorization": f"Bearer {access}"},
        json={"mode": "case", "case_id": str(case)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == str(case)
    assert len(body["invocations"]) == 1


@pytest.mark.asyncio
async def test_non_admin_gets_403(client):
    reg = await client.post(
        "/auth/register",
        json={"email": "broker@example.com", "password": "Cromulent42!", "full_name": "Broker"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/auth/login", json={"email": "broker@example.com", "password": "Cromulent42!"}
    )
    access = login.json()["access_token"]

    resp = await client.post(
        "/forensics/replay",
        headers={"Authorization": f"Bearer {access}"},
        json={"mode": "case", "case_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_gets_401(client):
    resp = await client.post(
        "/forensics/replay",
        json={"mode": "case", "case_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_case_returns_empty_not_404(client, db_session):
    """A case belonging to a different broker queried as the admin →
    200 with empty invocations (no info leak)."""
    access, admin_id = await _make_admin(client, db_session)
    case = uuid.uuid4()
    other_broker = uuid.uuid4()
    db_session.add(make_invocation(case_id=case, broker_id=other_broker, timestamp=_T0))
    await db_session.commit()

    resp = await client.post(
        "/forensics/replay",
        headers={"Authorization": f"Bearer {access}"},
        json={"mode": "case", "case_id": str(case)},
    )
    assert resp.status_code == 200
    assert resp.json()["invocations"] == []
```

- [ ] **Step 2: Run tests — they fail (route doesn't exist)**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_routes.py -v 2>&1 | tail -10`
Expected: all 4 failures (404 or auth chain issues).

- [ ] **Step 3: Implement the route**

Create `healthflow/forensics/routes.py`:

```python
"""FastAPI router: POST /forensics/replay.

Admin-only. tenant_id is the authenticated admin's broker_id — never
read from the request body (prevents spoofing). Returns CaseTimeline
for case/member modes, list[AgentInvocation] for agent mode.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.dependencies import require_admin
from healthflow.database.config import async_session_factory
from healthflow.database.models import Broker
from healthflow.forensics.replay import (
    replay_agent,
    replay_case,
    replay_member,
)
from healthflow.forensics.schemas import (
    ReplayAgentRequest,
    ReplayCaseRequest,
    ReplayMemberRequest,
)

forensics_router = APIRouter(prefix="/forensics", tags=["forensics"])


class _ReplayRequest(BaseModel):
    """Discriminated union — actual validation happens via the three concrete
    request models, dispatched on `mode`."""
    mode: str


def _get_session_factory() -> async_sessionmaker:
    """Indirection point so tests can monkeypatch."""
    return async_session_factory


@forensics_router.post("/replay")
async def replay(
    body: dict,
    admin: Broker = Depends(require_admin),
) -> Any:
    mode = body.get("mode")
    factory = _get_session_factory()

    if mode == "case":
        req = ReplayCaseRequest.model_validate(body)
        return await replay_case(req.case_id, tenant_id=admin.id, session_factory=factory)

    if mode == "member":
        req = ReplayMemberRequest.model_validate(body)
        return await replay_member(
            req.client_id,
            time_range=(req.from_ts, req.to_ts),
            tenant_id=admin.id,
            session_factory=factory,
        )

    if mode == "agent":
        req = ReplayAgentRequest.model_validate(body)
        return await replay_agent(
            req.agent,
            time_range=(req.from_ts, req.to_ts),
            tenant_id=admin.id,
            session_factory=factory,
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown mode: {mode!r}",
    )
```

- [ ] **Step 4: Mount in `healthflow/main.py`**

Open `healthflow/main.py`. After the `from healthflow.agents.temporal_awareness.routes import temporal_router` line, add:

```python
from healthflow.forensics.routes import forensics_router
```

After the `app.include_router(temporal_router)` line, add:

```python
app.include_router(forensics_router)
```

- [ ] **Step 5: Make the tests pick up the test session factory**

The route's `_get_session_factory()` returns the production async_session_factory. In tests, the `client` fixture overrides `get_db` but NOT this private helper. Patch it via FastAPI's `app.dependency_overrides` or just monkeypatch the symbol.

Update `healthflow/forensics/tests/test_routes.py` — add a fixture at the top that monkeypatches the session factory on each test:

```python
@pytest.fixture(autouse=True)
def _override_forensics_session_factory(db_session_factory, monkeypatch):
    """Make /forensics/replay use the in-memory test factory, same DB as the
    `client` fixture so seeded rows are visible."""
    from healthflow.forensics import routes as forensics_routes
    monkeypatch.setattr(forensics_routes, "_get_session_factory", lambda: db_session_factory)
```

Place the fixture immediately after the imports + before `_make_admin`.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_routes.py -v`
Expected: 4 passed.

- [ ] **Step 7: Full suite green**

Run: `make test 2>&1 | tail -3`
Expected: 698 passed, 3 skipped.

- [ ] **Step 8: Commit**

```bash
git add healthflow/forensics/routes.py healthflow/main.py healthflow/forensics/tests/test_routes.py
git commit -m "Forensics: POST /forensics/replay (admin-only) + 4 tests"
```

---

## Task 8: CLI + 2 tests

**Files:**
- Create: `healthflow/forensics/cli.py`
- Create: `healthflow/forensics/__main__.py`
- Create: `healthflow/forensics/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `healthflow/forensics/tests/test_cli.py`:

```python
"""CLI tests using click's CliRunner. No live DB — monkeypatches the
session factory to point at the in-memory test DB."""
import json
import uuid
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from healthflow.forensics.cli import cli
from healthflow.forensics.tests.fixtures import make_invocation


_T0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def _patch_cli_factory(db_session_factory, monkeypatch):
    from healthflow.forensics import cli as cli_mod
    monkeypatch.setattr(cli_mod, "_get_session_factory", lambda: db_session_factory)


@pytest.mark.asyncio
async def test_cli_case_json_emits_parseable_output(_patch_cli_factory, db_session):
    tenant = uuid.uuid4()
    case = uuid.uuid4()
    db_session.add(make_invocation(case_id=case, broker_id=tenant, timestamp=_T0))
    await db_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["replay", "case", str(case), "--tenant-id", str(tenant), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["case_id"] == str(case)
    assert len(body["invocations"]) == 1


@pytest.mark.asyncio
async def test_cli_agent_text_format_runs_and_exits_zero(_patch_cli_factory, db_session):
    tenant = uuid.uuid4()
    db_session.add(make_invocation(broker_id=tenant, agent="comparison", timestamp=_T0))
    await db_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "replay", "agent", "comparison",
            "--tenant-id", str(tenant),
            "--from", "2026-04-01T00:00:00",
            "--to", "2026-06-01T00:00:00",
            "--format", "text",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "comparison" in result.output
```

- [ ] **Step 2: Run tests — they fail (no CLI)**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_cli.py -v 2>&1 | tail -5`
Expected: 2 failures (ModuleNotFoundError).

- [ ] **Step 3: Implement the CLI**

Create `healthflow/forensics/cli.py`:

```python
"""click CLI for the forensics replay tool.

Usage:
    python -m healthflow.forensics replay case <case_id> --tenant-id <uuid>
    python -m healthflow.forensics replay member <client_id> --tenant-id <uuid> --from <iso> --to <iso>
    python -m healthflow.forensics replay agent <agent> --tenant-id <uuid> --from <iso> --to <iso>

Operator identity for the self-audit row uses the supplied --tenant-id
(same value used to scope the query). The CLI does not infer a separate
operator; document this constraint in the README.
"""
import asyncio
import json
import uuid
from datetime import datetime

import click

from healthflow.database.config import async_session_factory
from healthflow.forensics.replay import (
    replay_agent,
    replay_case,
    replay_member,
)


def _get_session_factory():
    """Indirection point so tests can monkeypatch."""
    return async_session_factory


@click.group()
def cli():
    """HealthFlow forensics — read-only audit replay over agent_invocation_log."""


@cli.group("replay")
def replay_group():
    """Replay an agent timeline by case / member / agent."""


def _emit(result_dict, fmt: str) -> None:
    if fmt == "json":
        click.echo(json.dumps(result_dict, default=str, indent=2))
        return
    # Text format — compact human summary.
    if "invocations" in result_dict:
        click.echo(f"Case: {result_dict.get('case_id')}")
        click.echo(f"Tenant: {result_dict.get('tenant_id')}")
        click.echo(f"{len(result_dict['invocations'])} invocations")
        for inv in result_dict["invocations"]:
            click.echo(
                f"  {inv['timestamp']}  {inv['agent']:>20}  {inv['event_type']:>20}"
                f"  ({inv.get('duration_ms', '?')}ms)"
            )
        if result_dict.get("integrity", {}).get("notes"):
            click.echo("Notes:")
            for note in result_dict["integrity"]["notes"]:
                click.echo(f"  - {note}")
    else:
        # list[AgentInvocation] from replay_agent
        click.echo(f"{len(result_dict)} invocations")
        for inv in result_dict:
            click.echo(
                f"  {inv['timestamp']}  {inv['agent']:>20}  {inv['event_type']:>20}"
                f"  ({inv.get('duration_ms', '?')}ms)"
            )


@replay_group.command("case")
@click.argument("case_id")
@click.option("--tenant-id", required=True, help="Tenant (broker) UUID to scope to.")
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def cli_case(case_id, tenant_id, fmt):
    """Replay an agent timeline for a case_id."""
    factory = _get_session_factory()
    timeline = asyncio.run(replay_case(
        uuid.UUID(case_id), tenant_id=uuid.UUID(tenant_id), session_factory=factory
    ))
    _emit(timeline.model_dump(mode="json"), fmt)


@replay_group.command("member")
@click.argument("client_id")
@click.option("--tenant-id", required=True)
@click.option("--from", "from_ts", required=True, help="ISO 8601 datetime (e.g. 2026-04-01T00:00:00).")
@click.option("--to", "to_ts", required=True)
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def cli_member(client_id, tenant_id, from_ts, to_ts, fmt):
    """Replay agent invocations that accessed a client within a time range."""
    factory = _get_session_factory()
    timeline = asyncio.run(replay_member(
        uuid.UUID(client_id),
        time_range=(datetime.fromisoformat(from_ts), datetime.fromisoformat(to_ts)),
        tenant_id=uuid.UUID(tenant_id),
        session_factory=factory,
    ))
    _emit(timeline.model_dump(mode="json"), fmt)


@replay_group.command("agent")
@click.argument("agent")
@click.option("--tenant-id", required=True)
@click.option("--from", "from_ts", required=True)
@click.option("--to", "to_ts", required=True)
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="text")
def cli_agent(agent, tenant_id, from_ts, to_ts, fmt):
    """Replay invocations of a specific agent in a time range."""
    factory = _get_session_factory()
    invocations = asyncio.run(replay_agent(
        agent,
        time_range=(datetime.fromisoformat(from_ts), datetime.fromisoformat(to_ts)),
        tenant_id=uuid.UUID(tenant_id),
        session_factory=factory,
    ))
    _emit([i.model_dump(mode="json") for i in invocations], fmt)


if __name__ == "__main__":
    cli()
```

Create `healthflow/forensics/__main__.py`:

```python
"""Entry point so `python -m healthflow.forensics ...` works."""
from healthflow.forensics.cli import cli

if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest healthflow/forensics/tests/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Manual smoke test**

Run: `.venv/bin/python -m healthflow.forensics --help`
Expected: lists `replay` group.

Run: `.venv/bin/python -m healthflow.forensics replay --help`
Expected: lists `case` / `member` / `agent` subcommands.

- [ ] **Step 6: Full suite green**

Run: `make test 2>&1 | tail -3`
Expected: 700 passed, 3 skipped.

- [ ] **Step 7: Commit**

```bash
git add healthflow/forensics/cli.py healthflow/forensics/__main__.py healthflow/forensics/tests/test_cli.py
git commit -m "Forensics: CLI with case/member/agent verbs + 2 tests"
```

---

## Task 9: README

**Files:**
- Create: `healthflow/forensics/README.md`

- [ ] **Step 1: Write the README**

Create `healthflow/forensics/README.md`:

```markdown
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
.venv/bin/python -m pytest healthflow/forensics/tests/ -v

# Or via make (also runs the rest of the suite)
make test
```
```

- [ ] **Step 2: Commit**

```bash
git add healthflow/forensics/README.md
git commit -m "Forensics: README (vocabulary mapping, three surfaces, explicit does-NOT list)"
```

---

## Task 10: Pre-push verification + push + PR

**Files:** none (operations only).

- [ ] **Step 1: Run lint**

Run: `make lint 2>&1 | tail -3`
Expected: baseline E402 count (no new findings should be attributable to forensics).

- [ ] **Step 2: Run dead-code scan**

Run: `make dead-code 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 3: Final test run**

Run: `make test 2>&1 | tail -3`
Expected: `700 passed, 3 skipped`.

- [ ] **Step 4: Pre-push smoke (per durable rule)**

Run: `make smoke-external 2>&1 | tail -3`
Expected: `3 passed`.

- [ ] **Step 5: Inspect commit history**

Run: `git log --oneline main..HEAD`
Expected: 9 commits in order:
1. Forensics: package skeleton + ForensicsAccessLog model + schemas
2. Forensics: test fixtures (synthetic AgentInvocationLog / PhiAccessLog)
3. Forensics: replay_case + self-audit + cross-tenant isolation (3 tests)
4. Forensics: replay_member + replay_agent + 5 more tests
5. Forensics: integrity.check (gap detection + error clusters + 5 tests)
6. Forensics: redaction.redact (PHI patterns + 200-char truncation + 3 tests)
7. Forensics: POST /forensics/replay (admin-only) + 4 tests
8. Forensics: CLI with case/member/agent verbs + 2 tests
9. Forensics: README (vocabulary mapping, three surfaces, explicit does-NOT list)

- [ ] **Step 6: Push the branch**

Run: `git push -u origin forensics-replay-tool`
Expected: branch pushed.

- [ ] **Step 7: Open the PR**

Run:

```bash
gh pr create --title "Audit Replay & Forensics Tool (PR #2/2 of forensics tooling)" --body "$(cat <<'EOF'
## Summary

Read-only forensics tool — Python API + CLI + FastAPI endpoint — that reconstructs chronological agent-activity timelines from `agent_invocation_log` (shipped in PR #18) and joins to `phi_access_log` for PHI-access context.

- `replay_case(case_id)` / `replay_member(client_id, time_range)` / `replay_agent(agent, time_range)` Python API
- `python -m healthflow.forensics replay <verb>` CLI
- `POST /forensics/replay` admin-only HTTP endpoint
- New `ForensicsAccessLog` table — one row per query for self-audit (fail-loud)
- 22 tests (8 replay + 5 integrity + 3 redaction + 4 routes + 2 CLI)

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-05-24-forensics-replay-tool-design.md`
- Plan: `docs/superpowers/plans/2026-05-24-forensics-replay-tool.md`

## Honest deviations from the original spec
Documented in the spec; recap here:
- `phi_fields_accessed` → `phi_tables_touched` + `phi_row_count` (audit is row-level, not field-level)
- `Handoff` model dropped (no agent-to-agent audit events exist; `decision_chain` covers it)
- `tamper_evidence` always `"unknown"` (hash-chain is a separate follow-up)
- Vocabulary: spec's `member_id`/`tenant_id` maps to codebase's `client_id`/`broker_id`

## Compliance properties
- Read-only on foundation tables
- Tenant isolation enforced at the query layer (every replay function filters by `broker_id = tenant_id`)
- Cross-tenant queries return empty (not 404, not 403 — no info leak)
- PHI never in output — `member_id_hash` is SHA-256 prefix; free-text fields pass through `PHIRedactor`
- Self-audit row per query, fail-loud
- Reproducible (no clock-dependent logic in the query)

## Tests
- 22 new (no network, no LLM)
- Full suite: 700 passed, 3 skipped (was 678 baseline from PR #18)
- `make smoke-external` 3/3 ✓
EOF
)"
```

Expected: PR URL printed; CI begins.

---

## Notes for the implementer

- **Build order matters.** Schemas first → fixtures → replay_case (smallest scope, single function) → other replay functions → integrity → redaction → routes → CLI → README. Don't reorder.
- **`session_factory` injection.** Every replay function takes `session_factory` as a kwarg so tests inject the in-memory fixture. The CLI + route load the real `async_session_factory` from `healthflow.database.config`.
- **`_get_session_factory()` indirection** in `routes.py` and `cli.py` is the monkeypatch seam for tests. Don't inline `async_session_factory` directly — tests will break.
- **PHI join window** (`PHI_JOIN_WINDOW = timedelta(seconds=2)`) is a tunable constant in `replay.py`. Document it in the README if it ever changes.
- **`row_ids` JSON list filter** in `replay_member` is done in Python after a coarse SQL fetch (`broker_id` + time range). SQLAlchemy can't portably express "value IN JSON list" across SQLite + Postgres, so the Python filter is intentional.
- **Self-audit failure must be fail-loud.** If `_write_self_audit` raises, the entire query rolls back. Unaudited admin queries are a compliance hole; better to error than to silently lose the audit.
- **`make dead-code` ignores list** in the Makefile already covers SQLAlchemy + Pydantic framework-callback patterns. No new ignores should be needed.
- **The route accepts `body: dict`** and dispatches via Pydantic models per-mode rather than a discriminated-union type because FastAPI's `Annotated[Union[...], Field(discriminator="mode")]` adds complexity for marginal benefit on a three-mode endpoint. Document this choice inline.
