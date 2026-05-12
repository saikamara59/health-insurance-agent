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

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.tenant_context import (
    TenantContextMissing,
    _in_system_context,
    current_broker_id,
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
    event.listen(factory.class_.sync_session_class, "do_orm_execute", _on_do_orm_execute)
