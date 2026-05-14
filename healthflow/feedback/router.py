from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import get_current_broker
from healthflow.database.config import get_db
from healthflow.database.models import Broker
from healthflow.feedback.collector import FeedbackCollector
from healthflow.feedback.reward_model import RewardModel
from healthflow.models.schemas import (
    FeedbackAnalytics,
    FeedbackCreate,
    FeedbackResponse,
    WeeklyReport,
)

feedback_router = APIRouter(prefix="/feedback", tags=["feedback"])

collector = FeedbackCollector()
reward_model = RewardModel()


@feedback_router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on an agent output."""
    fb = await collector.submit(
        db=db,
        broker_id=broker.id,
        output_id=body.output_id,
        agent_type=body.agent_type,
        accuracy=body.accuracy,
        clarity=body.clarity,
        helpfulness=body.helpfulness,
        comment=body.comment,
    )
    return FeedbackResponse(
        id=str(fb.id),
        broker_id=str(fb.broker_id),
        output_id=fb.output_id,
        agent_type=fb.agent_type,
        accuracy=fb.accuracy,
        clarity=fb.clarity,
        helpfulness=fb.helpfulness,
        comment=fb.comment,
        created_at=fb.created_at.isoformat(),
    )


@feedback_router.get("", response_model=list[FeedbackResponse])
async def list_feedback(
    agent_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """List feedback for the current broker."""
    items = await collector.list_feedback(
        db=db,
        agent_type=agent_type,
        limit=limit,
    )
    return [
        FeedbackResponse(
            id=str(fb.id),
            broker_id=str(fb.broker_id),
            output_id=fb.output_id,
            agent_type=fb.agent_type,
            accuracy=fb.accuracy,
            clarity=fb.clarity,
            helpfulness=fb.helpfulness,
            comment=fb.comment,
            created_at=fb.created_at.isoformat(),
        )
        for fb in items
    ]


@feedback_router.get("/analytics", response_model=FeedbackAnalytics)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated feedback analytics per agent type."""
    return await collector.get_analytics(db=db, days=days)


@feedback_router.post("/reward-score", response_model=WeeklyReport)
async def trigger_reward_score(
    days: int = Query(7, ge=1, le=365),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Trigger the reward model scoring pipeline."""
    return await reward_model.score_outputs(db=db, days=days)


@feedback_router.get("/weekly-report", response_model=WeeklyReport)
async def get_weekly_report(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Get the weekly feedback summary report."""
    return await reward_model.score_outputs(db=db, days=7)
