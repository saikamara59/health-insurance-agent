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
