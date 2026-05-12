# Multi-Tenancy Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tenant-isolation infrastructure (request-scoped `ContextVar` + SQLAlchemy `do_orm_execute` event listener + raw-SQL guard) and wire it into the auth dependency, so authenticated requests carry an automatic `WHERE broker_id = current_broker_id` filter on tenant-scoped tables. **No behavior change in this PR** — existing manual `WHERE broker_id` filters in routers stay in place as belt-and-suspenders.

**Architecture:** New `healthflow/auth/tenant_context.py` exposes a `ContextVar[uuid.UUID | None]`, a `system_context()` contextmanager, and a `TenantContextMissing` exception. New `healthflow/database/tenant_filter.py` registers a `do_orm_execute` listener on the `healthflow.db` async session that auto-injects a `WHERE broker_id = :tenant` filter for ORM queries against a hardcoded set of tenant-scoped models (`Client`, `ActionHistory`, `Feedback`). A separate `before_execute` engine listener heuristically guards raw SQL. The FastAPI auth dependency (`get_current_broker`) sets the `ContextVar` on entry and resets it on teardown. Test fixtures in `tests/conftest.py` are updated so DB-direct tests run inside `system_context()` by default.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x async (sqlalchemy.ext.asyncio), pytest, contextvars (stdlib).

**Spec:** [docs/superpowers/specs/2026-05-12-multi-tenancy-design.md](../specs/2026-05-12-multi-tenancy-design.md)

**Out of scope for this plan (lands in Plan 2):** removing manual `WHERE broker_id` filters from routers, composite-write protection on `ActionHistory`, the full `tests/tenancy/` suite extension, the `feedback/` analytics audit (legitimate cross-broker reads), and the `healthflow-security` skill update.

---

## File Structure

After this plan:

```
healthflow/
  auth/
    tenant_context.py      (NEW — ContextVar, system_context, TenantContextMissing)
    dependencies.py        (MODIFIED — set/reset ContextVar in get_current_broker)
  database/
    tenant_filter.py       (NEW — registry + do_orm_execute + raw-SQL guard)
    config.py              (MODIFIED — register listeners on engine + session factory)
  tests/
    conftest.py            (MODIFIED — wrap DB-direct tests in system_context())
    tenancy/
      test_tenant_context.py     (NEW — ContextVar lifecycle, system_context, asyncio gather)
      test_tenant_filter.py      (NEW — hook unit tests against real session)
```

Each new module has one clear responsibility:
- `tenant_context.py` — request-scoped tenant identity. Knows nothing about SQLAlchemy.
- `tenant_filter.py` — SQLAlchemy event integration. Reads from `tenant_context` but doesn't expose it.
- The split keeps the ContextVar reusable (e.g. for an audit logger in sub-project #3) without dragging SQLAlchemy into every consumer.

---

## Task 1: Branch + capture baseline

**Files:** Read-only.

- [ ] **Step 1: Confirm clean main and create feature branch**

```bash
git status
git checkout main && git pull --ff-only
git checkout -b multi-tenancy/foundation
git branch --show-current
```

Expected: `multi-tenancy/foundation`. If `git pull` reports anything other than already-up-to-date or fast-forward, STOP and surface — main may have moved.

- [ ] **Step 2: Capture pre-implementation test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `462 tests collected in X.XXs` (from prior baseline; record actual). Every later step must match.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick
```

Expected: all 462 tests pass. If anything fails, STOP — don't add infrastructure on top of broken tests.

No commit for this task.

---

## Task 2: Add `tenant_context.py` (ContextVar + exception)

**Files:**
- Create: `healthflow/auth/tenant_context.py`
- Test: `healthflow/tests/tenancy/test_tenant_context.py`

- [ ] **Step 1: Write the failing tests for `current_broker_id` and `require_current_broker`**

Create `healthflow/tests/tenancy/test_tenant_context.py`:

```python
"""Unit tests for the request-scoped tenant context."""
import asyncio
import uuid

import pytest

from healthflow.auth.tenant_context import (
    TenantContextMissing,
    current_broker_id,
    require_current_broker,
)


def test_current_broker_id_default_is_none():
    assert current_broker_id.get() is None


def test_require_current_broker_raises_when_unset():
    # ContextVar default in the test scope is None.
    assert current_broker_id.get() is None
    with pytest.raises(TenantContextMissing):
        require_current_broker()


def test_require_current_broker_returns_set_value():
    broker_id = uuid.uuid4()
    token = current_broker_id.set(broker_id)
    try:
        assert require_current_broker() == broker_id
    finally:
        current_broker_id.reset(token)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_context.py -v
```

Expected: collection error or ImportError on `healthflow.auth.tenant_context` — module doesn't exist yet.

- [ ] **Step 3: Create `tenant_context.py` with minimal implementation**

Create `healthflow/auth/tenant_context.py`:

```python
"""Request-scoped tenant identity for HealthFlow.

A `ContextVar` holds the current broker's UUID for the life of an HTTP
request (set by the FastAPI auth dependency, reset on teardown). Code
that touches PHI tables uses `require_current_broker()` to read it;
attempting to read when unset raises `TenantContextMissing`.

This module knows nothing about SQLAlchemy. The actual filter
enforcement lives in `healthflow.database.tenant_filter`.
"""
import uuid
from contextvars import ContextVar


class TenantContextMissing(Exception):
    """Raised when tenant-scoped code runs without a current broker.

    Indicates a bug: either the auth dependency didn't set the context
    var, or background code touched a tenant-scoped table without
    entering `system_context()`.
    """


current_broker_id: ContextVar[uuid.UUID | None] = ContextVar(
    "current_broker_id", default=None
)


def require_current_broker() -> uuid.UUID:
    """Return the current broker's UUID, or raise TenantContextMissing."""
    value = current_broker_id.get()
    if value is None:
        raise TenantContextMissing(
            "No current broker in context. Authenticated routes must run "
            "under get_current_broker; system code must use system_context()."
        )
    return value
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_context.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Verify total count is now 462 + 3 = 465**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `465 tests collected in X.XXs`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/auth/tenant_context.py healthflow/tests/tenancy/test_tenant_context.py
git commit -m "Add tenant_context module: ContextVar + TenantContextMissing"
```

No `Co-Authored-By` trailer.

---

## Task 3: Add `system_context()` contextmanager

**Files:**
- Modify: `healthflow/auth/tenant_context.py`
- Modify: `healthflow/tests/tenancy/test_tenant_context.py`

- [ ] **Step 1: Write failing tests for `system_context`**

Append to `healthflow/tests/tenancy/test_tenant_context.py`:

```python
import logging

from healthflow.auth.tenant_context import system_context


def test_system_context_clears_value():
    broker_id = uuid.uuid4()
    token = current_broker_id.set(broker_id)
    try:
        with system_context():
            assert current_broker_id.get() is None
        # restored after exit
        assert current_broker_id.get() == broker_id
    finally:
        current_broker_id.reset(token)


def test_system_context_works_when_already_unset():
    assert current_broker_id.get() is None
    with system_context():
        assert current_broker_id.get() is None
    assert current_broker_id.get() is None


def test_system_context_logs_warning_on_entry_and_exit(caplog):
    with caplog.at_level(logging.WARNING, logger="healthflow.auth.tenant_context"):
        with system_context():
            pass
    messages = [r.getMessage() for r in caplog.records]
    assert any("system_context: enter" in m for m in messages)
    assert any("system_context: exit" in m for m in messages)


@pytest.mark.anyio
async def test_concurrent_requests_do_not_leak_context():
    """contextvars + asyncio: each task sees its own value, not the other's."""
    a = uuid.uuid4()
    b = uuid.uuid4()
    seen = {}

    async def task(label, value):
        token = current_broker_id.set(value)
        try:
            await asyncio.sleep(0.01)  # yield to the other task
            seen[label] = current_broker_id.get()
        finally:
            current_broker_id.reset(token)

    await asyncio.gather(task("a", a), task("b", b))

    assert seen["a"] == a
    assert seen["b"] == b
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_context.py -v
```

Expected: 3 prior tests pass; the 4 new tests fail with ImportError on `system_context`.

- [ ] **Step 3: Add `system_context` to `tenant_context.py`**

Append to `healthflow/auth/tenant_context.py`:

```python
import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)


@contextmanager
def system_context() -> Iterator[None]:
    """Temporarily clear the tenant context for legitimate cross-tenant work.

    Use only at audited call sites (seeders, migrations, system-owned
    analytics). Logs WARN on entry and exit to make any use visible in
    the logs.
    """
    token = current_broker_id.set(None)
    logger.warning("system_context: enter (caller bypassing tenant filter)")
    try:
        yield
    finally:
        current_broker_id.reset(token)
        logger.warning("system_context: exit")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_context.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Verify total count is now 462 + 7 = 469**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `469 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/auth/tenant_context.py healthflow/tests/tenancy/test_tenant_context.py
git commit -m "Add system_context() contextmanager with WARN logging"
```

---

## Task 4: Add `tenant_filter.py` (registry + do_orm_execute listener)

**Files:**
- Create: `healthflow/database/tenant_filter.py`
- Test: `healthflow/tests/tenancy/test_tenant_filter.py`

- [ ] **Step 1: Write failing tests for the filter**

Create `healthflow/tests/tenancy/test_tenant_filter.py`:

```python
"""Tests for the do_orm_execute tenant filter against a real in-memory DB."""
import logging
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import (
    TenantContextMissing,
    current_broker_id,
    system_context,
)
from healthflow.database.models import Base, Broker, Client, PromptVariant
from healthflow.database.tenant_filter import (
    TENANT_SCOPED_MODELS,
    install_tenant_filter,
)


@pytest_asyncio.fixture
async def session_with_filter():
    """In-memory engine + session, with the tenant filter installed."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    async with factory() as session:
        # Seed two brokers + one client per broker, inside system_context so
        # the inserts/selects during setup don't trip the filter.
        with system_context():
            broker_a = Broker(email="a@t.test", hashed_password=hash_password("x"), full_name="A")
            broker_b = Broker(email="b@t.test", hashed_password=hash_password("x"), full_name="B")
            session.add_all([broker_a, broker_b])
            await session.flush()
            client_a = Client(
                broker_id=broker_a.id, full_name="A's client", zip_code="10001",
                age=40, income_level="medium", doctors=[], prescriptions=[], procedures=[],
            )
            client_b = Client(
                broker_id=broker_b.id, full_name="B's client", zip_code="10002",
                age=50, income_level="high", doctors=[], prescriptions=[], procedures=[],
            )
            session.add_all([client_a, client_b])
            await session.commit()
        yield session, broker_a, broker_b, client_a, client_b
    await engine.dispose()


def test_registry_lists_phi_tables_only():
    names = {m.__tablename__ for m in TENANT_SCOPED_MODELS}
    assert names == {"clients", "action_history", "feedback"}


@pytest.mark.anyio
async def test_query_with_no_context_raises(session_with_filter):
    session, _, _, _, _ = session_with_filter
    # current_broker_id is unset here.
    with pytest.raises(TenantContextMissing):
        await session.execute(select(Client))


@pytest.mark.anyio
async def test_query_with_context_filters_to_that_broker(session_with_filter):
    session, broker_a, broker_b, client_a, client_b = session_with_filter
    token = current_broker_id.set(broker_a.id)
    try:
        result = await session.execute(select(Client))
        rows = result.scalars().all()
        assert [r.id for r in rows] == [client_a.id]
    finally:
        current_broker_id.reset(token)


@pytest.mark.anyio
async def test_query_inside_system_context_returns_all(session_with_filter):
    session, _, _, client_a, client_b = session_with_filter
    with system_context():
        result = await session.execute(select(Client))
        ids = sorted(r.id for r in result.scalars().all())
    assert ids == sorted([client_a.id, client_b.id])


@pytest.mark.anyio
async def test_non_tenant_scoped_query_unaffected(session_with_filter):
    session, _, _, _, _ = session_with_filter
    # Broker is NOT tenant-scoped — query must work without context.
    assert current_broker_id.get() is None
    result = await session.execute(select(Broker))
    rows = result.scalars().all()
    assert len(rows) == 2  # both brokers visible


@pytest.mark.anyio
async def test_filter_logs_at_debug(session_with_filter, caplog):
    session, broker_a, _, _, _ = session_with_filter
    token = current_broker_id.set(broker_a.id)
    try:
        with caplog.at_level(logging.DEBUG, logger="healthflow.database.tenant_filter"):
            await session.execute(select(Client))
        assert any("tenant_filter: scoped" in r.getMessage() for r in caplog.records)
    finally:
        current_broker_id.reset(token)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_filter.py -v
```

Expected: ImportError on `healthflow.database.tenant_filter`.

- [ ] **Step 3: Implement `tenant_filter.py`**

Create `healthflow/database/tenant_filter.py`:

```python
"""SQLAlchemy event listener that auto-filters tenant-scoped queries by broker_id.

Registered on the async session factory at app startup
(see `healthflow.database.config`). For each ORM-level execute that
targets a model in `TENANT_SCOPED_MODELS`:

  * If `current_broker_id.get()` is a UUID, append
    `WHERE broker_id = :tenant` to the statement.
  * If unset, raise `TenantContextMissing`.

Code that legitimately needs cross-tenant access wraps the operation
in `with system_context():` (which sets the var to None and bypasses
the raise — the listener treats explicit-None as "no filter, but
explicitly OK").

This listener fires for SELECT/UPDATE/DELETE statements (the ORM
`do_orm_execute` event). INSERTs go through a different path; they
don't get filtered, but they don't need to be — tenant-scoped
INSERTs always set `broker_id` from the auth session, and any
cross-tenant references (e.g. `ActionHistory.client_id`) are
protected by the filtered SELECT that loads the related row before
the INSERT.
"""
import logging
import uuid

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from healthflow.auth.tenant_context import (
    TenantContextMissing,
    current_broker_id,
    system_context,  # re-exported for convenience
)
from healthflow.database.models import ActionHistory, Client, Feedback

logger = logging.getLogger(__name__)


# Explicit registry — adding a future PHI model is a one-line change here.
TENANT_SCOPED_MODELS: frozenset[type] = frozenset({Client, ActionHistory, Feedback})


def _statement_targets_tenant_model(orm_execute_state) -> type | None:
    """If the statement targets a tenant-scoped model, return that model."""
    if not (orm_execute_state.is_select or orm_execute_state.is_update or orm_execute_state.is_delete):
        return None
    for model in TENANT_SCOPED_MODELS:
        # bind_arguments propagates the primary entity for ORM-level queries.
        # We use the simpler check: does the statement reference the table?
        if orm_execute_state.bind_mapper is not None and orm_execute_state.bind_mapper.class_ is model:
            return model
        # For multi-entity selects (e.g. select(Client.id, Client.full_name)),
        # bind_mapper is None but the column descriptions cover it.
        for desc in getattr(orm_execute_state.statement, "column_descriptions", []) or []:
            if desc.get("entity") is model:
                return model
    return None


def _on_do_orm_execute(orm_execute_state) -> None:
    """SQLAlchemy do_orm_execute hook: enforce tenant filter."""
    target = _statement_targets_tenant_model(orm_execute_state)
    if target is None:
        return  # not tenant-scoped; no filter

    broker_id = current_broker_id.get()
    if broker_id is None:
        # Distinguish "explicitly cleared via system_context" from "never set".
        # We can't tell from the ContextVar alone, so we rely on the convention:
        # callers that need cross-tenant access enter system_context (which sets
        # to None). Either way, the runtime semantics are the same: no filter.
        # To make accidental misses loud, we raise unless we detect the
        # system_context flag (set as a sibling ContextVar — see below).
        if not _in_system_context.get():
            raise TenantContextMissing(
                f"Tenant-scoped query against {target.__tablename__} "
                f"without a current broker. Wrap in system_context() if "
                f"this is intentional cross-tenant access."
            )
        return  # in system_context, no filter

    # Apply the filter.
    new_stmt = orm_execute_state.statement.where(target.broker_id == broker_id)
    orm_execute_state.statement = new_stmt
    logger.debug(
        "tenant_filter: scoped %s to broker=%s",
        target.__tablename__,
        str(broker_id)[:8],
    )


def install_tenant_filter(factory: async_sessionmaker) -> None:
    """Register the do_orm_execute listener on this session factory.

    Idempotent for distinct factories; calling twice on the same factory is a
    bug (would fire the listener twice per query). Engine setup at startup
    should call this exactly once.
    """
    event.listen(factory.sync_session_class, "do_orm_execute", _on_do_orm_execute)
```

The `_in_system_context` ContextVar referenced above lives in `healthflow/auth/tenant_context.py` (alongside `current_broker_id` and `system_context`). The filter needs to distinguish "deliberately cleared via `system_context()`" from "never set" — the flag does that. Update `system_context()` to also set the flag.

Replace the `system_context` block in `healthflow/auth/tenant_context.py` with the version below (this is the final form — supersedes Task 3's definition):

```python
import logging
from contextlib import contextmanager
from typing import Iterator
from contextvars import ContextVar

logger = logging.getLogger(__name__)

_in_system_context: ContextVar[bool] = ContextVar("_in_system_context", default=False)


@contextmanager
def system_context() -> Iterator[None]:
    """Temporarily clear the tenant context for legitimate cross-tenant work.

    Use only at audited call sites (seeders, migrations, system-owned
    analytics). Logs WARN on entry and exit to make any use visible in
    the logs.
    """
    broker_token = current_broker_id.set(None)
    flag_token = _in_system_context.set(True)
    logger.warning("system_context: enter (caller bypassing tenant filter)")
    try:
        yield
    finally:
        _in_system_context.reset(flag_token)
        current_broker_id.reset(broker_token)
        logger.warning("system_context: exit")
```

- [ ] **Step 4: Run filter tests**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_filter.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run tenant_context tests too** (the system_context body changed; make sure they still pass)

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_context.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Verify total count is now 462 + 7 + 6 = 475**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `475 tests collected`.

- [ ] **Step 7: Commit**

```bash
git add healthflow/auth/tenant_context.py healthflow/database/tenant_filter.py healthflow/tests/tenancy/test_tenant_filter.py
git commit -m "Add tenant_filter: do_orm_execute listener + TENANT_SCOPED_MODELS registry"
```

---

## Task 5: Add raw-SQL guard heuristic on the engine

**Files:**
- Modify: `healthflow/database/tenant_filter.py`
- Modify: `healthflow/tests/tenancy/test_tenant_filter.py`

- [ ] **Step 1: Write failing test for raw-SQL guard**

Append to `healthflow/tests/tenancy/test_tenant_filter.py`:

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from healthflow.database.tenant_filter import install_raw_sql_guard


@pytest.mark.anyio
async def test_raw_sql_against_tenant_table_without_filter_raises():
    """text('SELECT * FROM clients') with no broker_id clause should fail loud."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    async with engine.connect() as conn:
        with pytest.raises(TenantContextMissing):
            await conn.execute(text("SELECT * FROM clients"))
    await engine.dispose()


@pytest.mark.anyio
async def test_raw_sql_with_explicit_broker_id_filter_passes():
    """text('SELECT ... WHERE broker_id = ...') should be allowed."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    async with engine.connect() as conn:
        # Empty result is fine; we're testing that the guard doesn't raise.
        result = await conn.execute(
            text("SELECT * FROM clients WHERE broker_id = :b"),
            {"b": str(uuid.uuid4())},
        )
        assert result.fetchall() == []
    await engine.dispose()


@pytest.mark.anyio
async def test_raw_sql_against_non_tenant_table_unaffected():
    """SELECT against `brokers` table is fine without a broker_id clause."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    install_raw_sql_guard(engine)

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM brokers"))
        assert result.fetchall() == []
    await engine.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_filter.py -v -k raw_sql
```

Expected: ImportError on `install_raw_sql_guard`.

- [ ] **Step 3: Implement the heuristic guard**

Append to `healthflow/database/tenant_filter.py`:

```python
import re
from sqlalchemy.engine import Engine

# Tables protected by the heuristic guard. Names match the registered models'
# __tablename__.
_TENANT_SCOPED_TABLE_NAMES: frozenset[str] = frozenset(
    m.__tablename__ for m in TENANT_SCOPED_MODELS
)

# Match a tenant table name appearing after FROM, JOIN, UPDATE, or INTO,
# case-insensitive. Word boundaries prevent matching e.g. "myclients".
_TENANT_TABLE_REGEX = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO)\s+(?:" +
    "|".join(_TENANT_SCOPED_TABLE_NAMES) +
    r")\b",
    re.IGNORECASE,
)
_BROKER_ID_FILTER_REGEX = re.compile(r"\bbroker_id\s*=", re.IGNORECASE)


def _on_before_execute(conn, clauseelement, multiparams, params, execution_options):
    """Engine-level guard for raw SQL that bypasses the ORM filter.

    Heuristic: if the SQL text references a tenant-scoped table and has no
    `broker_id =` clause, raise. Not a complete defense (an attacker
    constructing raw SQL deliberately could bypass), but catches accidental
    `session.execute(text(...))` against PHI tables in application code.
    """
    sql = str(clauseelement)
    if not _TENANT_TABLE_REGEX.search(sql):
        return  # not touching a tenant-scoped table
    if _BROKER_ID_FILTER_REGEX.search(sql):
        return  # has a broker_id clause; trust the caller
    if _in_system_context.get():
        return  # legitimately bypassed
    raise TenantContextMissing(
        f"Raw SQL against a tenant-scoped table without broker_id filter. "
        f"Use the ORM (which auto-filters) or wrap in system_context(). "
        f"SQL: {sql[:200]}"
    )


def install_raw_sql_guard(engine) -> None:
    """Register before_execute listener on the engine for raw-SQL protection."""
    event.listen(engine.sync_engine, "before_execute", _on_before_execute)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_filter.py -v
```

Expected: 9 passed (6 prior + 3 new).

- [ ] **Step 5: Verify total count is now 462 + 7 + 9 = 478**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `478 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/tenant_filter.py healthflow/tests/tenancy/test_tenant_filter.py
git commit -m "Add raw-SQL guard heuristic via engine before_execute listener"
```

---

## Task 6: Update `tests/conftest.py` to support tenancy in tests

**Files:**
- Modify: `healthflow/tests/conftest.py`

The new filter raises on any tenant-scoped query without a broker context. Existing tests that use `db_session` directly to insert/query `Client`, `ActionHistory`, or `Feedback` must wrap their setup in `system_context()` or set `current_broker_id` explicitly. To minimize churn across ~30 existing tests, the simplest fix is to make the `db_session` fixture itself enter `system_context()` for tests that don't authenticate via the API. Tests that DO authenticate via the API (the `client` fixture) will get their context set by the auth dependency in step 7.

- [ ] **Step 1: Read the current conftest**

The current `tests/conftest.py` has fixtures: `anyio_backend`, `db_engine`, `db_session_factory`, `db_session`, `client`, `isolate_server_log`. None of them install the new tenant filter, and `db_session` doesn't enter `system_context`.

- [ ] **Step 2: Modify `db_engine` to install the raw-SQL guard, and modify `db_session_factory` to install the ORM filter**

Edit `healthflow/tests/conftest.py`. Replace the existing `db_engine` fixture (lines ~17–23) with:

```python
@pytest_asyncio.fixture
async def db_engine():
    from healthflow.database.tenant_filter import install_raw_sql_guard

    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    install_raw_sql_guard(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
```

Replace the existing `db_session_factory` fixture with:

```python
@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    from healthflow.database.tenant_filter import install_tenant_filter

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    return factory
```

- [ ] **Step 3: Modify `db_session` to enter `system_context` by default**

Replace the existing `db_session` fixture with:

```python
@pytest_asyncio.fixture
async def db_session(db_session_factory):
    """Direct DB session for tests that bypass the auth flow.

    Enters system_context() by default so test setup can insert/query
    tenant-scoped tables without raising. Tests that want to assert
    tenancy behavior should use the `client` fixture (which routes
    through real auth) or explicitly set `current_broker_id` after
    `system_context` exits.
    """
    from healthflow.auth.tenant_context import system_context

    async with db_session_factory() as session:
        with system_context():
            yield session
```

- [ ] **Step 4: Run the existing test suite to confirm nothing broke**

```bash
make test-quick
```

Expected: all 478 tests pass. The conftest changes should be transparent to existing tests (they were already inserting/reading PHI tables; now those operations run inside `system_context()`).

If any tests fail with `TenantContextMissing`, the failure is in a test that doesn't use `db_session` (uses its own session factory). Surface those — they need their own `system_context` wrapper.

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/conftest.py
git commit -m "Install tenant filter in test fixtures; wrap db_session in system_context"
```

---

## Task 7: Wire context into `get_current_broker` auth dependency

**Files:**
- Modify: `healthflow/auth/dependencies.py`

- [ ] **Step 1: Write a failing test for context propagation through the auth dependency**

Create `healthflow/tests/tenancy/test_auth_sets_context.py`:

```python
"""Verify that get_current_broker sets the tenant ContextVar for the request."""
import pytest

from healthflow.auth.tenant_context import current_broker_id


@pytest.mark.anyio
async def test_authenticated_request_sees_broker_in_context_var(client, db_session):
    """When a route runs under get_current_broker, current_broker_id is set."""
    # Register + log in a broker.
    res = await client.post(
        "/auth/register",
        json={
            "email": "ctx@healthflow.test",
            "password": "Ctx123!Pass",
            "full_name": "Context Test",
        },
    )
    assert res.status_code == 201, res.text

    res = await client.post(
        "/auth/login",
        json={"email": "ctx@healthflow.test", "password": "Ctx123!Pass"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Hit /clients (a tenant-scoped route). If the auth dependency didn't
    # set the ContextVar, the new tenant filter would raise on the SELECT.
    res = await client.get(
        "/clients", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json() == []  # no clients yet
```

- [ ] **Step 2: Run test — it will fail because auth dep doesn't set the var yet**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_auth_sets_context.py -v
```

Expected: 500 internal error or `TenantContextMissing` — the SELECT in `list_clients` runs without a context.

(Note: until step 3 lands, the existing manual `WHERE broker_id == broker.id` filter in `client_router.py` doesn't help — the new tenant filter raises BEFORE the WHERE clause matters, because the ORM execute event fires before the user's WHERE clauses are inspected.)

- [ ] **Step 3: Modify `get_current_broker` to set/reset the ContextVar**

Edit `healthflow/auth/dependencies.py`. Change the function from a plain `async def` to a yield-style FastAPI dependency so we can reset the var on teardown:

```python
import uuid
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import decode_token
from healthflow.auth.tenant_context import current_broker_id
from healthflow.database.config import get_db
from healthflow.database.models import Broker

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)


async def get_current_broker(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[Broker, None]:
    """Extract and validate the current broker from a JWT access token.

    Sets `current_broker_id` for the duration of the request so that
    SQLAlchemy queries against tenant-scoped tables auto-filter to this
    broker. Resets on teardown so per-request isolation is clean under
    asyncio concurrency.

    Raises:
        HTTPException 401: If the token is invalid, expired, or the broker
            is not found or inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except (ValueError, Exception):
        raise credentials_exception

    broker_id_str: str | None = payload.get("sub")
    if broker_id_str is None:
        raise credentials_exception

    token_type = payload.get("type")
    if token_type != "access":
        raise credentials_exception

    try:
        broker_id = uuid.UUID(broker_id_str)
    except ValueError:
        raise credentials_exception

    # Set the ContextVar BEFORE the broker SELECT so the SELECT itself runs
    # under the right context (Broker is not tenant-scoped, so this isn't
    # strictly required for correctness — but it keeps the order intuitive).
    context_token = current_broker_id.set(broker_id)
    try:
        result = await db.execute(select(Broker).where(Broker.id == broker_id))
        broker = result.scalar_one_or_none()

        if broker is None or not broker.is_active:
            raise credentials_exception

        yield broker
    finally:
        current_broker_id.reset(context_token)
```

Note: changing the return type from a plain `Broker` to a yield-style dependency means FastAPI now treats it as a generator dependency. Routes that depend on it via `Depends(get_current_broker)` continue to work — FastAPI handles both styles transparently. The type annotation `AsyncGenerator[Broker, None]` is for clarity; FastAPI inspects the function body.

- [ ] **Step 4: Run the new test**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_auth_sets_context.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Run the full suite — every authenticated test now flows through the new context-setting dep**

```bash
make test-quick
```

Expected: all 479 tests pass (478 + the 1 new test). If any test fails:
- `TenantContextMissing` from a route or test → that route or test bypasses `get_current_broker`. Surface and either add the dependency or wrap the call in `system_context`.
- A different failure → unrelated, surface separately.

- [ ] **Step 6: Commit**

```bash
git add healthflow/auth/dependencies.py healthflow/tests/tenancy/test_auth_sets_context.py
git commit -m "Wire current_broker_id ContextVar into get_current_broker dependency"
```

---

## Task 8: Register listeners on the production engine + session factory

**Files:**
- Modify: `healthflow/database/config.py`

The test fixtures install the listeners on the test engine/factory (Task 6). Production needs the same wiring at module-import time so the running app benefits.

- [ ] **Step 1: Add a listener-installation call after the engine + factory are created**

Edit `healthflow/database/config.py`. Add at the end of the module-level setup (after the `async_session_factory` line):

```python
# Install the tenant isolation listeners on the production engine and session
# factory. Done at import time so any code path that uses the default factory
# is automatically protected.
from healthflow.database.tenant_filter import install_raw_sql_guard, install_tenant_filter

install_raw_sql_guard(engine)
install_tenant_filter(async_session_factory)
```

The import sits at the bottom of `config.py` because the install calls reference `engine` and `async_session_factory`, which must already be defined at module-level above. (No real circular import to avoid — `tenant_filter.py` only imports from `models.py` and `tenant_context.py`, neither of which touches `config.py`.)

- [ ] **Step 2: Run the full suite to confirm production wiring doesn't break anything**

```bash
make test-quick
```

Expected: all 479 tests pass. Tests use the test fixture's engine/factory; the production wiring is exercised by the import but does not affect test sessions.

- [ ] **Step 3: Smoke test: confirm the listeners are actually installed on the production factory**

Add a small test to `healthflow/tests/tenancy/test_tenant_filter.py`:

```python
@pytest.mark.anyio
async def test_production_factory_has_listeners_installed():
    """Importing the production config wires the listeners onto the factory.

    Smoke test: the import-time side effects in healthflow.database.config
    should leave the production async_session_factory ready to enforce.
    """
    from healthflow.database.config import async_session_factory, engine
    from sqlalchemy import event
    from healthflow.database.tenant_filter import _on_before_execute, _on_do_orm_execute

    # event.contains returns True if our specific listener function is
    # registered for that event on that target.
    assert event.contains(async_session_factory.sync_session_class, "do_orm_execute", _on_do_orm_execute), \
        "do_orm_execute listener missing from production session factory"
    assert event.contains(engine.sync_engine, "before_execute", _on_before_execute), \
        "before_execute guard missing from production engine"
```

- [ ] **Step 4: Run the smoke test**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_filter.py::test_production_factory_has_listeners_installed -v
```

Expected: 1 passed.

- [ ] **Step 5: Verify total count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `480 tests collected` (462 baseline + 7 context + 10 filter + 1 auth-context + 0 conftest = 480).

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/config.py healthflow/tests/tenancy/test_tenant_filter.py
git commit -m "Install tenant filter and raw-SQL guard on production engine + factory"
```

---

## Task 9: Final verification

**Files:** None — verification only.

- [ ] **Step 1: Confirm full suite is green at the new baseline**

```bash
make test-quick
```

Expected: `480 passed` in ~30s.

- [ ] **Step 2: Confirm `make check` runs (lint + tests + frontend build)**

```bash
make check 2>&1 | tail -20
```

Expected: tests green; lint may report the same pre-existing E402 errors in `healthflow/main.py` and `test_refresh_downloaders.py` from before (those predate this PR); frontend build green.

- [ ] **Step 3: Hand-verify the new modules exist and are wired**

```bash
ls healthflow/auth/tenant_context.py healthflow/database/tenant_filter.py
.venv/bin/python -c "
from sqlalchemy import event
from healthflow.database.config import async_session_factory, engine
from healthflow.database.tenant_filter import _on_do_orm_execute, _on_before_execute
assert event.contains(async_session_factory.sync_session_class, 'do_orm_execute', _on_do_orm_execute), 'ORM listener missing'
assert event.contains(engine.sync_engine, 'before_execute', _on_before_execute), 'raw-SQL guard missing'
print('listeners installed: OK')
"
```

Expected: `listeners installed: OK`.

- [ ] **Step 4: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: 7 commits (one per task with code changes; Tasks 1 and 9 don't commit):
- `Install tenant filter and raw-SQL guard on production engine + factory`
- `Wire current_broker_id ContextVar into get_current_broker dependency`
- `Install tenant filter in test fixtures; wrap db_session in system_context`
- `Add raw-SQL guard heuristic via engine before_execute listener`
- `Add tenant_filter: do_orm_execute listener + TENANT_SCOPED_MODELS registry`
- `Add system_context() contextmanager with WARN logging`
- `Add tenant_context module: ContextVar + TenantContextMissing`

(Order in `git log` is reverse chrono; the list above is newest-to-oldest.)

- [ ] **Step 5: Push the branch**

```bash
git push -u origin multi-tenancy/foundation
```

- [ ] **Step 6: Open a PR**

```bash
gh pr create --title "Multi-tenancy foundation: ContextVar + SQLAlchemy filter hook" --body "$(cat <<'EOF'
## Summary

Builds the tenant-isolation infrastructure for HealthFlow. **No behavior change in this PR** — existing manual `WHERE broker_id` filters in routers stay in place as belt-and-suspenders. The next PR (Plan 2) removes those manual filters and makes the new hook load-bearing.

- `healthflow/auth/tenant_context.py`: request-scoped `ContextVar[uuid.UUID]`, `system_context()` contextmanager, `TenantContextMissing` exception.
- `healthflow/database/tenant_filter.py`: `do_orm_execute` listener that auto-injects `WHERE broker_id = :tenant` for `Client`/`ActionHistory`/`Feedback`; `before_execute` engine listener heuristically guards raw SQL.
- `healthflow/auth/dependencies.py`: `get_current_broker` now sets/resets the ContextVar via a yield-style FastAPI dependency.
- `healthflow/database/config.py`: listeners installed on the production engine and session factory at module import.
- `healthflow/tests/conftest.py`: test fixtures install the same listeners and wrap `db_session` in `system_context()` so existing tests keep passing.

Spec: [docs/superpowers/specs/2026-05-12-multi-tenancy-design.md](./docs/superpowers/specs/2026-05-12-multi-tenancy-design.md)
Plan: [docs/superpowers/plans/2026-05-12-multi-tenancy-foundation.md](./docs/superpowers/plans/2026-05-12-multi-tenancy-foundation.md)

## Test Plan

- [x] 18 new unit tests (tenant_context: 7, tenant_filter: 10, auth-sets-context: 1) all green
- [x] Full backend suite: 480/480 (prior baseline 462 + 18 new)
- [x] Authenticated route smoke test confirms ContextVar is set during a real `/clients` request
- [x] Concurrent asyncio.gather test confirms ContextVar isolation between concurrent requests
- [ ] CI green on this PR

## Out of scope

- Removing the manual `WHERE broker_id` filters from routers (Plan 2)
- Composite-write protection on `ActionHistory.client_id` (Plan 2)
- Auditing `feedback/collector.py`, `feedback/prompt_updater.py`, `feedback/reward_model.py` for legitimate cross-broker analytics (Plan 2)
- Updating the `healthflow-security` skill to reference the new enforcement (Plan 2)
- Pre-existing E402 lint errors in `healthflow/main.py` (separate PR)
EOF
)"
```

No new commit for this task — verification only.
