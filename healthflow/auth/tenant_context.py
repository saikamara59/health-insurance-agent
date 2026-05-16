"""Request-scoped tenant identity for HealthFlow.

A `ContextVar` holds the current broker's UUID for the life of an HTTP
request (set by the FastAPI auth dependency, reset on teardown). Code
that touches PHI tables uses `require_current_broker()` to read it;
attempting to read when unset raises `TenantContextMissing`.

This module knows nothing about SQLAlchemy. The actual filter
enforcement lives in `healthflow.database.tenant_filter`.
"""
import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


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


logger = logging.getLogger(__name__)

_in_system_context: ContextVar[bool] = ContextVar("_in_system_context", default=False)

current_endpoint: ContextVar[str | None] = ContextVar("current_endpoint", default=None)


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
