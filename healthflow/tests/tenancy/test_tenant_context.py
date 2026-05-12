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
