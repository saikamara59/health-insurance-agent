import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import get_current_broker
from healthflow.database.config import get_db
from healthflow.database.models import ActionHistory, Broker, Client
from healthflow.models.schemas import ActionHistoryCreate, ActionHistoryResponse

history_router = APIRouter(prefix="/history", tags=["history"])


@history_router.get("", response_model=list[ActionHistoryResponse])
async def list_history(
    action_type: str | None = Query(None),
    client_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """List action history for the current broker."""
    stmt = (
        select(ActionHistory)
        .where(ActionHistory.broker_id == broker.id)
        .order_by(ActionHistory.created_at.desc())
        .limit(limit)
    )
    if action_type:
        stmt = stmt.where(ActionHistory.action_type == action_type)
    if client_id:
        stmt = stmt.where(ActionHistory.client_id == client_id)

    result = await db.execute(stmt)
    actions = result.scalars().all()

    # Fetch client names
    client_ids = {a.client_id for a in actions}
    client_names = {}
    if client_ids:
        clients_result = await db.execute(
            select(Client.id, Client.full_name).where(Client.id.in_(client_ids))
        )
        client_names = {row.id: row.full_name for row in clients_result}

    return [
        ActionHistoryResponse(
            id=str(a.id),
            broker_id=str(a.broker_id),
            client_id=str(a.client_id),
            action_type=a.action_type,
            request_data=a.request_data or {},
            response_summary=a.response_summary or {},
            created_at=a.created_at.isoformat(),
            client_name=client_names.get(a.client_id),
        )
        for a in actions
    ]


@history_router.post("", response_model=ActionHistoryResponse, status_code=201)
async def create_history(
    entry: ActionHistoryCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Record an action in the history."""
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

    # Get client name
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
