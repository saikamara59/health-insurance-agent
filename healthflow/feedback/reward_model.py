from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.tenant_context import system_context
from healthflow.database.models import Feedback
from healthflow.models.schemas import AgentFeedbackStats, WeeklyReport


class RewardModel:
    """Scores agent outputs based on collected feedback."""

    LOW_SCORE_THRESHOLD = 3.0
    TOP_SCORE_THRESHOLD = 4.5

    async def score_outputs(
        self,
        db: AsyncSession,
        agent_type: str | None = None,
        days: int = 7,
    ) -> dict:
        """Score outputs from the last N days, grouped by agent_type.

        Returns a dict matching the WeeklyReport schema.
        """
        # RLHF aggregates feedback across all brokers to improve the
        # system-wide prompt. Cross-broker access is intentional;
        # bypasses the per-tenant filter for this read.
        with system_context():  # TASK-9: add reason="RLHF reward scoring: cross-broker feedback aggregation"
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # --- Per-agent aggregates ---
            agg_stmt = (
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
            if agent_type:
                agg_stmt = agg_stmt.where(Feedback.agent_type == agent_type)

            result = await db.execute(agg_stmt)
            rows = result.all()

            agents: list[AgentFeedbackStats] = []
            total_feedback = 0
            weighted_sum = 0.0
            best_agent: str | None = None
            best_avg = -1.0
            worst_agent: str | None = None
            worst_avg = 6.0

            for row in rows:
                avg_acc = float(row.avg_accuracy or 0)
                avg_cla = float(row.avg_clarity or 0)
                avg_hlp = float(row.avg_helpfulness or 0)
                combined = round((avg_acc + avg_cla + avg_hlp) / 3, 2)
                count = int(row.total_feedback)
                total_feedback += count
                weighted_sum += combined * count

                if combined > best_avg:
                    best_avg = combined
                    best_agent = row.agent_type
                if combined < worst_avg:
                    worst_avg = combined
                    worst_agent = row.agent_type

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

            # --- Per-output scoring for top/bottom identification ---
            per_output_stmt = (
                select(
                    Feedback.output_id,
                    func.avg(Feedback.accuracy).label("avg_accuracy"),
                    func.avg(Feedback.clarity).label("avg_clarity"),
                    func.avg(Feedback.helpfulness).label("avg_helpfulness"),
                )
                .where(Feedback.created_at >= cutoff)
                .group_by(Feedback.output_id)
            )
            if agent_type:
                per_output_stmt = per_output_stmt.where(Feedback.agent_type == agent_type)

            output_result = await db.execute(per_output_stmt)
            output_rows = output_result.all()

            top_output_ids: list[str] = []
            bottom_output_ids: list[str] = []
            low_score_count = 0

            for orow in output_rows:
                o_avg = (
                    float(orow.avg_accuracy or 0)
                    + float(orow.avg_clarity or 0)
                    + float(orow.avg_helpfulness or 0)
                ) / 3
                if o_avg >= self.TOP_SCORE_THRESHOLD:
                    top_output_ids.append(orow.output_id)
                if o_avg < self.LOW_SCORE_THRESHOLD:
                    bottom_output_ids.append(orow.output_id)
                    low_score_count += 1

            return WeeklyReport(
                period_days=days,
                agents=agents,
                overall_avg=overall_avg,
                worst_agent=worst_agent,
                best_agent=best_agent,
                low_score_count=low_score_count,
                top_output_ids=top_output_ids,
                bottom_output_ids=bottom_output_ids,
            ).model_dump()
