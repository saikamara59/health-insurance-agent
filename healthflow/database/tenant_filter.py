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
import re

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

    Idempotent: calling repeatedly is a no-op. The listener attaches to the
    global Session class (via AsyncSession.sync_session_class), so registering
    once is enough — calls from test fixtures and production startup both
    resolve to the same class.
    """
    target = factory.class_.sync_session_class
    if not event.contains(target, "do_orm_execute", _on_do_orm_execute):
        event.listen(target, "do_orm_execute", _on_do_orm_execute)


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
    """Register before_execute listener on the engine for raw-SQL protection.

    Idempotent per engine: calling repeatedly on the same engine is a no-op.
    """
    target = engine.sync_engine
    if not event.contains(target, "before_execute", _on_before_execute):
        event.listen(target, "before_execute", _on_before_execute)
