import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.tenant_context import system_context
from healthflow.database.models import ActionHistory, Feedback, PromptVariant


class PromptUpdater:
    """Generates improved prompts from top-rated outputs and manages A/B variants."""

    async def generate_few_shot(
        self,
        db: AsyncSession,
        agent_type: str,
        top_n: int = 3,
    ) -> str:
        """Query top-rated outputs from action_history and format as few-shot examples.

        Finds the output_ids with the highest average feedback scores, then
        pulls their request_data and response_summary from action_history to
        build few-shot examples.
        """
        # RLHF aggregates feedback across all brokers to improve the
        # system-wide prompt. Cross-broker access is intentional;
        # bypasses the per-tenant filter for this read.
        with system_context():  # TASK-9: add reason="RLHF prompt update: cross-broker feedback aggregation"
            from sqlalchemy import func

            # Find top-rated output_ids for this agent type
            top_stmt = (
                select(
                    Feedback.output_id,
                    func.avg(Feedback.accuracy).label("avg_acc"),
                    func.avg(Feedback.clarity).label("avg_cla"),
                    func.avg(Feedback.helpfulness).label("avg_hlp"),
                )
                .where(Feedback.agent_type == agent_type)
                .group_by(Feedback.output_id)
                .order_by(
                    (func.avg(Feedback.accuracy) + func.avg(Feedback.clarity) + func.avg(Feedback.helpfulness)).desc()
                )
                .limit(top_n)
            )
            result = await db.execute(top_stmt)
            top_rows = result.all()

            if not top_rows:
                return ""

            output_ids = [row.output_id for row in top_rows]

            # Try to fetch corresponding action_history entries
            # output_id may be a UUID string matching action_history.id
            history_stmt = select(ActionHistory).where(
                ActionHistory.action_type == agent_type
            )
            history_result = await db.execute(history_stmt)
            history_rows = history_result.scalars().all()

            # Build a lookup by string id
            history_by_id = {str(h.id): h for h in history_rows}

            examples = []
            for oid in output_ids:
                h = history_by_id.get(oid)
                if h:
                    examples.append(
                        f"### Example\n"
                        f"**Input:** {h.request_data}\n"
                        f"**Output:** {h.response_summary}\n"
                    )

            if not examples:
                # Fallback: just note the top output IDs
                return (
                    f"Use high-quality outputs as reference for {agent_type} agent.\n"
                    f"Top-rated output IDs: {', '.join(output_ids)}"
                )

            header = f"Here are examples of high-quality {agent_type} outputs:\n\n"
            return header + "\n".join(examples)

    async def create_variant(
        self,
        db: AsyncSession,
        agent_type: str,
        prompt_template: str,
        traffic_pct: int = 20,
    ) -> PromptVariant:
        """Insert a new prompt variant and adjust existing traffic percentages.

        The new variant gets `traffic_pct`% of traffic. Existing active variants
        for the same agent_type have their traffic reduced proportionally so the
        total stays at 100%.
        """
        # Fetch existing active variants for this agent type
        existing_stmt = (
            select(PromptVariant)
            .where(PromptVariant.agent_type == agent_type)
            .where(PromptVariant.is_active == True)  # noqa: E712
        )
        result = await db.execute(existing_stmt)
        existing = list(result.scalars().all())

        # Adjust existing variants proportionally
        remaining_pct = 100 - traffic_pct
        if existing:
            total_existing = sum(v.traffic_pct for v in existing)
            for v in existing:
                if total_existing > 0:
                    v.traffic_pct = round(v.traffic_pct / total_existing * remaining_pct)
                else:
                    v.traffic_pct = round(remaining_pct / len(existing))
                db.add(v)

        # Determine variant name
        variant_count = len(existing) + 1
        variant_name = f"updated_v{variant_count}"

        variant = PromptVariant(
            id=uuid.uuid4(),
            agent_type=agent_type,
            variant_name=variant_name,
            prompt_template=prompt_template,
            is_active=True,
            traffic_pct=traffic_pct,
        )
        db.add(variant)
        await db.flush()
        await db.refresh(variant)
        return variant

    async def get_active_variant(
        self,
        db: AsyncSession,
        agent_type: str,
    ) -> PromptVariant | None:
        """Select an active variant using weighted random selection based on traffic_pct."""
        stmt = (
            select(PromptVariant)
            .where(PromptVariant.agent_type == agent_type)
            .where(PromptVariant.is_active == True)  # noqa: E712
        )
        result = await db.execute(stmt)
        variants = list(result.scalars().all())

        if not variants:
            return None

        weights = [v.traffic_pct for v in variants]
        total = sum(weights)
        if total == 0:
            return random.choice(variants)

        chosen = random.choices(variants, weights=weights, k=1)[0]
        return chosen
