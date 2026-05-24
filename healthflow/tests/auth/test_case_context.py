"""Tests for the case_id ContextVar + parse helper + middleware."""
import asyncio
import logging
import uuid

import pytest

from healthflow.auth.case_context import case_id, parse_case_id_header


# ── parse_case_id_header ────────────────────────────────────────────────────


def test_parse_returns_fresh_uuid_when_header_missing():
    a = parse_case_id_header(None)
    b = parse_case_id_header(None)
    assert isinstance(a, uuid.UUID)
    assert isinstance(b, uuid.UUID)
    assert a != b


def test_parse_returns_fresh_uuid_when_header_empty():
    assert isinstance(parse_case_id_header(""), uuid.UUID)


def test_parse_accepts_valid_uuid():
    given = uuid.uuid4()
    parsed = parse_case_id_header(str(given))
    assert parsed == given


def test_parse_logs_warning_and_falls_back_on_invalid_uuid(caplog):
    with caplog.at_level(logging.WARNING, logger="healthflow.auth.case_context"):
        result = parse_case_id_header("not-a-uuid")
    assert isinstance(result, uuid.UUID)
    assert any("Invalid X-Case-Id header" in r.getMessage() for r in caplog.records)


# ── ContextVar propagation across asyncio.create_task ───────────────────────


@pytest.mark.asyncio
async def test_case_id_propagates_into_create_task():
    """PEP 567 — ContextVars are copied into asyncio.create_task by default.

    HealthFlow agents fan out work via asyncio.create_task; this test pins the
    behavior so a future asyncio change (or accidental sync_to_async wrapper)
    breaks loudly rather than silently dropping case_id.
    """
    parent = uuid.uuid4()
    token = case_id.set(parent)
    try:
        seen: list[uuid.UUID | None] = []

        async def inner():
            seen.append(case_id.get())

        await asyncio.create_task(inner())
        assert seen == [parent]
    finally:
        case_id.reset(token)


@pytest.mark.asyncio
async def test_case_id_propagates_into_asyncio_gather():
    parent = uuid.uuid4()
    token = case_id.set(parent)
    try:
        async def inner():
            return case_id.get()

        results = await asyncio.gather(inner(), inner(), inner())
        assert results == [parent, parent, parent]
    finally:
        case_id.reset(token)


@pytest.mark.asyncio
async def test_case_id_isolation_across_concurrent_outer_scopes():
    """Two concurrent tasks each set their own case_id; they MUST NOT see each
    other's. This is the request-isolation property we rely on under load."""
    a = uuid.uuid4()
    b = uuid.uuid4()
    seen_a: list[uuid.UUID | None] = []
    seen_b: list[uuid.UUID | None] = []

    async def outer(value, seen):
        token = case_id.set(value)
        try:
            await asyncio.sleep(0)  # yield so the other task can run
            seen.append(case_id.get())
        finally:
            case_id.reset(token)

    await asyncio.gather(outer(a, seen_a), outer(b, seen_b))
    assert seen_a == [a]
    assert seen_b == [b]


# ── CaseContextMiddleware end-to-end via the live app ───────────────────────


@pytest.mark.asyncio
async def test_middleware_uses_supplied_header(client):
    given = uuid.uuid4()
    resp = await client.get("/health", headers={"X-Case-Id": str(given)})
    assert resp.status_code == 200
    assert resp.headers.get("x-case-id") == str(given)


@pytest.mark.asyncio
async def test_middleware_generates_fresh_when_header_missing(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    echoed = resp.headers.get("x-case-id")
    assert echoed
    # Round-trip uuid.UUID() — proves it's a valid UUID string.
    assert uuid.UUID(echoed)


@pytest.mark.asyncio
async def test_middleware_generates_fresh_when_header_invalid(client):
    resp = await client.get("/health", headers={"X-Case-Id": "garbage"})
    assert resp.status_code == 200
    echoed = resp.headers.get("x-case-id")
    assert echoed
    assert echoed != "garbage"
    assert uuid.UUID(echoed)
