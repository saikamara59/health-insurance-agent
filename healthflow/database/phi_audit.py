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


def install_phi_audit(factory: async_sessionmaker) -> None:
    """Register the PHI audit listeners on this session factory.

    Idempotent. MUST be called AFTER install_tenant_filter — the audit
    listener invokes the statement and needs to see it already tenant-scoped.
    """
    target = factory.class_.sync_session_class
    if not event.contains(target, "do_orm_execute", _on_do_orm_execute_audit):
        event.listen(target, "do_orm_execute", _on_do_orm_execute_audit)
