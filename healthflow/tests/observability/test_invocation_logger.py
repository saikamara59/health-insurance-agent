"""Tests for the InvocationLogger context manager + AgentInvocationLog row writes."""
import logging
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from healthflow.auth.case_context import case_id
from healthflow.auth.tenant_context import current_broker_id, current_endpoint
from healthflow.database.models import AgentInvocationLog, Base
from healthflow.logs.invocation import InvocationLogger, _sync_url


# ── _sync_url helper ────────────────────────────────────────────────────────


def test_sync_url_converts_aiosqlite():
    assert _sync_url("sqlite+aiosqlite:///healthflow.db") == "sqlite:///healthflow.db"


def test_sync_url_converts_asyncpg_to_psycopg():
    assert _sync_url("postgresql+asyncpg://user:pw@host/db") == "postgresql+psycopg://user:pw@host/db"


def test_sync_url_passes_through_unknown():
    assert _sync_url("mysql+aiomysql://x") == "mysql+aiomysql://x"


# ── InvocationLogger fixture: pristine on-disk sqlite per test ──────────────


@pytest.fixture
def inv_engine(tmp_path):
    """Build a sync sqlite engine + create schema."""
    db_path = tmp_path / "invlog.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def inv_logger(inv_engine, monkeypatch):
    """A logger wired to the per-test engine."""
    logger = InvocationLogger()
    # Force the engine to the test one (bypasses lazy DATABASE_URL lookup).
    monkeypatch.setattr(logger, "_engine", inv_engine)
    return logger


def _read_all_rows(engine):
    with Session(engine) as s:
        return list(s.execute(select(AgentInvocationLog)).scalars().all())


# ── Happy path: row written, fields populated ──────────────────────────────


def test_invocation_writes_one_row_on_success(inv_logger, inv_engine):
    cid = uuid.uuid4()
    bid = uuid.uuid4()
    case_token = case_id.set(cid)
    broker_token = current_broker_id.set(bid)
    endpoint_token = current_endpoint.set("/temporal/plan")
    try:
        with inv_logger(agent="temporal_awareness", event_type="plan_generated", model="claude-sonnet-4-6") as inv:
            inv.details = {"event": "sep_job_loss"}
    finally:
        case_id.reset(case_token)
        current_broker_id.reset(broker_token)
        current_endpoint.reset(endpoint_token)

    rows = _read_all_rows(inv_engine)
    assert len(rows) == 1
    r = rows[0]
    assert r.case_id == cid
    assert r.broker_id == bid
    assert r.endpoint == "/temporal/plan"
    assert r.agent == "temporal_awareness"
    assert r.event_type == "plan_generated"
    assert r.model_used == "claude-sonnet-4-6"
    assert r.details == {"event": "sep_job_loss"}
    assert r.error is None
    assert r.duration_ms is not None and r.duration_ms >= 0


def test_invocation_records_endpoint_unknown_when_unset(inv_logger, inv_engine):
    # Don't set current_endpoint — record should land "unknown".
    with inv_logger(agent="comparison", event_type="recommendation_generated") as inv:
        inv.details = {"length": 42}
    rows = _read_all_rows(inv_engine)
    assert len(rows) == 1
    assert rows[0].endpoint == "unknown"


# ── Exception path: row STILL written with error field ─────────────────────


def test_invocation_writes_row_on_exception_with_error_field(inv_logger, inv_engine):
    with pytest.raises(RuntimeError, match="boom"):
        with inv_logger(agent="appeal", event_type="recommendation_generated"):
            raise RuntimeError("boom")

    rows = _read_all_rows(inv_engine)
    assert len(rows) == 1
    r = rows[0]
    assert r.agent == "appeal"
    assert r.error is not None
    assert "RuntimeError" in r.error
    assert "boom" in r.error
    assert r.duration_ms is not None


def test_invocation_truncates_long_error_messages(inv_logger, inv_engine):
    long_msg = "x" * 1000
    with pytest.raises(ValueError):
        with inv_logger(agent="harness", event_type="input_validated"):
            raise ValueError(long_msg)
    rows = _read_all_rows(inv_engine)
    assert len(rows) == 1
    assert len(rows[0].error) <= 512


# ── DB-failure fallback: text-logger gets called, no exception propagates ──


def test_db_write_failure_falls_back_to_text_logger_and_does_not_raise(monkeypatch, caplog):
    """Simulated DB write failure should not propagate; the text AuditLogger
    must receive an `agent_invocation_log_write_failed` entry with the row data."""
    logger = InvocationLogger()
    # Force _ensure_engine to raise — simulates a DB outage / config issue.
    monkeypatch.setattr(
        logger,
        "_ensure_engine",
        lambda: (_ for _ in ()).throw(RuntimeError("simulated DB outage")),
    )

    with caplog.at_level(logging.INFO, logger="healthflow.audit"):
        # The wrapped body completes successfully — the failure is in our write.
        with logger(agent="comparison", event_type="recommendation_generated") as inv:
            inv.details = {"length": 5}

    # Read the AuditLogger text-log records that came through.
    import json
    audit_records = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.getMessage().startswith("{")
    ]
    fallbacks = [
        r for r in audit_records
        if r.get("event_type") == "agent_invocation_log_write_failed"
    ]
    assert len(fallbacks) == 1
    details = fallbacks[0]["details"]
    assert details["agent"] == "comparison"
    assert details["event_type"] == "recommendation_generated"
    assert details["details"] == {"length": 5}
    assert "simulated DB outage" in details["fallback_reason"]


def test_exception_in_body_still_falls_back_cleanly_on_db_failure(monkeypatch):
    """Both the wrapped body AND the DB write fail. The wrapped exception must
    propagate (it's the real failure); the DB-write failure becomes a text-log
    fallback. Neither swallows the other."""
    logger = InvocationLogger()
    monkeypatch.setattr(
        logger,
        "_ensure_engine",
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    with pytest.raises(ValueError, match="agent boom"):
        with logger(agent="network", event_type="recommendation_generated"):
            raise ValueError("agent boom")


# ── ContextVar values captured at __enter__, not at __exit__ ───────────────


def test_invocation_captures_context_vars_at_enter_not_exit(inv_logger, inv_engine):
    """Even if a later code path resets the ContextVars before the body
    finishes, the row records the values that were live at __enter__."""
    early_case = uuid.uuid4()
    case_token = case_id.set(early_case)
    try:
        with inv_logger(agent="comparison", event_type="recommendation_generated") as inv:
            inv.details = {"length": 1}
            # Reset case_id MID-body. The recorded row should still show
            # `early_case` because the value was captured at __enter__.
            case_id.reset(case_token)
            case_token = case_id.set(uuid.uuid4())
    finally:
        case_id.reset(case_token)

    rows = _read_all_rows(inv_engine)
    assert len(rows) == 1
    assert rows[0].case_id == early_case
