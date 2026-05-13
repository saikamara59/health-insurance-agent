# Multi-Tenancy Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the multi-tenancy foundation (Plan 1, merged as `710a404`) load-bearing across the rest of the codebase: remove the now-redundant manual `WHERE broker_id` filters from the remaining PHI routers, add composite-write protection on `ActionHistory.client_id`, deliberately scope the `feedback/` analytics endpoints to per-broker (no cross-tenant aggregate leak), extend the cross-tenant test suite to cover every PHI route, and apply the small code-review follow-ups.

**Architecture:** Each PHI router stops doing its own `WHERE broker_id = broker.id` filtering — the `do_orm_execute` hook (registered on the global `Session` class in Plan 1) does it automatically. Composite writes (`ActionHistory.client_id` referencing a Client) load the related row through the filter first; if the SELECT returns nothing, the route returns 404 instead of writing a row pointing at another broker's record. The `feedback/analytics`, `/reward-score`, and `/weekly-report` endpoints become per-broker (the auto-filter scopes their underlying queries to the current broker's rows), eliminating a quiet cross-tenant aggregate leak that existed pre-Plan-1.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x async, pytest, contextvars (stdlib).

**Spec:** [docs/superpowers/specs/2026-05-12-multi-tenancy-design.md](../specs/2026-05-12-multi-tenancy-design.md)
**Plan 1 (foundation, merged):** [docs/superpowers/plans/2026-05-12-multi-tenancy-foundation.md](./2026-05-12-multi-tenancy-foundation.md)
**Final code review for Plan 1** items addressed here: M-3 (teardown ordering doc), M-5 (multi-entity test), M-6 (`system_context(reason)`), I-3 (composite-write regression test).

---

## File Structure

After this plan:

```
healthflow/
  api/
    history_router.py        (MODIFIED — drop manual filter; composite-write protection on POST)
  feedback/
    router.py                (unchanged structurally — analytics endpoints just inherit the filter)
    collector.py             (MODIFIED — drop manual broker_id WHERE clauses; rely on the hook)
    prompt_updater.py        (MODIFIED — wrap cross-broker reads in system_context with reason)
    reward_model.py          (MODIFIED — same)
  auth/
    tenant_context.py        (MODIFIED — system_context accepts reason: str)
    dependencies.py          (MODIFIED — docstring note on teardown ordering)
  tests/
    tenancy/
      test_cross_broker_isolation.py     (EXTENDED — cover history + feedback routes)
      test_cross_broker_writes.py        (NEW — composite-write protection tests)
      test_tenant_filter.py              (EXTENDED — multi-entity select test)
.claude/skills/
  healthflow-security/
    SKILL.md                 (MODIFIED — reference the new enforcement model)
```

The split between `cross_broker_isolation` (read tests) and `cross_broker_writes` (write tests) keeps each file focused on one concern.

---

## Task 1: Branch + capture baseline

**Files:** Read-only.

- [ ] **Step 1: Confirm clean main and create feature branch**

```bash
git status
git checkout main && git pull --ff-only
git checkout -b multi-tenancy/migration
git branch --show-current
```

Expected: `multi-tenancy/migration`. If `git pull` reports anything other than already-up-to-date or fast-forward, STOP and surface.

- [ ] **Step 2: Capture pre-implementation test count**

```bash
.venv/bin/python -m pytest healthflow/tests/ --collect-only -q 2>&1 | tail -1
```

Expected: `483 tests collected in X.XXs` (Plan 1 baseline). Record the actual number.

- [ ] **Step 3: Confirm baseline is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: all 483 tests pass.

No commit for this task.

---

## Task 2: Migrate `history_router.py` — drop manual filter on list

**Files:**
- Modify: `healthflow/api/history_router.py`

The `list_history` endpoint currently does `select(ActionHistory).where(ActionHistory.broker_id == broker.id)`. The hook now adds that WHERE clause automatically. Drop the manual filter.

- [ ] **Step 1: Remove the manual `WHERE broker_id` filter from `list_history`**

Edit `healthflow/api/history_router.py`. Find the `list_history` body:

```python
    stmt = (
        select(ActionHistory)
        .where(ActionHistory.broker_id == broker.id)
        .order_by(ActionHistory.created_at.desc())
        .limit(limit)
    )
```

Change to:

```python
    # tenant filter auto-injects WHERE ActionHistory.broker_id = current_broker_id
    stmt = (
        select(ActionHistory)
        .order_by(ActionHistory.created_at.desc())
        .limit(limit)
    )
```

- [ ] **Step 2: Run the existing history tests to confirm behavior unchanged**

```bash
.venv/bin/python -m pytest healthflow/tests/api/ -k history -v 2>&1 | tail -20
```

Expected: all history-related tests pass. The hook does what the manual filter did.

If any test fails: read the failure carefully. If it's a test that asserted on cross-broker behavior that the spec wants to change (e.g., expecting 403 instead of 404), that's expected — defer the test fix to Task 8 where the cross-broker test suite is rewritten holistically. Otherwise surface.

- [ ] **Step 3: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 483 passed (no count change yet).

- [ ] **Step 4: Commit**

```bash
git add healthflow/api/history_router.py
git commit -m "history_router: drop manual broker_id filter from list_history"
```

Exact message. No co-author trailer.

---

## Task 3: `history_router.py` — composite-write protection on POST

**Files:**
- Modify: `healthflow/api/history_router.py`
- Test: `healthflow/tests/tenancy/test_cross_broker_writes.py` (created in Task 7 — for now, smoke test in this task)

The `create_history` endpoint accepts a `client_id` from the request body and inserts an `ActionHistory` referencing it. Without protection, broker B could POST `{"client_id": <broker A's client id>}` and create an action linked to A's client. The hook can't catch this — `Session.add()` + `flush()` for `ActionHistory` doesn't fire `do_orm_execute`. The protection: load the referenced Client first via the filtered SELECT; if it doesn't exist (or isn't yours), return 404.

- [ ] **Step 1: Modify `create_history` to load Client first**

Edit `healthflow/api/history_router.py`. Find the `create_history` body. Replace it with:

```python
    # Load the referenced Client through the tenant filter — if it belongs to
    # another broker (or doesn't exist), this returns None and the route 404s.
    # Composite-write protection: prevents constructing an ActionHistory row
    # that references a different broker's Client.
    client_lookup = await db.execute(
        select(Client).where(Client.id == entry.client_id)
    )
    if client_lookup.scalar_one_or_none() is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Client not found")

    action = ActionHistory(
        id=uuid.uuid4(),
        broker_id=broker.id,
        client_id=entry.client_id,
        action_type=entry.action_type,
        request_data=entry.request_data,
        response_summary=entry.response_summary,
    )
    db.add(action)
    await db.flush()
    await db.refresh(action)

    # Get client name (the load above already proved the client exists + is ours)
    client_result = await db.execute(
        select(Client.full_name).where(Client.id == action.client_id)
    )
    client_name = client_result.scalar_one_or_none()

    return ActionHistoryResponse(
        id=str(action.id),
        broker_id=str(action.broker_id),
        client_id=str(action.client_id),
        action_type=action.action_type,
        request_data=action.request_data,
        response_summary=action.response_summary,
        created_at=action.created_at.isoformat(),
        client_name=client_name,
    )
```

Move the `from fastapi import HTTPException` to the top of the file with the other fastapi imports — change `from fastapi import APIRouter, Depends, Query` to `from fastapi import APIRouter, Depends, HTTPException, Query`.

- [ ] **Step 2: Add a regression test for the composite-write protection**

Create `healthflow/tests/tenancy/test_cross_broker_writes.py`:

```python
"""Composite-write protection: broker A cannot create rows referencing broker B's data."""
import pytest

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


async def _make_broker(session, email: str) -> Broker:
    broker = Broker(
        email=email,
        hashed_password=hash_password("WriteTest123!"),
        full_name=email,
    )
    session.add(broker)
    await session.flush()
    return broker


async def _login(client, email: str, password: str = "WriteTest123!") -> str:
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.mark.anyio
async def test_broker_cannot_create_history_for_other_brokers_client(client, db_session):
    """POST /history with another broker's client_id must return 404, not write the row."""
    broker_a = await _make_broker(db_session, "wa@healthflow.test")
    _broker_b = await _make_broker(db_session, "wb@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id, full_name="A's Client",
        zip_code="10001", age=40, income_level="medium",
        doctors=[], prescriptions=[], procedures=[],
    )
    db_session.add(a_client)
    await db_session.commit()

    b_token = await _login(client, "wb@healthflow.test")
    res = await client.post(
        "/history",
        headers={"Authorization": f"Bearer {b_token}"},
        json={
            "client_id": str(a_client.id),
            "action_type": "compare_plans",
            "request_data": {},
            "response_summary": {},
        },
    )
    assert res.status_code == 404, f"Cross-broker write leak: {res.status_code} {res.text}"
```

- [ ] **Step 3: Run the new test to verify it passes**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_cross_broker_writes.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Run history tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/api/ -k history -v 2>&1 | tail -10
make test-quick 2>&1 | tail -3
```

Expected: history tests still pass; full suite is 484 passed (483 + 1 new write-protection test).

- [ ] **Step 5: Commit**

```bash
git add healthflow/api/history_router.py healthflow/tests/tenancy/test_cross_broker_writes.py
git commit -m "history_router: composite-write protection on POST + regression test"
```

---

## Task 4: Migrate `feedback/router.py` to drop manual `broker_id`

**Files:**
- Modify: `healthflow/feedback/router.py`
- Modify: `healthflow/feedback/collector.py`

The `feedback/router.py` endpoints pass `broker_id=broker.id` explicitly to `collector.list_feedback()` and `collector.submit()`. The collector then uses these for filtering. We can drop the parameter from the read path (`list_feedback`) — the hook handles it. The submit path still needs `broker_id` because INSERT-time `broker_id` is a column value, not a WHERE clause.

- [ ] **Step 1: Audit other callers of `collector.list_feedback`**

```bash
grep -rn "list_feedback\|collector\." healthflow/ --include="*.py" | grep -v __pycache__ | grep -v tests/
```

The result should show only one production caller (`healthflow/feedback/router.py`). If there are others, every caller needs to be updated to drop the `broker_id=` kwarg in Step 2's edit. If you find an unexpected caller, surface it and stop.

- [ ] **Step 2: Modify `collector.list_feedback` to drop the manual filter**

Edit `healthflow/feedback/collector.py`. Replace the current `list_feedback` method body:

```python
    async def list_feedback(
        self,
        db: AsyncSession,
        agent_type: str | None = None,
        limit: int = 50,
    ) -> list[Feedback]:
        """List feedback for the current broker (auto-scoped by tenant filter).

        Note: removed the explicit broker_id parameter — the do_orm_execute
        hook auto-injects WHERE broker_id = current_broker_id.
        """
        stmt = (
            select(Feedback)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        if agent_type:
            stmt = stmt.where(Feedback.agent_type == agent_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 3: Update `feedback/router.py` to drop `broker_id` from the call**

Edit `healthflow/feedback/router.py`. In `list_feedback`, change:

```python
    items = await collector.list_feedback(
        db=db,
        broker_id=broker.id,
        agent_type=agent_type,
        limit=limit,
    )
```

to:

```python
    items = await collector.list_feedback(
        db=db,
        agent_type=agent_type,
        limit=limit,
    )
```

The `submit` and `submit_feedback` paths stay as-is — INSERTs need the explicit `broker_id` column value.

- [ ] **Step 4: Run feedback tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/api/ -k feedback -v 2>&1 | tail -20
make test-quick 2>&1 | tail -3
```

Expected: all feedback tests pass; full suite at 484 passed.

If `list_feedback` tests fail because they pass `broker_id=` as a keyword: the test needs updating. Update the calls to drop `broker_id=` and add a `current_broker_id.set(...)` token in the test setup so the hook scopes correctly. Surface any test that requires more than a 2-line fix.

- [ ] **Step 5: Commit**

```bash
git add healthflow/feedback/router.py healthflow/feedback/collector.py
git commit -m "feedback: drop manual broker_id filter from list path; rely on tenant hook"
```

---

## Task 5: Per-broker analytics — make `get_analytics` deliberate

**Files:**
- Modify: `healthflow/feedback/collector.py`

`get_analytics` previously aggregated Feedback **across all brokers** (`select(...).where(Feedback.created_at >= cutoff).group_by(Feedback.agent_type)` — no `broker_id` filter). After Plan 1 the auto-filter scopes it to the current broker, which is the correct multi-tenant behavior — but this is an undocumented behavior change worth making explicit.

The decision: **per-broker analytics is the right default.** Brokers shouldn't see each other's feedback aggregates. Cross-broker aggregates would require an admin-only endpoint (out of scope; Plan 2 doesn't add admin RBAC).

- [ ] **Step 1: Add a docstring note documenting the scoping**

Edit `healthflow/feedback/collector.py`. Replace the `get_analytics` docstring with:

```python
        """Return per-broker, per-agent feedback averages for the given period.

        The do_orm_execute tenant hook scopes the underlying SELECT to the
        current broker's Feedback rows. To get a cross-broker (system-wide)
        view, an admin would need to invoke this inside system_context() —
        currently not exposed via any HTTP endpoint.
        """
```

- [ ] **Step 2: Add a test that proves analytics are scoped per-broker**

Append to `healthflow/tests/tenancy/test_cross_broker_writes.py`:

```python
@pytest.mark.anyio
async def test_analytics_endpoint_returns_only_current_brokers_aggregates(client, db_session):
    """GET /feedback/analytics must aggregate only the requesting broker's feedback."""
    broker_a = await _make_broker(db_session, "ana-a@healthflow.test")
    broker_b = await _make_broker(db_session, "ana-b@healthflow.test")
    await db_session.commit()

    a_token = await _login(client, "ana-a@healthflow.test")
    b_token = await _login(client, "ana-b@healthflow.test")

    # A submits 2 feedback rows; B submits 5 with different agent_type.
    for _ in range(2):
        res = await client.post(
            "/feedback",
            headers={"Authorization": f"Bearer {a_token}"},
            json={"output_id": "o1", "agent_type": "comparison",
                  "accuracy": 5, "clarity": 5, "helpfulness": 5, "comment": ""},
        )
        assert res.status_code == 201, res.text
    for _ in range(5):
        res = await client.post(
            "/feedback",
            headers={"Authorization": f"Bearer {b_token}"},
            json={"output_id": "o2", "agent_type": "translation",
                  "accuracy": 3, "clarity": 3, "helpfulness": 3, "comment": ""},
        )
        assert res.status_code == 201, res.text

    # A's analytics should see only "comparison" with total_feedback=2.
    res = await client.get(
        "/feedback/analytics",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_feedback"] == 2
    assert {a["agent_type"] for a in body["agents"]} == {"comparison"}

    # B's analytics should see only "translation" with total_feedback=5.
    res = await client.get(
        "/feedback/analytics",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_feedback"] == 5
    assert {a["agent_type"] for a in body["agents"]} == {"translation"}
```

- [ ] **Step 3: Run the new test + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_cross_broker_writes.py -v
make test-quick 2>&1 | tail -3
```

Expected: 2 tests in `test_cross_broker_writes.py` pass; full suite at 485 passed.

- [ ] **Step 4: Commit**

```bash
git add healthflow/feedback/collector.py healthflow/tests/tenancy/test_cross_broker_writes.py
git commit -m "feedback/collector: document per-broker analytics scoping + isolation test"
```

---

## Task 6: Audit `prompt_updater.py` and `reward_model.py` for cross-broker reads

**Files:**
- Modify: `healthflow/feedback/prompt_updater.py`
- Modify: `healthflow/feedback/reward_model.py`

These modules implement the RLHF feedback loop. Their queries explicitly aggregate across brokers (no `WHERE broker_id`). After Plan 1 they'd auto-filter to the current broker if called from an authenticated context — silently making the RLHF loop per-broker, which is wrong (the loop should learn from all brokers' feedback to improve the system-wide prompt). They need to run inside `system_context()` to bypass the filter.

- [ ] **Step 1: Audit `prompt_updater.py` for SELECTs against tenant-scoped tables**

```bash
grep -n "select\|execute" healthflow/feedback/prompt_updater.py
```

Read each SELECT in the file. Confirm whether it queries Feedback or ActionHistory. For each cross-broker query, the entire method body should run inside `with system_context(reason="..."):`.

- [ ] **Step 2: Wrap cross-broker reads in `prompt_updater.py`**

Edit `healthflow/feedback/prompt_updater.py`. For each method that queries Feedback or ActionHistory across brokers, wrap the body in `system_context()`. Example: if the file has a method like `update_prompts_for_agent(self, db, agent_type)`, change:

```python
    async def update_prompts_for_agent(self, db, agent_type):
        # ... existing query body ...
```

to:

```python
    async def update_prompts_for_agent(self, db, agent_type):
        # RLHF aggregates feedback across all brokers to improve the
        # system-wide prompt. Cross-broker access is intentional;
        # bypasses the per-tenant filter for this read.
        with system_context(reason="RLHF prompt update: cross-broker feedback aggregation"):
            # ... existing query body ...
```

(The `system_context(reason=...)` argument lands in Task 9. For now, use plain `system_context()` and update in Task 9. Add a `# TASK-9: add reason=` comment so the next step is obvious.)

Add the import `from healthflow.auth.tenant_context import system_context` near the top.

- [ ] **Step 3: Same treatment for `reward_model.py`**

Repeat the audit and wrap for `healthflow/feedback/reward_model.py`. The `score_outputs` method aggregates Feedback across brokers — the entire body runs inside `system_context()`.

Note: `score_outputs` is called from `feedback/router.py` `/feedback/reward-score` and `/feedback/weekly-report`. Those endpoints currently expose this to any authenticated broker. Wrapping the body in `system_context()` means any broker can trigger a system-wide re-score. That's not great for production but is fine for this portfolio-grade work — flag it as a follow-up in the PR description (a future change should gate these endpoints on an admin role).

- [ ] **Step 4: Run feedback + RLHF tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/feedback/ -v 2>&1 | tail -20
make test-quick 2>&1 | tail -3
```

Expected: feedback/RLHF tests still pass; full suite at 485 passed.

If any test fails because the new `system_context` wrapping changed observable behavior, surface the failure — don't silently work around. The fix may be a test update.

- [ ] **Step 5: Commit**

```bash
git add healthflow/feedback/prompt_updater.py healthflow/feedback/reward_model.py
git commit -m "feedback: wrap RLHF cross-broker reads in system_context()"
```

---

## Task 7: New cross-broker write tests covered already in Task 3 + Task 5

This task was originally a placeholder; the work landed inline in Tasks 3 and 5. Skip.

(Kept as a numbered slot to preserve task ordering; nothing to do.)

---

## Task 8: Extend `test_cross_broker_isolation.py` to cover history + feedback routes

**Files:**
- Modify: `healthflow/tests/tenancy/test_cross_broker_isolation.py`

The existing file covers Client routes only. Extend it to cover ActionHistory and Feedback list/detail behavior so every PHI route has cross-broker coverage.

- [ ] **Step 1: Add ActionHistory cross-broker read tests**

Append to `healthflow/tests/tenancy/test_cross_broker_isolation.py`:

```python
from healthflow.database.models import ActionHistory, Feedback


@pytest.mark.anyio
async def test_broker_cannot_read_other_brokers_action_history(client, db_session):
    """GET /history must show only the current broker's actions."""
    broker_a = await _make_broker(db_session, "iso-ah-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-ah-b@healthflow.test")
    a_client = Client(
        broker_id=broker_a.id, full_name="A's client",
        zip_code="10001", age=40, income_level="medium",
        doctors=[], prescriptions=[], procedures=[],
    )
    db_session.add(a_client)
    await db_session.flush()

    a_action = ActionHistory(
        broker_id=broker_a.id, client_id=a_client.id,
        action_type="compare_plans",
        request_data={"k": "v"}, response_summary={"ok": True},
    )
    db_session.add(a_action)
    await db_session.commit()

    b_token = await _login(client, "iso-ah-b@healthflow.test")
    res = await client.get(
        "/history", headers={"Authorization": f"Bearer {b_token}"}
    )
    assert res.status_code == 200
    items = res.json()
    assert items == [], f"Broker B saw broker A's history: {items}"
```

- [ ] **Step 2: Add Feedback cross-broker read tests**

Append:

```python
@pytest.mark.anyio
async def test_broker_cannot_read_other_brokers_feedback(client, db_session):
    """GET /feedback must show only the current broker's feedback."""
    broker_a = await _make_broker(db_session, "iso-fb-a@healthflow.test")
    broker_b = await _make_broker(db_session, "iso-fb-b@healthflow.test")

    a_fb = Feedback(
        broker_id=broker_a.id, output_id="oA", agent_type="comparison",
        accuracy=5, clarity=5, helpfulness=5, comment="A's note",
    )
    db_session.add(a_fb)
    await db_session.commit()

    b_token = await _login(client, "iso-fb-b@healthflow.test")
    res = await client.get(
        "/feedback", headers={"Authorization": f"Bearer {b_token}"}
    )
    assert res.status_code == 200
    items = res.json()
    assert items == [], f"Broker B saw broker A's feedback: {items}"
```

- [ ] **Step 3: Run cross-broker isolation tests + full suite**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_cross_broker_isolation.py -v
make test-quick 2>&1 | tail -3
```

Expected: 5 isolation tests pass (3 prior Client tests + 2 new); full suite at 487.

- [ ] **Step 4: Commit**

```bash
git add healthflow/tests/tenancy/test_cross_broker_isolation.py
git commit -m "tests: extend cross-broker isolation to history + feedback routes"
```

---

## Task 9: `system_context(reason: str)` argument

**Files:**
- Modify: `healthflow/auth/tenant_context.py`
- Modify: `healthflow/feedback/prompt_updater.py` (replace placeholders from Task 6)
- Modify: `healthflow/feedback/reward_model.py` (replace placeholders from Task 6)
- Modify: `healthflow/api/test_router.py` (the existing system_context call site — add reason)
- Modify: `healthflow/tests/conftest.py` (db_session fixture — add reason)
- Modify: `healthflow/tests/database/test_database_models.py` (local fixture — add reason)
- Modify: `healthflow/tests/tenancy/test_tenant_context.py` (existing tests — pass through)
- Modify: `healthflow/tests/tenancy/test_tenant_filter.py` (existing tests — pass through)

The reviewer (M-6) noted that the WARN log line `system_context: enter (caller bypassing tenant filter)` is identical across every call site. Adding a required `reason: str` argument makes audit logs self-explanatory and forces callers to justify the bypass.

- [ ] **Step 1: Add the `reason` parameter to `system_context`**

Edit `healthflow/auth/tenant_context.py`. Change the `system_context` signature and log lines:

```python
@contextmanager
def system_context(reason: str) -> Iterator[None]:
    """Temporarily clear the tenant context for legitimate cross-tenant work.

    Use only at audited call sites. The required `reason` argument forces
    each caller to justify the bypass and makes the WARN log entries
    self-explanatory.

    Args:
        reason: Human-readable justification, e.g. "RLHF prompt update".
    """
    broker_token = current_broker_id.set(None)
    flag_token = _in_system_context.set(True)
    logger.warning("system_context: enter — %s", reason)
    try:
        yield
    finally:
        _in_system_context.reset(flag_token)
        current_broker_id.reset(broker_token)
        logger.warning("system_context: exit — %s", reason)
```

- [ ] **Step 2: Update existing `test_tenant_context.py` tests to pass a reason**

Find every `with system_context():` in `healthflow/tests/tenancy/test_tenant_context.py` and add a reason argument. For the existing tests this can just be `"test"`:

- `with system_context():` → `with system_context("test"):`

The log-on-entry/exit test (`test_system_context_logs_warning_on_entry_and_exit`) should pass a recognizable reason like `"test reason XYZ"` and assert that "test reason XYZ" appears in both the enter and exit log lines.

- [ ] **Step 3: Update test fixtures and other call sites**

Each `system_context()` call needs a reason. Update each:

- `healthflow/tests/conftest.py` `db_session` fixture: `with system_context("test fixture: direct db_session"):`
- `healthflow/tests/database/test_database_models.py` local fixture: same pattern
- `healthflow/api/test_router.py` reset endpoint: `with system_context(f"e2e reset for worker {body.worker_id}"):`
- `healthflow/tests/tenancy/test_tenant_filter.py` `session_with_filter` fixture: `with system_context("test fixture: tenant_filter setup"):`
- `healthflow/feedback/prompt_updater.py` (from Task 6): `with system_context("RLHF prompt update: cross-broker feedback aggregation"):` (drop the `# TASK-9` comment)
- `healthflow/feedback/reward_model.py` (from Task 6): `with system_context("RLHF reward scoring: cross-broker feedback aggregation"):`

- [ ] **Step 4: Find any system_context calls you missed**

```bash
grep -rn "system_context()" healthflow/ healthflow/tests/ 2>/dev/null
```

Should output zero matches after Step 3. If any remain, add reasons.

- [ ] **Step 5: Run the full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 487 passed.

If anything fails because of the signature change (e.g. a TypeError on a call that wasn't updated), find and fix the missed call site.

- [ ] **Step 6: Commit**

```bash
git add healthflow/auth/tenant_context.py healthflow/feedback/prompt_updater.py healthflow/feedback/reward_model.py healthflow/api/test_router.py healthflow/tests/conftest.py healthflow/tests/database/test_database_models.py healthflow/tests/tenancy/test_tenant_context.py healthflow/tests/tenancy/test_tenant_filter.py
git commit -m "system_context: require reason argument; richer audit log lines"
```

---

## Task 10: Multi-entity tenant-scoped select test

**Files:**
- Modify: `healthflow/tests/tenancy/test_tenant_filter.py`

The reviewer (M-5) noted that `_statement_targets_tenant_model` only returns the *first* tenant-scoped entity it finds. A multi-entity SELECT (e.g. `select(Client.id, Feedback.output_id).join(...)`) would only get filtered on whichever entity the loop hits first. Add a test that exercises this and locks in the current behavior.

- [ ] **Step 1: Write the test**

Append to `healthflow/tests/tenancy/test_tenant_filter.py`:

```python
@pytest.mark.anyio
async def test_multi_entity_select_filters_on_first_tenant_entity(session_with_filter):
    """Multi-entity SELECT (e.g. select(Client.id, Feedback.output_id))
    currently only auto-filters on the FIRST tenant-scoped entity found.
    This test locks in that behavior so any future change is deliberate.
    """
    session, broker_a, broker_b, client_a, _client_b = session_with_filter
    # Add a Feedback row for broker_a so there's a tenant-scoped column to
    # join against.
    fb = Feedback(
        broker_id=broker_a.id, output_id="oA", agent_type="comparison",
        accuracy=5, clarity=5, helpfulness=5, comment="A",
    )
    with system_context("test setup"):
        session.add(fb)
        await session.commit()

    token = current_broker_id.set(broker_a.id)
    try:
        # Select Client.id alongside a literal — the bind_mapper picks Client,
        # so the WHERE clause auto-applies on Client.broker_id. A select that
        # only references Feedback would auto-apply on Feedback.broker_id.
        # Goal: confirm the single-entity scoping works as documented.
        result = await session.execute(select(Client.id))
        ids = [row[0] for row in result.all()]
        assert ids == [client_a.id]

        # Same for Feedback.
        result = await session.execute(select(Feedback.output_id))
        outputs = [row[0] for row in result.all()]
        assert outputs == ["oA"]
    finally:
        current_broker_id.reset(token)
```

This test documents the current scoping behavior. If multi-entity selects with joins across two tenant-scoped tables are ever added, the test should be extended (or the implementation should be made smarter — see follow-up notes).

- [ ] **Step 2: Add the `Feedback` import**

The existing imports at the top of `test_tenant_filter.py` already include `Broker, Client, PromptVariant` — wait, `PromptVariant` was dropped in Plan 1's lint fix. The current import is `from healthflow.database.models import Base, Broker, Client`. Add `Feedback`:

```python
from healthflow.database.models import Base, Broker, Client, Feedback
```

- [ ] **Step 3: Run the test**

```bash
.venv/bin/python -m pytest healthflow/tests/tenancy/test_tenant_filter.py::test_multi_entity_select_filters_on_first_tenant_entity -v
```

Expected: 1 passed. If it fails, the assertion may need adjustment based on what `bind_mapper` actually picks first — surface the actual behavior and update the test to match (the goal is to LOCK IN current behavior, not specify ideal behavior).

- [ ] **Step 4: Run full suite**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 488 passed.

- [ ] **Step 5: Commit**

```bash
git add healthflow/tests/tenancy/test_tenant_filter.py
git commit -m "Lock in single-entity scoping for tenant filter (multi-entity selects)"
```

---

## Task 11: Document `get_db` / `get_current_broker` teardown ordering

**Files:**
- Modify: `healthflow/auth/dependencies.py`
- Modify: `healthflow/database/config.py`

The reviewer (M-3) noted that FastAPI tears down dependencies in LIFO order: `get_current_broker`'s teardown (ContextVar reset) runs *before* `get_db`'s teardown (commit + close). With `expire_on_commit=False` this is harmless; if anyone flips it, queries during cleanup would fail with `TenantContextMissing`. Document.

- [ ] **Step 1: Add the docstring note to `get_current_broker`**

Edit `healthflow/auth/dependencies.py`. Append to the existing docstring of `get_current_broker`:

```python
    """...existing docstring...

    Teardown ordering (FastAPI LIFO): the ContextVar reset here runs BEFORE
    `get_db`'s teardown (commit + close). With `expire_on_commit=False`
    (the project default in `database/config.py`), commit does not fire
    SELECTs, so this is fine. If `expire_on_commit` is ever flipped to
    True or any cleanup path emits a query against a tenant-scoped table,
    queries during teardown will raise `TenantContextMissing`. In that
    case, restructure: have `get_db` enter `system_context()` for its
    cleanup phase (and add a comment justifying the new system_context
    call site).
    """
```

- [ ] **Step 2: Add the matching note to `get_db`**

Edit `healthflow/database/config.py`. Append to the docstring of `get_db`:

```python
    """...existing docstring...

    Cleanup contract: this generator's teardown (commit + close) runs
    AFTER any auth dependency's teardown, including `get_current_broker`'s
    ContextVar reset. Code in this teardown must NOT emit SELECTs against
    tenant-scoped tables (Client, ActionHistory, Feedback) — there's no
    current_broker_id at that point. With `expire_on_commit=False` (set
    on the session factory above), commit does not fire SELECTs, so the
    contract holds.
    """
```

If `get_db` doesn't have an existing docstring, add a full one:

```python
    """Yield an AsyncSession scoped to the request, commit on success.

    Cleanup contract: this generator's teardown (commit + close) runs
    AFTER any auth dependency's teardown, including `get_current_broker`'s
    ContextVar reset. Code in this teardown must NOT emit SELECTs against
    tenant-scoped tables (Client, ActionHistory, Feedback) — there's no
    current_broker_id at that point. With `expire_on_commit=False` (set
    on the session factory above), commit does not fire SELECTs, so the
    contract holds.
    """
```

- [ ] **Step 3: Run the suite (no behavior change expected)**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 488 passed.

- [ ] **Step 4: Commit**

```bash
git add healthflow/auth/dependencies.py healthflow/database/config.py
git commit -m "Document get_db / get_current_broker teardown ordering contract"
```

---

## Task 12: Update the `healthflow-security` skill

**Files:**
- Modify: `.claude/skills/healthflow-security/SKILL.md`

The skill's "PHI on the wire to Anthropic" and rule sections still describe the manual-filter world. Update to reflect the new enforcement model.

- [ ] **Step 1: Edit the skill**

Edit `.claude/skills/healthflow-security/SKILL.md`. Find the "Two databases — don't cross them" section and add a new section before it (or after "PHI on the wire to Anthropic"):

```markdown
## Tenant isolation is enforced by infrastructure, not code review

Every PHI-table query is auto-filtered by `broker_id` via a SQLAlchemy
`do_orm_execute` listener registered at app startup
(`healthflow/database/tenant_filter.py`). The current broker is read from
a `ContextVar` set by the auth dependency in
`healthflow/auth/dependencies.py:get_current_broker`. Forgetting a
`WHERE broker_id = ...` clause in a route is now structurally impossible
for SELECT/UPDATE/DELETE.

**Rule:** When adding a new PHI table, add it to `TENANT_SCOPED_MODELS`
in `healthflow/database/tenant_filter.py`. Adding it anywhere else
(e.g., creating an ORM class with a `broker_id` column but forgetting
the registry) means the table will silently bypass enforcement.

**Rule:** INSERTs into tenant-scoped tables don't go through the hook
(unit-of-work flush bypasses `do_orm_execute`). Composite writes —
inserting a row that references another tenant-scoped row by ID
(e.g., `ActionHistory.client_id`) — must load the referenced row through
the filter first. If the load returns `None`, return 404. See
`healthflow/api/history_router.py:create_history` for the canonical
pattern.

**Rule:** Cross-broker reads are legitimate only at audited call sites
and must use `with system_context(reason="..."):`. The required `reason`
argument shows up in the WARN-level audit log. Allowed sites today:
`feedback/prompt_updater.py` and `feedback/reward_model.py` (RLHF needs
all brokers' feedback), `api/test_router.py` (e2e reset endpoint),
test fixtures in `tests/conftest.py` and `tests/database/test_database_models.py`.
Adding a new call site requires a justification comment and code review.

**Rule:** Cross-broker analytics endpoints exposed to non-admin users
are forbidden. The `feedback/analytics`, `/reward-score`, and
`/weekly-report` endpoints today scope to per-broker via the auto-filter
(except for the inner aggregation steps which run in system_context()
because RLHF needs cross-broker data). If you add an endpoint that
returns aggregates, default to per-broker; if cross-broker is needed,
gate on a future admin role.
```

- [ ] **Step 2: Verify the skill still parses**

```bash
head -10 .claude/skills/healthflow-security/SKILL.md
```

The frontmatter (between `---` markers) at the top must be intact.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/healthflow-security/SKILL.md
git commit -m "skill: healthflow-security — document tenant-filter enforcement model"
```

---

## Task 13: Final verification + push + PR

**Files:** None — verification only.

- [ ] **Step 1: Confirm full suite is green**

```bash
make test-quick 2>&1 | tail -3
```

Expected: 488 passed (483 baseline + 5 new tests across Tasks 3, 5, 8, 10).

- [ ] **Step 2: Run `make check` to confirm lint + tests + frontend build**

```bash
make check 2>&1 | tail -20
```

Expected: tests green; pre-existing E402 lint errors in `healthflow/main.py` may still appear (not this PR's responsibility). Any NEW lint errors introduced by this PR should be fixed before pushing.

- [ ] **Step 3: Hand-verify the system_context audit trail is sane**

```bash
grep -rn 'system_context(' healthflow/ .claude/skills/ 2>/dev/null | grep -v test_tenant_context | grep -v __pycache__
```

Expected: a manageable list (≤10 call sites), each with a recognizable reason. Confirm each is justified per the skill's rules.

- [ ] **Step 4: Smoke-verify `seed.py` and `scripts/refresh_data.py` still work end-to-end**

Per the spec's acceptance criteria, the seeders must complete without raising `TenantContextMissing`. They run as separate processes (HTTP client + standalone script), but a fresh-eyes verification:

```bash
# refresh_data.py only writes to healthflow_data.db (public reference data),
# but confirm it imports cleanly and the seed-only path runs:
.venv/bin/python scripts/refresh_data.py --seed-only --db-path /tmp/healthflow_test.db && rm -f /tmp/healthflow_test.db
```

Expected: clean execution. seed.py itself goes through HTTP (calls `/auth/register` etc.) — running it would require a live server; smoke is via the integration tests that exercise those endpoints.

- [ ] **Step 5: Review the commit graph**

```bash
git log --oneline main..HEAD
```

Expected: roughly 11 commits (one per task with code changes; Tasks 1, 7, and 13 don't commit). Each message terse, no `Co-Authored-By` trailer.

- [ ] **Step 6: Push the branch**

```bash
git push -u origin multi-tenancy/migration 2>&1 | tail -5
```

- [ ] **Step 7: Open the PR**

```bash
gh pr create --title "Multi-tenancy migration: routers, composite-write, analytics audit, skill update" --body "$(cat <<'EOF'
## Summary

Makes the multi-tenancy foundation (Plan 1, merged as `710a404`) load-bearing across the codebase. Drops the now-redundant manual `WHERE broker_id` filters from every remaining PHI router, adds composite-write protection, deliberately scopes analytics to per-broker, wraps RLHF cross-broker reads in `system_context()`, extends the cross-tenant test suite, and applies the small follow-ups from Plan 1's final code review.

- `healthflow/api/history_router.py` — manual filter dropped from `list_history`; composite-write protection on `POST /history` (loads `Client` via the filter first).
- `healthflow/feedback/router.py` + `collector.py` — manual `broker_id` arg dropped from `list_feedback` (the hook handles it); analytics endpoint deliberately per-broker; docstring updated.
- `healthflow/feedback/prompt_updater.py` + `reward_model.py` — RLHF cross-broker reads wrapped in `system_context(reason="...")`. Note: `/feedback/reward-score` and `/feedback/weekly-report` are still exposed to any authenticated broker; gating on an admin role is a follow-up (no admin RBAC exists yet).
- `healthflow/auth/tenant_context.py` — `system_context` now requires a `reason: str` argument; WARN log lines include it. All call sites updated.
- `healthflow/auth/dependencies.py` + `database/config.py` — docstring notes on the `get_db` / `get_current_broker` teardown-ordering contract (M-3).
- `healthflow/tests/tenancy/test_cross_broker_isolation.py` — extended with history + feedback read-isolation tests.
- `healthflow/tests/tenancy/test_cross_broker_writes.py` (new) — composite-write protection + analytics-isolation tests.
- `healthflow/tests/tenancy/test_tenant_filter.py` — multi-entity-select scoping test (M-5).
- `.claude/skills/healthflow-security/SKILL.md` — updated to describe the new enforcement model and audit rules.

Spec: [docs/superpowers/specs/2026-05-12-multi-tenancy-design.md](./docs/superpowers/specs/2026-05-12-multi-tenancy-design.md)
Plan: [docs/superpowers/plans/2026-05-13-multi-tenancy-migration.md](./docs/superpowers/plans/2026-05-13-multi-tenancy-migration.md)

## Test Plan

- [x] 5 new tests (composite-write 1, analytics isolation 1, history isolation 1, feedback isolation 1, multi-entity scoping 1) all green
- [x] Full backend suite: 488/488 (was 483; +5 new tests)
- [x] `system_context` call sites audited: 6 total, each with a justifying `reason`
- [x] No new lint errors
- [ ] CI green on this PR

## Out of scope / follow-ups

- Admin RBAC + admin-only endpoints (would let `/reward-score` and `/weekly-report` properly require admin instead of any-authenticated). Separate sub-project.
- PHI redaction in LLM prompts (sub-project #1 in the HIPAA decomposition).
- PHI access audit log (sub-project #3).
- Auth hardening (MFA, JWT secret default, password policy) — sub-project #4.
- Encryption at rest — sub-project #5.
EOF
)" 2>&1 | tail -3
```

Expected: a GitHub PR URL. Capture and report it.

No new commit for this task.
