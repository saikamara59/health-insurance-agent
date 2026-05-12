"""Unit tests for the request-scoped tenant context."""
import asyncio
import logging
import uuid

import pytest

from healthflow.auth.tenant_context import (
    TenantContextMissing,
    current_broker_id,
    require_current_broker,
    system_context,
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
