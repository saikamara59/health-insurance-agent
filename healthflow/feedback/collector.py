import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Feedback
from healthflow.models.schemas import AgentFeedbackStats


class FeedbackCollector:
    """Handles feedback CRUD operations."""

    async def submit(
        self,
        db: AsyncSession,
        broker_id: uuid.UUID,
        output_id: str,
        agent_type: str,
        accuracy: int,
        clarity: int,
        helpfulness: int,
        comment: str = "",
    ) -> Feedback:
        """Submit feedback for an agent output."""
        feedback = Feedback(
            id=uuid.uuid4(),
            broker_id=broker_id,
            output_id=output_id,
            agent_type=agent_type,
            accuracy=accuracy,
            clarity=clarity,
            helpfulness=helpfulness,
            comment=comment,
        )
        db.add(feedback)
        await db.flush()
        await db.refresh(feedback)
        return feedback

    async def list_feedback(
        self,
        db: AsyncSession,
        broker_id: uuid.UUID,
        agent_type: str | None = None,
        limit: int = 50,
    ) -> list[Feedback]:
        """List feedback for a broker, optionally filtered by agent_type."""
        stmt = (
            select(Feedback)
            .where(Feedback.broker_id == broker_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        if agent_type:
            stmt = stmt.where(Feedback.agent_type == agent_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_analytics(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Return per-agent feedback averages for the given period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                Feedback.agent_type,
                func.count(Feedback.id).label("total_feedback"),
                func.avg(Feedback.accuracy).label("avg_accuracy"),
                func.avg(Feedback.clarity).label("avg_clarity"),
                func.avg(Feedback.helpfulness).label("avg_helpfulness"),
            )
            .where(Feedback.created_at >= cutoff)
            .group_by(Feedback.agent_type)
        )
        result = await db.execute(stmt)
        rows = result.all()

        agents = []
        total_feedback = 0
        weighted_sum = 0.0
        for row in rows:
            avg_acc = float(row.avg_accuracy or 0)
            avg_cla = float(row.avg_clarity or 0)
            avg_hlp = float(row.avg_helpfulness or 0)
            combined = round((avg_acc + avg_cla + avg_hlp) / 3, 2)
            count = int(row.total_feedback)
            total_feedback += count
            weighted_sum += combined * count
            agents.append(
                AgentFeedbackStats(
                    agent_type=row.agent_type,
                    total_feedback=count,
                    avg_accuracy=round(avg_acc, 2),
                    avg_clarity=round(avg_cla, 2),
                    avg_helpfulness=round(avg_hlp, 2),
                    combined_avg=combined,
                )
            )

        overall_avg = round(weighted_sum / total_feedback, 2) if total_feedback else 0.0

        return {
            "period_days": days,
            "agents": agents,
            "overall_avg": overall_avg,
            "total_feedback": total_feedback,
        }
