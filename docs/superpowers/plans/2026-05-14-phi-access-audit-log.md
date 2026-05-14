# PHI Access Audit Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable, queryable `phi_access_log` table that records one append-only row per PHI query — who (broker), what (table + operation), which patients (result row IDs), how/why (endpoint), and when — populated by SQLAlchemy event listeners so coverage is enforced by infrastructure, not developer discipline.

**Architecture:** A `PhiAccessLog` model in `models.py`. Two listeners in a new `phi_audit.py`: a `do_orm_execute` listener for SELECT/UPDATE/DELETE (it uses `invoke_statement()` + `Result.freeze()` to observe result row IDs and still return them), and an `after_flush` listener for INSERTs (which `do_orm_execute` never sees). A new `current_endpoint` ContextVar carries the request path down to the listeners, set by a small middleware for HTTP requests and by `system_context()` for background work. Listeners are installed at startup *after* `install_tenant_filter` so the audit listener observes the already-tenant-scoped statement.

**Tech Stack:** Python 3.14, SQLAlchemy 2.x async (`do_orm_execute` + `after_flush` events, `Result.freeze()`), FastAPI/Starlette middleware, `contextvars` (stdlib), pytest.

**Spec:** [docs/superpowers/specs/2026-05-14-phi-access-audit-log-design.md](../specs/2026-05-14-phi-access-audit-log-design.md)

---

## Background: the two SQLAlchemy mechanisms this plan leans on

**`Result.freeze()`** — when a `do_orm_execute` listener wants to *see* the rows a query returns AND still hand a usable result back to the caller, it can't just call `.all()` (that consumes the result). The idiom is: `result = orm_execute_state.invoke_statement()` runs the (already tenant-scoped) statement; `frozen = result.freeze()` captures it as a re-runnable `FrozenResult`; `frozen()` produces a fresh `Result` each time it's called. So the listener inspects `frozen().all()` for row IDs, then `return frozen()` to give the caller an untouched result. Returning a non-None value from `do_orm_execute` tells SQLAlchemy "I handled execution — don't run it again."

**Listener ordering** — `do_orm_execute` listeners fire in registration order, and the first to return a non-None value halts the rest. The tenant filter modifies `orm_execute_state.statement` and returns `None` (lets execution proceed). The audit listener must run *after* it, call `invoke_statement()` (which runs the tenant-scoped statement), and return a result. So `install_tenant_filter` must be called before `install_phi_audit` — in both `config.py` and the test conftest.

**`invoke_statement()` does not re-trigger `do_orm_execute`** — when the audit listener calls `orm_execute_state.invoke_statement()`, that runs the statement *without* firing the `do_orm_execute` hooks again. So the audit listener invoking the statement does not recurse into itself or re-run the tenant filter. (This is separate from the `phi_access_log` self-exclusion, which guards the *write* side — the listeners never classify `phi_access_log` as an audited table.)

---

## File Structure

```
healthflow/
  database/
    models.py            (MODIFIED — add PhiAccessLog model)
    phi_audit.py          (NEW — both listeners + install_phi_audit + the audit-write helper)
    config.py            (MODIFIED — call install_phi_audit after install_tenant_filter)
  auth/
    tenant_context.py    (MODIFIED — add current_endpoint ContextVar; system_context sets it)
  api/
    middleware.py        (MODIFIED — add EndpointContextMiddleware)
  main.py                (MODIFIED — register EndpointContextMiddleware)
  tests/
    database/
      test_phi_audit.py  (NEW — model, listeners, self-exclusion, coexistence)
    conftest.py          (MODIFIED — install_phi_audit on the test factory, after install_tenant_filter)
scripts/
  audit_query.py         (NEW — CLI to read the log back)
.claude/skills/
  healthflow-security/
    SKILL.md             (MODIFIED — document the audit-log enforcement model)
```

---

## Task 1: Branch + capture baseline

**Files:** Read-only.

- [ ] **Step 1: Confirm clean main and create feature branch**

```bash
git status
git checkout main && git pull --ff-only
git checkout -b phi-audit-log/access-trail
git branch --show-current
```

Expected: `phi-audit-log/access-trail`. If `git pull` reports anything other than already-up-to-date or fast-forward, STOP and surface.

- [ ] **Step 2: Capture pre-implementation test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `504 tests collected in X.XXs`. Record the actual number.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: all 504 tests pass. There is a known-flaky `test_tampered_token_raises`; if exactly that one fails on the first run, re-run once before declaring failure.

No commit for this task.

---

## Task 2: Add the `PhiAccessLog` model

**Files:**
- Modify: `healthflow/database/models.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

- [ ] **Step 1: Write the failing test**

Create `healthflow/tests/database/test_phi_audit.py`:

```python
"""Tests for the PHI access audit log — model, listeners, self-exclusion."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.models import Base, PhiAccessLog


@pytest_asyncio.fixture
async def raw_engine():
    """In-memory engine + tables, NO listeners installed (for model-only tests)."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.anyio
async def test_phi_access_log_table_exists_with_expected_columns(raw_engine):
    async with raw_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("phi_access_log")}
        )
    assert columns == {
        "id", "broker_id", "table_name", "operation",
        "row_ids", "row_count", "endpoint", "created_at",
    }


@pytest.mark.anyio
async def test_phi_access_log_row_roundtrips(raw_engine):
    factory = async_sessionmaker(raw_engine, class_=AsyncSession, expire_on_commit=False)
    broker_id = uuid.uuid4()
    client_id = uuid.uuid4()
    async with factory() as session:
        entry = PhiAccessLog(
            broker_id=broker_id,
            table_name="clients",
            operation="read",
            row_ids=[str(client_id)],
            row_count=1,
            endpoint="GET /clients",
        )
        session.add(entry)
        await session.commit()

    async with factory() as session:
        result = await session.execute(select(PhiAccessLog))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].broker_id == broker_id
    assert rows[0].table_name == "clients"
    assert rows[0].operation == "read"
    assert rows[0].row_ids == [str(client_id)]
    assert rows[0].row_count == 1
    assert rows[0].endpoint == "GET /clients"
    assert rows[0].created_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v
```

Expected: ImportError — `PhiAccessLog` does not exist in `healthflow.database.models`.

- [ ] **Step 3: Add the `PhiAccessLog` model**

Edit `healthflow/database/models.py`. The file already imports `Boolean, DateTime, ForeignKey, Integer, String` from `sqlalchemy` and `JSON` from `sqlalchemy.types`, and defines `GUID`, `_utcnow`, and `Base`. Add this model at the end of the file (after `PromptVariant`):

```python
class PhiAccessLog(Base):
    """Append-only audit trail: one row per PHI query.

    System table — NOT tenant-scoped (it records everyone's access) and
    NOT watched by the audit listeners themselves (writing an entry is a
    DB write; watching this table would recurse forever). See
    healthflow/database/phi_audit.py.
    """
    __tablename__ = "phi_access_log"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), index=True, nullable=True
    )
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    row_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
```

Note: `broker_id` is a plain indexed `GUID`, NOT a `ForeignKey` — the spec is explicit that this column means "who acted," not "who owns the row," and it's nullable for system operations. No `relationship()` either.

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Verify total count is now 504 + 2 = 506**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `506 tests collected`.

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/models.py healthflow/tests/database/test_phi_audit.py
git commit -m "Add PhiAccessLog model for the PHI access audit trail"
```

No `Co-Authored-By` trailer.

---

## Task 3: `current_endpoint` ContextVar + middleware

**Files:**
- Modify: `healthflow/auth/tenant_context.py`
- Modify: `healthflow/api/middleware.py`
- Modify: `healthflow/main.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/database/test_phi_audit.py`:

```python
from healthflow.auth.tenant_context import current_endpoint, system_context


def test_current_endpoint_default_is_none():
    assert current_endpoint.get() is None


def test_system_context_sets_endpoint_to_system_reason():
    assert current_endpoint.get() is None
    with system_context("RLHF reward scoring"):
        assert current_endpoint.get() == "system:RLHF reward scoring"
    # restored on exit
    assert current_endpoint.get() is None


def test_system_context_restores_prior_endpoint():
    token = current_endpoint.set("GET /clients")
    try:
        with system_context("nested system work"):
            assert current_endpoint.get() == "system:nested system work"
        assert current_endpoint.get() == "GET /clients"
    finally:
        current_endpoint.reset(token)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k endpoint
```

Expected: ImportError — `current_endpoint` does not exist in `healthflow.auth.tenant_context`.

- [ ] **Step 3: Add `current_endpoint` and have `system_context` set it**

Edit `healthflow/auth/tenant_context.py`. After the `_in_system_context` ContextVar definition (around line 45), add:

```python
current_endpoint: ContextVar[str | None] = ContextVar("current_endpoint", default=None)
```

Then modify `system_context` to also set `current_endpoint` for its duration. Replace the existing `system_context` function body with:

```python
@contextmanager
def system_context(reason: str) -> Iterator[None]:
    """Temporarily clear the tenant context for legitimate cross-tenant work.

    Use only at audited call sites. The required `reason` argument forces
    each caller to justify the bypass, makes the WARN log entries
    self-explanatory, and is recorded as the `endpoint` on any PHI access
    audit entry written during the block (`system:<reason>`).

    Args:
        reason: Human-readable justification, e.g. "RLHF prompt update".
    """
    broker_token = current_broker_id.set(None)
    flag_token = _in_system_context.set(True)
    endpoint_token = current_endpoint.set(f"system:{reason}")
    logger.warning("system_context: enter — %s", reason)
    try:
        yield
    finally:
        current_endpoint.reset(endpoint_token)
        _in_system_context.reset(flag_token)
        current_broker_id.reset(broker_token)
        logger.warning("system_context: exit — %s", reason)
```

- [ ] **Step 4: Add `EndpointContextMiddleware` to `middleware.py`**

Edit `healthflow/api/middleware.py`. Add the import at the top, next to the existing imports:

```python
from healthflow.auth.tenant_context import current_endpoint
```

Add this middleware class at the end of the file (after `_replay_iterator`):

```python
class EndpointContextMiddleware(BaseHTTPMiddleware):
    """Set `current_endpoint` for the duration of each HTTP request.

    The PHI access audit listener (healthflow/database/phi_audit.py) reads
    this ContextVar to record WHICH request triggered a PHI query. Background
    work has no request — it runs inside `system_context(reason=...)`, which
    sets `current_endpoint` to `system:<reason>` instead.
    """

    async def dispatch(self, request: Request, call_next):
        token = current_endpoint.set(f"{request.method} {request.url.path}")
        try:
            return await call_next(request)
        finally:
            current_endpoint.reset(token)
```

- [ ] **Step 5: Register the middleware in `main.py`**

Edit `healthflow/main.py`. It currently imports `HTTPLoggingMiddleware` from `healthflow.api.middleware` and calls `app.add_middleware(HTTPLoggingMiddleware)`. Change the import to also bring in the new middleware:

```python
from healthflow.api.middleware import EndpointContextMiddleware, HTTPLoggingMiddleware
```

And add the registration. Starlette runs middleware in reverse registration order (last added = outermost). Add `EndpointContextMiddleware` immediately after the existing `app.add_middleware(HTTPLoggingMiddleware)` line:

```python
app.add_middleware(HTTPLoggingMiddleware)
app.add_middleware(EndpointContextMiddleware)
```

Either order works for correctness (the ContextVar just needs to be set before any route runs), but adding it after means it's the outermost wrapper — `current_endpoint` is set before `HTTPLoggingMiddleware` even starts timing.

- [ ] **Step 6: Run the new tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v
make test-quick 2>&1 | tail -3
```

Expected: the 3 new `current_endpoint` tests pass (5 total in `test_phi_audit.py` now); full suite at 509 (506 + 3).

If an existing `system_context` test in `healthflow/tests/tenancy/test_tenant_context.py` breaks because the function body changed, it should not — the change only *adds* a ContextVar set/reset, the existing behavior (broker cleared, flag set, WARN logged) is unchanged. If one does break, surface it.

- [ ] **Step 7: Commit**

```bash
git add healthflow/auth/tenant_context.py healthflow/api/middleware.py healthflow/main.py healthflow/tests/database/test_phi_audit.py
git commit -m "Add current_endpoint ContextVar + EndpointContextMiddleware"
```

---

## Task 4: `phi_audit.py` — the read listener (SELECT)

**Files:**
- Create: `healthflow/database/phi_audit.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

This task builds the `do_orm_execute` listener's SELECT path, the audit-write helper, `install_phi_audit`, and the self-exclusion guard. UPDATE/DELETE handling is added in Task 5; INSERT in Task 6.

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/database/test_phi_audit.py`:

```python
from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import current_broker_id
from healthflow.database.models import Broker, Client
from healthflow.database.phi_audit import install_phi_audit
from healthflow.database.tenant_filter import install_tenant_filter


@pytest_asyncio.fixture
async def audited_session():
    """In-memory engine + session with BOTH the tenant filter and the audit
    listeners installed, in the required order (tenant filter first)."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)   # MUST be installed before the audit listener
    install_phi_audit(factory)
    async with factory() as session:
        with system_context("test setup"):
            broker = Broker(email="ra@t.test", hashed_password=hash_password("x"), full_name="RA")
            session.add(broker)
            await session.flush()
            c1 = Client(
                broker_id=broker.id, full_name="C One", zip_code="10001",
                age=40, income_level="medium", doctors=[], prescriptions=[], procedures=[],
            )
            c2 = Client(
                broker_id=broker.id, full_name="C Two", zip_code="10002",
                age=50, income_level="high", doctors=[], prescriptions=[], procedures=[],
            )
            session.add_all([c1, c2])
            await session.commit()
        yield session, broker, c1, c2
    await engine.dispose()


@pytest.mark.anyio
async def test_read_listener_logs_single_row_select(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients/{id}")
    try:
        result = await session.execute(select(Client).where(Client.id == c1.id))
        rows = result.scalars().all()
        assert len(rows) == 1  # result still usable after the listener observed it
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert len(log) == 1
    assert log[0].broker_id == broker.id
    assert log[0].table_name == "clients"
    assert log[0].operation == "read"
    assert log[0].row_ids == [str(c1.id)]
    assert log[0].row_count == 1
    assert log[0].endpoint == "GET /clients/{id}"


@pytest.mark.anyio
async def test_read_listener_logs_all_ids_for_a_list_query(audited_session):
    session, broker, c1, c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients")
    try:
        result = await session.execute(select(Client))
        rows = result.scalars().all()
        assert len(rows) == 2
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert len(log) == 1
    assert log[0].operation == "read"
    assert log[0].row_count == 2
    assert set(log[0].row_ids) == {str(c1.id), str(c2.id)}


@pytest.mark.anyio
async def test_read_listener_uses_system_endpoint_under_system_context(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("nightly recompute"):
        await session.execute(select(Client))
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    # one entry for the Client read; the PhiAccessLog read itself is self-excluded
    client_entries = [e for e in log if e.table_name == "clients"]
    assert len(client_entries) == 1
    assert client_entries[0].broker_id is None
    assert client_entries[0].endpoint == "system:nightly recompute"


@pytest.mark.anyio
async def test_read_listener_ignores_non_phi_tables(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("verify"):
        # Broker is not a PHI table — querying it must not create an audit entry.
        await session.execute(select(Broker))
        log = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert log == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "read_listener or ignores_non_phi"
```

Expected: ImportError — `healthflow.database.phi_audit` does not exist.

- [ ] **Step 3: Create `phi_audit.py`**

Create `healthflow/database/phi_audit.py`:

```python
"""SQLAlchemy event listeners that record every PHI query to phi_access_log.

Two listeners, registered on the session factory at startup AFTER
install_tenant_filter (the audit listener invokes the tenant-scoped
statement and must see it already scoped):

  * do_orm_execute  — SELECT / UPDATE / DELETE. Observes results via
    Result.freeze() so it can capture row IDs and still return a usable
    result to the caller.
  * after_flush     — INSERT. do_orm_execute never fires for unit-of-work
    flushes, so freshly-inserted PHI rows are caught here.

phi_access_log itself is excluded from both listeners — writing an audit
entry is a DB write, and watching the audit table would recurse forever.
phi_access_log is also NOT in TENANT_SCOPED_MODELS — it is a system table.

Identity comes from two request-scoped ContextVars:
  * current_broker_id — who (None for system operations)
  * current_endpoint  — the request path, or system:<reason> for background work
"""
import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.tenant_context import current_broker_id, current_endpoint
from healthflow.database.models import ActionHistory, Client, Feedback, PhiAccessLog

logger = logging.getLogger(__name__)

# The PHI tables whose access is audited. Mirrors TENANT_SCOPED_MODELS, but
# kept as its own list so the two concerns stay decoupled — a future table
# could be tenant-scoped without being PHI, or vice versa.
_AUDITED_MODELS: frozenset[type] = frozenset({Client, ActionHistory, Feedback})
_AUDITED_TABLE_NAMES: dict[type, str] = {m: m.__tablename__ for m in _AUDITED_MODELS}


def _audited_model_for_statement(orm_execute_state) -> type | None:
    """If the statement targets an audited PHI model, return it. Else None.

    PhiAccessLog is never audited (it is not in _AUDITED_MODELS), so reads of
    the audit table itself produce no entry — that is the recursion guard for
    the read path.
    """
    if not (orm_execute_state.is_select or orm_execute_state.is_update or orm_execute_state.is_delete):
        return None
    for model in _AUDITED_MODELS:
        if orm_execute_state.bind_mapper is not None and orm_execute_state.bind_mapper.class_ is model:
            return model
        for desc in getattr(orm_execute_state.statement, "column_descriptions", []) or []:
            if desc.get("entity") is model:
                return model
    return None


def _write_audit_entry(
    session, *, table_name: str, operation: str, row_ids: list[str]
) -> None:
    """Append one row to phi_access_log on the same session/transaction.

    Fails loud: if this raises, the caller's operation fails too — a broken
    audit listener must not silently lose coverage.
    """
    entry = PhiAccessLog(
        broker_id=current_broker_id.get(),
        table_name=table_name,
        operation=operation,
        row_ids=row_ids,
        row_count=len(row_ids),
        endpoint=current_endpoint.get() or "unknown",
    )
    session.add(entry)


def _extract_ids_from_orm_rows(rows: list) -> list[str]:
    """Pull `.id` off each ORM object a SELECT returned, as strings."""
    ids = []
    for row in rows:
        # scalars() yields the entity directly; a multi-entity row is a tuple.
        obj = row
        if isinstance(row, tuple):
            obj = next((x for x in row if hasattr(x, "id")), None)
        if obj is not None and hasattr(obj, "id"):
            ids.append(str(obj.id))
    return ids


def _on_do_orm_execute_audit(orm_execute_state):
    """do_orm_execute listener: audit SELECT (this task). UPDATE/DELETE added in Task 5."""
    model = _audited_model_for_statement(orm_execute_state)
    if model is None:
        return None  # not an audited table — let execution proceed normally

    if orm_execute_state.is_select:
        # Run the (already tenant-scoped) statement, freeze the result so we
        # can both inspect it and return a fresh copy to the caller.
        result = orm_execute_state.invoke_statement()
        frozen = result.freeze()
        rows = list(frozen().scalars().all())
        row_ids = _extract_ids_from_orm_rows(rows)
        _write_audit_entry(
            orm_execute_state.session,
            table_name=_AUDITED_TABLE_NAMES[model],
            operation="read",
            row_ids=row_ids,
        )
        return frozen()

    return None  # UPDATE/DELETE handled in Task 5


def install_phi_audit(factory: async_sessionmaker) -> None:
    """Register the PHI audit listeners on this session factory.

    Idempotent. MUST be called AFTER install_tenant_filter — the audit
    listener invokes the statement and needs to see it already tenant-scoped.
    """
    target = factory.class_.sync_session_class
    if not event.contains(target, "do_orm_execute", _on_do_orm_execute_audit):
        event.listen(target, "do_orm_execute", _on_do_orm_execute_audit)
```

Note on `frozen().scalars().all()`: for a `select(Client)` the frozen result yields ORM `Client` objects via `.scalars()`. For a column select like `select(Client.id)` there are no ORM objects — `_extract_ids_from_orm_rows` simply returns `[]` for those (the `hasattr(obj, "id")` check fails on a raw scalar). That is an accepted limitation: HealthFlow's routes select whole entities, not bare columns, on the PHI tables. If a column-only PHI select is ever added, the entry still records the table/operation/endpoint, just with empty `row_ids` — documented, not a silent failure.

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "read_listener or ignores_non_phi"
```

Expected: 4 passed.

- [ ] **Step 5: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 513 passed (509 + 4 new).

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/phi_audit.py healthflow/tests/database/test_phi_audit.py
git commit -m "phi_audit: do_orm_execute listener for SELECT — captures result row IDs"
```

---

## Task 5: `phi_audit.py` — UPDATE and DELETE in the read listener

**Files:**
- Modify: `healthflow/database/phi_audit.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

UPDATE/DELETE go through `do_orm_execute` too, but `invoke_statement()` on them returns a `CursorResult` with no rows to inspect — there is no result set, only a `rowcount`. HealthFlow's UPDATE/DELETE on PHI tables are id-based (`WHERE id = :x` — see `client_router.py`). So the affected ID is extracted from the statement's WHERE-clause bind parameters.

- [ ] **Step 1: Write the failing tests**

Append to `healthflow/tests/database/test_phi_audit.py`:

```python
from sqlalchemy import delete as sa_delete, update as sa_update


@pytest.mark.anyio
async def test_delete_listener_logs_affected_id(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("DELETE /clients/{id}")
    try:
        await session.execute(sa_delete(Client).where(Client.id == c1.id))
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.operation == "delete")
        )).scalars().all()
    assert len(log) == 1
    assert log[0].table_name == "clients"
    assert log[0].row_ids == [str(c1.id)]
    assert log[0].row_count == 1
    assert log[0].endpoint == "DELETE /clients/{id}"


@pytest.mark.anyio
async def test_update_listener_logs_affected_id(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("PUT /clients/{id}")
    try:
        await session.execute(
            sa_update(Client).where(Client.id == c1.id).values(age=99)
        )
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.operation == "update")
        )).scalars().all()
    assert len(log) == 1
    assert log[0].table_name == "clients"
    assert log[0].row_ids == [str(c1.id)]
    assert log[0].operation == "update"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "delete_listener or update_listener"
```

Expected: 2 failed — no `update`/`delete` entries are written yet (the listener returns `None` for those).

- [ ] **Step 3: Add UPDATE/DELETE handling**

Edit `healthflow/database/phi_audit.py`. Add this helper above `_on_do_orm_execute_audit`:

```python
def _extract_ids_from_where(orm_execute_state, model: type) -> list[str]:
    """Pull id-equality values out of an UPDATE/DELETE statement's WHERE clause.

    HealthFlow's PHI UPDATE/DELETE are id-based (WHERE id = :x). We walk the
    statement's WHERE clause looking for `<model>.id == <bound value>`
    comparisons and read the bound value.

    The tenant filter appends `AND broker_id = :tenant`, so the WHERE clause is
    typically a flat AND of two comparisons — `getattr(whereclause, "clauses",
    [whereclause])` handles both the single-comparison and flat-AND shapes. A
    deeply nested WHERE (AND/OR of AND/OR) is not recursed into; if a future
    UPDATE/DELETE uses one, row_ids will be empty but table/operation/endpoint
    are still recorded — documented limitation.
    """
    stmt = orm_execute_state.statement
    whereclause = getattr(stmt, "whereclause", None)
    if whereclause is None:
        return []
    # A single comparison has no `.clauses`; a flat AND/OR exposes its leaves there.
    candidates = getattr(whereclause, "clauses", [whereclause])
    ids: list[str] = []
    for clause in candidates:
        left = getattr(clause, "left", None)
        right = getattr(clause, "right", None)
        # left should be the `id` column; right a bound parameter carrying .value.
        if left is not None and getattr(left, "key", None) == "id" and hasattr(right, "value"):
            if right.value is not None:
                ids.append(str(right.value))
    return ids
```

Then replace the final `return None  # UPDATE/DELETE handled in Task 5` line in `_on_do_orm_execute_audit` with:

```python
    # UPDATE / DELETE: no result set to inspect — capture the affected id(s)
    # from the WHERE clause bind parameters and let execution proceed.
    operation = "update" if orm_execute_state.is_update else "delete"
    row_ids = _extract_ids_from_where(orm_execute_state, model)
    _write_audit_entry(
        orm_execute_state.session,
        table_name=_AUDITED_TABLE_NAMES[model],
        operation=operation,
        row_ids=row_ids,
    )
    return None  # let SQLAlchemy run the UPDATE/DELETE normally
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "delete_listener or update_listener"
```

Expected: 2 passed. If `_extract_ids_from_where` finds no ids (the WHERE-clause shape differs from what's assumed), the test will fail with `row_ids == []` — add a temporary `print(repr(whereclause), repr(candidates))` inside the helper, run the test, and inspect the actual clause structure (the `.left` / `.right` / `.key` attribute names, or whether `.clauses` is nested). Adjust the traversal to match. The table/operation/endpoint assertions should pass regardless; only the `row_ids` assertion is sensitive to the WHERE-clause shape.

- [ ] **Step 5: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 515 passed (513 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/phi_audit.py healthflow/tests/database/test_phi_audit.py
git commit -m "phi_audit: capture UPDATE/DELETE affected ids from WHERE clause"
```

---

## Task 6: `phi_audit.py` — the insert listener (`after_flush`)

**Files:**
- Modify: `healthflow/database/phi_audit.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

`do_orm_execute` never fires for `session.add()` + `flush()`. INSERTs are caught by `after_flush`, which exposes `session.new` — the set of objects being inserted.

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/database/test_phi_audit.py`:

```python
@pytest.mark.anyio
async def test_insert_listener_logs_created_phi_rows(audited_session):
    session, broker, _c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("POST /clients")
    try:
        new_client = Client(
            broker_id=broker.id, full_name="Created Client", zip_code="33101",
            age=70, income_level="low", doctors=[], prescriptions=[], procedures=[],
        )
        session.add(new_client)
        await session.flush()
        created_id = new_client.id
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.operation == "create")
        )).scalars().all()
    assert len(log) == 1
    assert log[0].table_name == "clients"
    assert log[0].row_ids == [str(created_id)]
    assert log[0].operation == "create"
    assert log[0].endpoint == "POST /clients"


@pytest.mark.anyio
async def test_insert_listener_ignores_non_phi_inserts(audited_session):
    session, _broker, _c1, _c2 = audited_session
    with system_context("verify"):
        # Inserting a Broker (not a PHI table) must not create a 'create' entry.
        b = Broker(email="ignored@t.test", hashed_password=hash_password("x"), full_name="X")
        session.add(b)
        await session.flush()
        await session.commit()
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.operation == "create")
        )).scalars().all()
    assert log == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "insert_listener"
```

Expected: `test_insert_listener_logs_created_phi_rows` fails (no `create` entry written); `test_insert_listener_ignores_non_phi_inserts` passes trivially (still no listener).

- [ ] **Step 3: Add the `after_flush` listener**

Edit `healthflow/database/phi_audit.py`. Add this listener function after `_on_do_orm_execute_audit`:

```python
def _on_after_flush_audit(session, flush_context):
    """after_flush listener: audit INSERTs of PHI rows.

    do_orm_execute does not fire for unit-of-work flushes, so freshly-inserted
    PHI rows are caught here via session.new. PhiAccessLog rows are skipped —
    they are not in _AUDITED_MODELS — so writing an audit entry does not
    recurse. Entries are grouped by model into one `create` entry per table.
    """
    by_model: dict[type, list[str]] = {}
    for obj in session.new:
        model = type(obj)
        if model in _AUDITED_MODELS and hasattr(obj, "id"):
            by_model.setdefault(model, []).append(str(obj.id))

    for model, row_ids in by_model.items():
        _write_audit_entry(
            session,
            table_name=_AUDITED_TABLE_NAMES[model],
            operation="create",
            row_ids=row_ids,
        )
```

Then register it inside `install_phi_audit` — add this alongside the existing `do_orm_execute` registration:

```python
def install_phi_audit(factory: async_sessionmaker) -> None:
    """Register the PHI audit listeners on this session factory.

    Idempotent. MUST be called AFTER install_tenant_filter — the audit
    listener invokes the statement and needs to see it already tenant-scoped.
    """
    target = factory.class_.sync_session_class
    if not event.contains(target, "do_orm_execute", _on_do_orm_execute_audit):
        event.listen(target, "do_orm_execute", _on_do_orm_execute_audit)
    if not event.contains(target, "after_flush", _on_after_flush_audit):
        event.listen(target, "after_flush", _on_after_flush_audit)
```

Note: `_write_audit_entry` calls `session.add(entry)` inside `after_flush`. SQLAlchemy permits adding new objects during `after_flush`; they are flushed in the same transaction. Because `PhiAccessLog` is not in `_AUDITED_MODELS`, adding it does not re-trigger audit logic — that is the recursion guard for the insert path. (Adding objects in `after_flush` can trigger a follow-up flush; the `by_model` filter on `_AUDITED_MODELS` means the follow-up sees only `PhiAccessLog` in `session.new`, which is ignored — the loop does nothing and there is no infinite cycle.)

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "insert_listener"
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 517 passed (515 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/phi_audit.py healthflow/tests/database/test_phi_audit.py
git commit -m "phi_audit: after_flush listener for INSERT — one create entry per PHI table"
```

---

## Task 7: Wire into production + conftest; self-exclusion + coexistence tests

**Files:**
- Modify: `healthflow/database/config.py`
- Modify: `healthflow/tests/conftest.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

- [ ] **Step 1: Write the self-exclusion + coexistence tests**

Append to `healthflow/tests/database/test_phi_audit.py`:

```python
@pytest.mark.anyio
async def test_phi_access_log_is_self_excluded_no_recursion(audited_session):
    """Writing and reading phi_access_log must not generate audit entries
    about phi_access_log itself."""
    session, broker, _c1, _c2 = audited_session
    # Trigger one real audit entry (a Client read).
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients")
    try:
        await session.execute(select(Client))
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    # Now read phi_access_log many times. If it were audited, each read would
    # append more entries and the count would grow.
    with system_context("verify"):
        first = (await session.execute(select(PhiAccessLog))).scalars().all()
        second = (await session.execute(select(PhiAccessLog))).scalars().all()
        third = (await session.execute(select(PhiAccessLog))).scalars().all()
    assert len(first) == len(second) == len(third) == 1
    assert all(e.table_name != "phi_access_log" for e in third)


@pytest.mark.anyio
async def test_audit_listener_sees_tenant_scoped_results(audited_session):
    """The audit listener runs AFTER the tenant filter, so row_ids reflect the
    tenant-scoped result, not the unscoped table."""
    session, broker, c1, c2 = audited_session
    # Add a second broker with a client that should NOT appear in broker A's
    # audit entry.
    with system_context("test setup"):
        broker_b = Broker(email="rb@t.test", hashed_password=hash_password("x"), full_name="RB")
        session.add(broker_b)
        await session.flush()
        cb = Client(
            broker_id=broker_b.id, full_name="B Client", zip_code="90210",
            age=33, income_level="high", doctors=[], prescriptions=[], procedures=[],
        )
        session.add(cb)
        await session.commit()

    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients")
    try:
        result = await session.execute(select(Client))
        rows = result.scalars().all()
        assert len(rows) == 2  # tenant filter scoped to broker A
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("verify"):
        log = (await session.execute(
            select(PhiAccessLog).where(PhiAccessLog.endpoint == "GET /clients")
        )).scalars().all()
    assert len(log) == 1
    assert set(log[0].row_ids) == {str(c1.id), str(c2.id)}
    assert str(cb.id) not in log[0].row_ids  # broker B's client was filtered out
```

- [ ] **Step 2: Run tests to verify they pass already**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "self_excluded or tenant_scoped_results"
```

Expected: 2 passed. These should pass with the listeners as built in Tasks 4-6 — `PhiAccessLog` is not in `_AUDITED_MODELS` (self-exclusion), and the `audited_session` fixture already installs the tenant filter before the audit listener (correct ordering). This task is *verifying* those properties hold, then wiring production.

If `test_audit_listener_sees_tenant_scoped_results` fails with broker B's client appearing, the listener ordering is wrong — confirm `install_tenant_filter` is called before `install_phi_audit` in the `audited_session` fixture.

- [ ] **Step 3: Wire `install_phi_audit` into `config.py`**

Edit `healthflow/database/config.py`. Change the import line:

```python
from healthflow.database.tenant_filter import install_raw_sql_guard, install_tenant_filter
```

to:

```python
from healthflow.database.phi_audit import install_phi_audit
from healthflow.database.tenant_filter import install_raw_sql_guard, install_tenant_filter
```

And in the install block (currently lines ~22-26), add `install_phi_audit` AFTER `install_tenant_filter`:

```python
# Install the tenant isolation listeners on the production engine and session
# factory. Done at import time so any code path that uses the default factory
# is automatically protected.
install_raw_sql_guard(engine)
install_tenant_filter(async_session_factory)
# PHI access audit listeners — MUST be installed after install_tenant_filter so
# the audit listener observes the already-tenant-scoped statement.
install_phi_audit(async_session_factory)
```

- [ ] **Step 4: Wire `install_phi_audit` into the test conftest**

Edit `healthflow/tests/conftest.py`. Find the `db_session_factory` fixture — Plan 1 added an `install_tenant_filter(factory)` call there. Add `install_phi_audit` immediately after it. The fixture should end up looking like:

```python
@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    from healthflow.database.tenant_filter import install_tenant_filter
    from healthflow.database.phi_audit import install_phi_audit

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(factory)
    install_phi_audit(factory)  # MUST come after install_tenant_filter
    return factory
```

(Match the existing fixture's exact structure — only add the import and the one `install_phi_audit(factory)` line after the existing `install_tenant_filter(factory)` line.)

- [ ] **Step 5: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 519 passed (517 + 2 new). Every test that exercises a PHI route now also writes audit entries — if a test asserted on exact DB row counts in a way that the audit table breaks, surface it (unlikely — `phi_access_log` is a separate table). The smoke test here is that the whole suite stays green with audit listeners live on the test factory.

- [ ] **Step 6: Commit**

```bash
git add healthflow/database/config.py healthflow/tests/conftest.py healthflow/tests/database/test_phi_audit.py
git commit -m "phi_audit: wire listeners into production + test factory; verify self-exclusion + ordering"
```

---

## Task 8: `scripts/audit_query.py` — CLI to read the log back

**Files:**
- Create: `scripts/audit_query.py`
- Test: `healthflow/tests/database/test_phi_audit.py`

- [ ] **Step 1: Write the failing test**

Append to `healthflow/tests/database/test_phi_audit.py`:

```python
from healthflow.database.phi_audit import query_by_broker, query_by_patient


@pytest.mark.anyio
async def test_query_by_patient_finds_entries_mentioning_that_patient(audited_session):
    session, broker, c1, c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients")
    try:
        await session.execute(select(Client))  # logs c1 + c2
        await session.execute(select(Client).where(Client.id == c1.id))  # logs c1
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("audit query"):
        c1_hits = await query_by_patient(session, str(c1.id))
        c2_hits = await query_by_patient(session, str(c2.id))
    # c1 appears in both the list read and the single read; c2 only in the list.
    assert len(c1_hits) == 2
    assert len(c2_hits) == 1
    assert all(str(c1.id) in e.row_ids for e in c1_hits)


@pytest.mark.anyio
async def test_query_by_broker_finds_that_brokers_entries(audited_session):
    session, broker, c1, _c2 = audited_session
    token = current_broker_id.set(broker.id)
    endpoint_token = current_endpoint.set("GET /clients/{id}")
    try:
        await session.execute(select(Client).where(Client.id == c1.id))
        await session.commit()
    finally:
        current_endpoint.reset(endpoint_token)
        current_broker_id.reset(token)

    with system_context("audit query"):
        hits = await query_by_broker(session, str(broker.id))
    assert len(hits) >= 1
    assert all(e.broker_id == broker.id for e in hits)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "query_by"
```

Expected: ImportError — `query_by_broker` / `query_by_patient` do not exist in `phi_audit`.

- [ ] **Step 3: Add the query functions to `phi_audit.py`**

Edit `healthflow/database/phi_audit.py`. Add these imports at the top (next to the existing `from sqlalchemy import event`):

```python
from sqlalchemy import event, func, select
```

Add these query functions at the end of the file:

```python
async def query_by_patient(session, patient_id: str) -> list[PhiAccessLog]:
    """Every audit entry whose row_ids list mentions this patient UUID.

    Uses SQLite's json_each to search the JSON array. Caller must run this
    inside system_context() — phi_access_log is a system table and reading it
    is a legitimate cross-tenant operation.
    """
    stmt = (
        select(PhiAccessLog)
        .where(
            func.json_array_length(PhiAccessLog.row_ids) > 0,
            PhiAccessLog.id.in_(
                select(PhiAccessLog.id)
                .select_from(
                    PhiAccessLog,
                    func.json_each(PhiAccessLog.row_ids).table_valued("value"),
                )
                .where(func.json_each(PhiAccessLog.row_ids).c.value == patient_id)
            ),
        )
        .order_by(PhiAccessLog.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def query_by_broker(session, broker_id: str) -> list[PhiAccessLog]:
    """Every audit entry for this broker, oldest first.

    Caller must run this inside system_context() — see query_by_patient.
    """
    stmt = (
        select(PhiAccessLog)
        .where(PhiAccessLog.broker_id == broker_id)
        .order_by(PhiAccessLog.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

Note on the `query_by_patient` JSON query: if the `json_each` table-valued construction proves awkward in SQLAlchemy 2.x against SQLite, a correct and simpler fallback is to load candidate rows and filter in Python: `select(PhiAccessLog).where(func.json_array_length(PhiAccessLog.row_ids) > 0)` then `[e for e in rows if patient_id in e.row_ids]`. At portfolio data volumes this is acceptable — note the fallback in a code comment if you take it.

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
.venv/bin/python -m pytest healthflow/tests/database/test_phi_audit.py -v -k "query_by"
```

Expected: 2 passed. If the `json_each` query errors, switch to the Python-filter fallback described above and re-run.

- [ ] **Step 5: Create the CLI script**

Create `scripts/audit_query.py`:

```python
#!/usr/bin/env python3
"""Read the PHI access audit log.

Usage:
    python scripts/audit_query.py --patient <uuid>   # who touched this patient's records
    python scripts/audit_query.py --broker <uuid>    # everything this broker did

Runs inside system_context() — phi_access_log is a system table, and reading
it for a breach investigation is a legitimate cross-tenant operation.
"""
import argparse
import asyncio
import sys

from healthflow.auth.tenant_context import system_context
from healthflow.database.config import async_session_factory
from healthflow.database.phi_audit import query_by_broker, query_by_patient


def _print_entries(entries) -> None:
    if not entries:
        print("  (no matching audit entries)")
        return
    for e in entries:
        broker = str(e.broker_id) if e.broker_id else "system"
        ids = ", ".join(e.row_ids) if e.row_ids else "—"
        print(
            f"  {e.created_at.isoformat()}  {e.operation:6}  {e.table_name:14}  "
            f"broker={broker}  endpoint={e.endpoint}  rows=[{ids}]"
        )


async def _main(args) -> int:
    async with async_session_factory() as session:
        with system_context("audit query CLI"):
            if args.patient:
                print(f"PHI access entries mentioning patient {args.patient}:")
                _print_entries(await query_by_patient(session, args.patient))
            else:
                print(f"PHI access entries for broker {args.broker}:")
                _print_entries(await query_by_broker(session, args.broker))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the PHI access audit log.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--patient", help="Patient (client) UUID to search for")
    group.add_argument("--broker", help="Broker UUID to search for")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Smoke-test the CLI**

```bash
.venv/bin/python scripts/audit_query.py --broker 00000000-0000-0000-0000-000000000000
```

Expected: prints the header line and `(no matching audit entries)` — proves the script imports, connects, and runs the query without error against the real (empty-of-matches) `healthflow.db`. (It is fine if `healthflow.db` has unrelated entries; a random zero-UUID broker will simply have none.)

- [ ] **Step 7: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 521 passed (519 + 2 new).

- [ ] **Step 8: Commit**

```bash
git add healthflow/database/phi_audit.py scripts/audit_query.py healthflow/tests/database/test_phi_audit.py
git commit -m "phi_audit: query_by_patient / query_by_broker + audit_query.py CLI"
```

---

## Task 9: Update the `healthflow-security` skill

**Files:**
- Modify: `.claude/skills/healthflow-security/SKILL.md`

- [ ] **Step 1: Read the current skill**

```bash
cat .claude/skills/healthflow-security/SKILL.md
```

It has YAML frontmatter, then sections including "Tenant isolation is enforced by infrastructure, not code review" and "PHI on the wire to Anthropic". Don't touch the frontmatter.

- [ ] **Step 2: Add a new section documenting the audit log**

Edit `.claude/skills/healthflow-security/SKILL.md`. Add this new section immediately after the "Tenant isolation is enforced by infrastructure, not code review" section (audit logging is the natural companion to tenant isolation — both are SQLAlchemy-listener-enforced):

```markdown
## Every PHI access is audited automatically

Every query against a PHI table (`clients`, `action_history`, `feedback`)
writes an append-only row to `phi_access_log` — who (broker), what (table +
operation), which patients (result row IDs), how/why (request endpoint), and
when. Enforced by two SQLAlchemy listeners in `healthflow/database/phi_audit.py`
(`do_orm_execute` for read/update/delete, `after_flush` for inserts), installed
at startup *after* the tenant filter. You never call an audit function — it
fires on its own.

**Rule:** `phi_access_log` is a system table — NOT in `TENANT_SCOPED_MODELS`,
NOT audited by its own listeners (writing an entry is a DB write; auditing the
audit table would recurse forever). When adding a new PHI table, add it to
`_AUDITED_MODELS` in `phi_audit.py` AND `TENANT_SCOPED_MODELS` in
`tenant_filter.py` — they are deliberately separate lists but a new PHI table
belongs in both.

**Rule:** Background/system code that touches PHI must run inside
`system_context(reason="...")` — the reason becomes the audit entry's
`endpoint` as `system:<reason>`, so the audit trail explains itself. Code that
runs with no broker and no `system_context` records `endpoint="unknown"` —
that is a smell worth investigating.

**Rule:** Listener ordering is load-bearing. `install_phi_audit` MUST be
called after `install_tenant_filter` (in `config.py` and the test conftest) —
the audit listener invokes the statement and must observe it already
tenant-scoped, so `row_ids` reflects what the broker could actually see.

**Rule:** Read the audit log via `scripts/audit_query.py` (`--patient` /
`--broker`). It runs inside `system_context()` because reading the whole audit
trail is a legitimate cross-tenant operation. An admin API endpoint is a
follow-up that depends on admin RBAC.
```

- [ ] **Step 3: Verify the frontmatter is intact**

```bash
head -10 .claude/skills/healthflow-security/SKILL.md
```

The `---` frontmatter block must be unchanged.

- [ ] **Step 4: Run the full suite (no behavior change)**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 521 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/healthflow-security/SKILL.md
git commit -m "skill: healthflow-security — document the PHI access audit log"
```

---

## Task 10: Final verification + push + PR

**Files:** None — verification only.

- [ ] **Step 1: Confirm full suite is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: `521 passed`.

- [ ] **Step 2: Run `make check` (lint + tests + frontend build)**

```bash
make check 2>&1 | tail -20
```

Expected: tests green; lint shows only the pre-existing errors (this branch should introduce none). If this branch introduced a new lint error, fix it before pushing.

- [ ] **Step 3: Hand-verify the audit trail end-to-end against a real session**

```bash
.venv/bin/python -c "
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from healthflow.database.models import Base, Broker, Client, PhiAccessLog
from healthflow.database.tenant_filter import install_tenant_filter
from healthflow.database.phi_audit import install_phi_audit
from healthflow.auth.security import hash_password
from healthflow.auth.tenant_context import current_broker_id, current_endpoint, system_context

async def main():
    engine = create_async_engine('sqlite+aiosqlite:///', echo=False)
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    install_tenant_filter(f)
    install_phi_audit(f)
    async with f() as s:
        with system_context('setup'):
            b = Broker(email='v@t.test', hashed_password=hash_password('x'), full_name='V')
            s.add(b); await s.flush()
            cl = Client(broker_id=b.id, full_name='V Client', zip_code='10001', age=40,
                        income_level='low', doctors=[], prescriptions=[], procedures=[])
            s.add(cl); await s.commit()
        t = current_broker_id.set(b.id); e = current_endpoint.set('GET /clients')
        try:
            await s.execute(select(Client))
        finally:
            current_endpoint.reset(e); current_broker_id.reset(t)
        with system_context('verify'):
            log = (await s.execute(select(PhiAccessLog))).scalars().all()
        # expect: 1 create (from setup flush) + 1 read
        ops = sorted(x.operation for x in log)
        assert ops == ['create', 'read'], ops
        assert all(x.endpoint for x in log)
        print('audit trail end-to-end: OK —', ops)
    await engine.dispose()

asyncio.run(main())
"
```

Expected: `audit trail end-to-end: OK — ['create', 'read']`.

- [ ] **Step 4: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: 8 commits (Tasks 1 and 10 don't commit):
- `skill: healthflow-security — document the PHI access audit log`
- `phi_audit: query_by_patient / query_by_broker + audit_query.py CLI`
- `phi_audit: wire listeners into production + test factory; verify self-exclusion + ordering`
- `phi_audit: after_flush listener for INSERT — one create entry per PHI table`
- `phi_audit: capture UPDATE/DELETE affected ids from WHERE clause`
- `phi_audit: do_orm_execute listener for SELECT — captures result row IDs`
- `Add current_endpoint ContextVar + EndpointContextMiddleware`
- `Add PhiAccessLog model for the PHI access audit trail`

Each message terse, no `Co-Authored-By` trailer.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin phi-audit-log/access-trail 2>&1 | tail -5
```

- [ ] **Step 6: Open the PR**

```bash
gh pr create --title "PHI access audit log: append-only trail of who touched which patient's data" --body "$(cat <<'EOF'
## Summary

Adds a durable, queryable PHI access audit trail — sub-project #3 of the HIPAA-readiness foundation. Every query against a PHI table now writes one append-only row to `phi_access_log` recording who, what, which patients, how/why, and when. Coverage is enforced by SQLAlchemy event listeners, not developer discipline.

- `healthflow/database/models.py` — new `PhiAccessLog` model. A system table: not tenant-scoped, not audited by its own listeners.
- `healthflow/database/phi_audit.py` (new) — two listeners. `do_orm_execute` handles SELECT (via `Result.freeze()` to observe result row IDs and still return a usable result) and UPDATE/DELETE (affected ID from the WHERE clause). `after_flush` handles INSERTs, which `do_orm_execute` never sees. Plus `query_by_patient` / `query_by_broker`.
- `healthflow/auth/tenant_context.py` — new `current_endpoint` ContextVar; `system_context(reason)` now also sets it to `system:<reason>` so background work self-describes in the audit trail.
- `healthflow/api/middleware.py` — `EndpointContextMiddleware` sets `current_endpoint` per HTTP request.
- `healthflow/database/config.py` + `tests/conftest.py` — `install_phi_audit` wired in, **after** `install_tenant_filter` (the audit listener must observe the already-tenant-scoped statement).
- `scripts/audit_query.py` (new) — CLI: `--patient <uuid>` / `--broker <uuid>`.
- `.claude/skills/healthflow-security/SKILL.md` — documents the audit-log enforcement model.

## Threat model / scope

Breach investigation + compliance evidence (HIPAA §164.312(b)). Per-query granularity with result row IDs captured. Same-transaction writes — successful access only; failed *attempts* are out of scope (pairs with anomaly detection). Read surface is a CLI; an admin endpoint is deferred until admin RBAC exists.

## Test Plan

- [x] 17 new tests in `tests/database/test_phi_audit.py`: model roundtrip, `current_endpoint` + `system_context`, read listener (single/list/system-context/non-PHI), update + delete, insert (PHI + non-PHI), self-exclusion (no recursion), tenant-filter coexistence (audit sees scoped results), `query_by_patient` / `query_by_broker`
- [x] Full backend suite: 521/521 (was 504; +17)
- [x] End-to-end hand-verification: a create + a read produce exactly two audit entries with endpoints set
- [ ] CI green on this PR

## Out of scope / follow-ups

- Failed-attempt logging (pairs with real-time anomaly detection).
- Admin API endpoint for the audit log (depends on admin RBAC — deferred follow-up from the multi-tenancy work).
- Automated retention/archival (HIPAA's ~6-year expectation is noted in the spec; automation deferred).
- A `phi_access_log_rows` join table for scale (YAGNI until real volume).
- Auth hardening (sub-project #4), encryption at rest (sub-project #5).
EOF
)" 2>&1 | tail -3
```

Expected: a GitHub PR URL. Capture and report it.

No new commit for this task.
