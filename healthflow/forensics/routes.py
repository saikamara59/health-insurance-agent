"""FastAPI router: POST /forensics/replay.

Admin-only. tenant_id is the authenticated admin's broker_id — never
read from the request body (prevents spoofing). Returns CaseTimeline
for case/member modes, list[AgentInvocation] for agent mode.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker

from healthflow.auth.dependencies import require_admin
from healthflow.database.config import async_session_factory
from healthflow.database.models import Broker
from healthflow.forensics.replay import (
    replay_agent,
    replay_case,
    replay_member,
)
from healthflow.forensics.schemas import (
    ReplayAgentRequest,
    ReplayCaseRequest,
    ReplayMemberRequest,
)

forensics_router = APIRouter(prefix="/forensics", tags=["forensics"])


class _ReplayRequest(BaseModel):
    """Discriminated union — actual validation happens via the three concrete
    request models, dispatched on `mode`."""
    mode: str


def _get_session_factory() -> async_sessionmaker:
    """Indirection point so tests can monkeypatch."""
    return async_session_factory


@forensics_router.post("/replay")
async def replay(
    body: dict,
    admin: Broker = Depends(require_admin),
) -> Any:
    mode = body.get("mode")
    factory = _get_session_factory()

    if mode == "case":
        req = ReplayCaseRequest.model_validate(body)
        return await replay_case(req.case_id, tenant_id=admin.id, session_factory=factory)

    if mode == "member":
        req = ReplayMemberRequest.model_validate(body)
        return await replay_member(
            req.client_id,
            time_range=(req.from_ts, req.to_ts),
            tenant_id=admin.id,
            session_factory=factory,
        )

    if mode == "agent":
        req = ReplayAgentRequest.model_validate(body)
        return await replay_agent(
            req.agent,
            time_range=(req.from_ts, req.to_ts),
            tenant_id=admin.id,
            session_factory=factory,
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown mode: {mode!r}",
    )
