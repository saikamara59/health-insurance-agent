# RLHF Feedback System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a feedback collection, reward scoring, and prompt improvement loop so brokers can rate AI outputs and the system learns from high-quality examples.

**Architecture:** Feedback table stores 1-5 ratings per agent output. RewardModel scores weekly aggregates. PromptUpdater generates few-shot prompts from top-rated outputs. Simple A/B testing routes traffic between control and updated prompt variants.

**Tech Stack:** Python, FastAPI, SQLAlchemy 2.0, Pydantic, pytest

---

## Task 1: ORM Models (Feedback + PromptVariant)

**File:** `healthflow/database/models.py` (append after `ActionHistory` class, line ~110)

- [ ] Add `Feedback` ORM model to `healthflow/database/models.py` after the `ActionHistory` class (line 110):

```python
class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("brokers.id"), index=True, nullable=False
    )
    output_id: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity: Mapped[int] = mapped_column(Integer, nullable=False)
    helpfulness: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    broker: Mapped["Broker"] = relationship()
```

- [ ] Add `PromptVariant` ORM model immediately after `Feedback`:

```python
class PromptVariant(Base):
    __tablename__ = "prompt_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    traffic_pct: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
```

- [ ] Add `feedbacks` relationship to `Broker` model (after `actions` relationship, line 59):

```python
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="broker", cascade="all, delete-orphan")
```

- [ ] Update the `Feedback.broker` relationship to include `back_populates="feedbacks"`:

```python
    broker: Mapped["Broker"] = relationship(back_populates="feedbacks")
```

- [ ] Add model tests in `healthflow/tests/test_feedback_models.py`:

```python
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker, Feedback, PromptVariant


@pytest.mark.anyio
async def test_create_feedback(db_session: AsyncSession):
    """Feedback row can be created and read back."""
    broker = Broker(
        id=uuid.uuid4(),
        email="fb@test.com",
        hashed_password="hashed",
        full_name="FB Tester",
    )
    db_session.add(broker)
    await db_session.flush()

    fb = Feedback(
        broker_id=broker.id,
        output_id="sess-123",
        agent_type="compare",
        accuracy=5,
        clarity=4,
        helpfulness=3,
        comment="Great comparison",
    )
    db_session.add(fb)
    await db_session.flush()
    await db_session.refresh(fb)

    assert fb.id is not None
    assert fb.accuracy == 5
    assert fb.clarity == 4
    assert fb.helpfulness == 3
    assert fb.agent_type == "compare"
    assert fb.comment == "Great comparison"


@pytest.mark.anyio
async def test_create_prompt_variant(db_session: AsyncSession):
    """PromptVariant row can be created with defaults."""
    pv = PromptVariant(
        agent_type="compare",
        variant_name="control",
        prompt_template="You are a helpful plan comparison agent.",
    )
    db_session.add(pv)
    await db_session.flush()
    await db_session.refresh(pv)

    assert pv.id is not None
    assert pv.is_active is True
    assert pv.traffic_pct == 100
    assert pv.agent_type == "compare"


@pytest.mark.anyio
async def test_feedback_broker_relationship(db_session: AsyncSession):
    """Feedback links back to Broker via relationship."""
    broker = Broker(
        id=uuid.uuid4(),
        email="rel@test.com",
        hashed_password="hashed",
        full_name="Rel Tester",
    )
    db_session.add(broker)
    await db_session.flush()

    fb = Feedback(
        broker_id=broker.id,
        output_id="sess-456",
        agent_type="translate",
        accuracy=3,
        clarity=3,
        helpfulness=3,
    )
    db_session.add(fb)
    await db_session.flush()
    await db_session.refresh(fb)

    assert fb.broker_id == broker.id
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_feedback_models.py -v`

---

## Task 2: Pydantic Schemas

**File:** `healthflow/models/schemas.py` (append after `BrokerProfileUpdate` class, line ~462)

- [ ] Add the `VALID_AGENT_TYPES` constant and all feedback schemas at the end of `healthflow/models/schemas.py`:

```python
# ── Phase 7: RLHF Feedback Schemas ─────────────────────────────────────────


VALID_AGENT_TYPES = {"compare", "calculate", "translate", "appeal", "verify"}


class FeedbackCreate(BaseModel):
    output_id: str = Field(..., description="ID of the agent output being rated")
    agent_type: str = Field(..., description="Agent type: compare/calculate/translate/appeal/verify")
    accuracy: int = Field(..., ge=1, le=5, description="Accuracy rating 1-5")
    clarity: int = Field(..., ge=1, le=5, description="Clarity rating 1-5")
    helpfulness: int = Field(..., ge=1, le=5, description="Helpfulness rating 1-5")
    comment: str = Field(default="", max_length=2000, description="Optional comment")

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        if v not in VALID_AGENT_TYPES:
            raise ValueError(
                f"agent_type must be one of: {', '.join(sorted(VALID_AGENT_TYPES))}"
            )
        return v


class FeedbackResponse(BaseModel):
    id: str
    broker_id: str
    output_id: str
    agent_type: str
    accuracy: int
    clarity: int
    helpfulness: int
    comment: str
    created_at: str

    model_config = {"from_attributes": True}


class AgentFeedbackStats(BaseModel):
    agent_type: str
    total_feedback: int
    avg_accuracy: float
    avg_clarity: float
    avg_helpfulness: float
    combined_avg: float


class FeedbackAnalytics(BaseModel):
    period_days: int
    agents: list[AgentFeedbackStats]
    overall_avg: float
    total_feedback: int


class WeeklyReport(BaseModel):
    period_days: int
    agents: list[AgentFeedbackStats]
    overall_avg: float
    worst_agent: str | None
    best_agent: str | None
    low_score_count: int
    top_output_ids: list[str]
    bottom_output_ids: list[str]
```

- [ ] Add schema validation tests in `healthflow/tests/test_feedback_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from healthflow.models.schemas import FeedbackCreate, FeedbackResponse, AgentFeedbackStats


def test_feedback_create_valid():
    fb = FeedbackCreate(
        output_id="sess-123",
        agent_type="compare",
        accuracy=5,
        clarity=4,
        helpfulness=3,
        comment="Good output",
    )
    assert fb.accuracy == 5
    assert fb.agent_type == "compare"


def test_feedback_create_invalid_rating_too_low():
    with pytest.raises(ValidationError) as exc_info:
        FeedbackCreate(
            output_id="sess-123",
            agent_type="compare",
            accuracy=0,
            clarity=4,
            helpfulness=3,
        )
    assert "greater than or equal to 1" in str(exc_info.value)


def test_feedback_create_invalid_rating_too_high():
    with pytest.raises(ValidationError) as exc_info:
        FeedbackCreate(
            output_id="sess-123",
            agent_type="compare",
            accuracy=6,
            clarity=4,
            helpfulness=3,
        )
    assert "less than or equal to 5" in str(exc_info.value)


def test_feedback_create_invalid_agent_type():
    with pytest.raises(ValidationError) as exc_info:
        FeedbackCreate(
            output_id="sess-123",
            agent_type="invalid_agent",
            accuracy=3,
            clarity=3,
            helpfulness=3,
        )
    assert "agent_type must be one of" in str(exc_info.value)


def test_feedback_create_comment_too_long():
    with pytest.raises(ValidationError):
        FeedbackCreate(
            output_id="sess-123",
            agent_type="compare",
            accuracy=3,
            clarity=3,
            helpfulness=3,
            comment="x" * 2001,
        )


def test_feedback_create_default_comment():
    fb = FeedbackCreate(
        output_id="sess-123",
        agent_type="compare",
        accuracy=3,
        clarity=3,
        helpfulness=3,
    )
    assert fb.comment == ""


def test_agent_feedback_stats():
    stats = AgentFeedbackStats(
        agent_type="compare",
        total_feedback=42,
        avg_accuracy=4.2,
        avg_clarity=3.8,
        avg_helpfulness=4.0,
        combined_avg=4.0,
    )
    assert stats.combined_avg == 4.0
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_feedback_schemas.py -v`

---

## Task 3: Feedback Collector

**Files:** Create `healthflow/feedback/__init__.py` and `healthflow/feedback/collector.py`

- [ ] Create empty `healthflow/feedback/__init__.py`

- [ ] Create `healthflow/feedback/collector.py`:

```python
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
```

- [ ] Create collector tests in `healthflow/tests/test_feedback_collector.py`:

```python
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker
from healthflow.feedback.collector import FeedbackCollector


@pytest.mark.anyio
async def test_submit_feedback(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email="coll@test.com",
        hashed_password="hashed",
        full_name="Coll Tester",
    )
    db_session.add(broker)
    await db_session.flush()

    collector = FeedbackCollector()
    fb = await collector.submit(
        db=db_session,
        broker_id=broker.id,
        output_id="sess-001",
        agent_type="compare",
        accuracy=5,
        clarity=4,
        helpfulness=4,
        comment="Very helpful",
    )

    assert fb.id is not None
    assert fb.accuracy == 5
    assert fb.broker_id == broker.id


@pytest.mark.anyio
async def test_list_feedback(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email="list@test.com",
        hashed_password="hashed",
        full_name="List Tester",
    )
    db_session.add(broker)
    await db_session.flush()

    collector = FeedbackCollector()
    for i in range(3):
        await collector.submit(
            db=db_session,
            broker_id=broker.id,
            output_id=f"sess-{i}",
            agent_type="compare",
            accuracy=3,
            clarity=3,
            helpfulness=3,
        )

    results = await collector.list_feedback(db=db_session, broker_id=broker.id)
    assert len(results) == 3


@pytest.mark.anyio
async def test_list_feedback_filter_by_agent_type(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email="filter@test.com",
        hashed_password="hashed",
        full_name="Filter Tester",
    )
    db_session.add(broker)
    await db_session.flush()

    collector = FeedbackCollector()
    await collector.submit(
        db=db_session, broker_id=broker.id, output_id="s1",
        agent_type="compare", accuracy=4, clarity=4, helpfulness=4,
    )
    await collector.submit(
        db=db_session, broker_id=broker.id, output_id="s2",
        agent_type="translate", accuracy=3, clarity=3, helpfulness=3,
    )

    compare_only = await collector.list_feedback(
        db=db_session, broker_id=broker.id, agent_type="compare"
    )
    assert len(compare_only) == 1
    assert compare_only[0].agent_type == "compare"


@pytest.mark.anyio
async def test_get_analytics(db_session: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email="analytics@test.com",
        hashed_password="hashed",
        full_name="Analytics Tester",
    )
    db_session.add(broker)
    await db_session.flush()

    collector = FeedbackCollector()
    await collector.submit(
        db=db_session, broker_id=broker.id, output_id="a1",
        agent_type="compare", accuracy=5, clarity=5, helpfulness=5,
    )
    await collector.submit(
        db=db_session, broker_id=broker.id, output_id="a2",
        agent_type="compare", accuracy=3, clarity=3, helpfulness=3,
    )

    analytics = await collector.get_analytics(db=db_session, days=30)
    assert analytics["total_feedback"] == 2
    assert len(analytics["agents"]) == 1
    assert analytics["agents"][0].agent_type == "compare"
    assert analytics["agents"][0].avg_accuracy == 4.0
    assert analytics["overall_avg"] == 4.0


@pytest.mark.anyio
async def test_get_analytics_empty(db_session: AsyncSession):
    collector = FeedbackCollector()
    analytics = await collector.get_analytics(db=db_session, days=30)
    assert analytics["total_feedback"] == 0
    assert analytics["agents"] == []
    assert analytics["overall_avg"] == 0.0
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_feedback_collector.py -v`

---

## Task 4: Reward Model

**File:** Create `healthflow/feedback/reward_model.py`

- [ ] Create `healthflow/feedback/reward_model.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
```

- [ ] Create reward model tests in `healthflow/tests/test_reward_model.py`:

```python
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker, Feedback
from healthflow.feedback.reward_model import RewardModel


async def _create_broker(db: AsyncSession, email: str) -> Broker:
    broker = Broker(
        id=uuid.uuid4(),
        email=email,
        hashed_password="hashed",
        full_name="Reward Tester",
    )
    db.add(broker)
    await db.flush()
    return broker


async def _add_feedback(
    db: AsyncSession,
    broker_id: uuid.UUID,
    output_id: str,
    agent_type: str,
    accuracy: int,
    clarity: int,
    helpfulness: int,
):
    fb = Feedback(
        broker_id=broker_id,
        output_id=output_id,
        agent_type=agent_type,
        accuracy=accuracy,
        clarity=clarity,
        helpfulness=helpfulness,
    )
    db.add(fb)
    await db.flush()


@pytest.mark.anyio
async def test_score_outputs_correct_averages(db_session: AsyncSession):
    broker = await _create_broker(db_session, "reward1@test.com")
    await _add_feedback(db_session, broker.id, "out1", "compare", 5, 5, 5)
    await _add_feedback(db_session, broker.id, "out2", "compare", 3, 3, 3)

    model = RewardModel()
    report = await model.score_outputs(db_session, days=7)

    assert report["overall_avg"] == 4.0
    assert len(report["agents"]) == 1
    assert report["agents"][0]["avg_accuracy"] == 4.0


@pytest.mark.anyio
async def test_flag_low_scoring_outputs(db_session: AsyncSession):
    broker = await _create_broker(db_session, "reward2@test.com")
    await _add_feedback(db_session, broker.id, "bad1", "translate", 1, 1, 1)
    await _add_feedback(db_session, broker.id, "bad2", "translate", 2, 2, 2)

    model = RewardModel()
    report = await model.score_outputs(db_session, days=7)

    assert report["low_score_count"] >= 1
    assert "bad1" in report["bottom_output_ids"]


@pytest.mark.anyio
async def test_identify_top_outputs(db_session: AsyncSession):
    broker = await _create_broker(db_session, "reward3@test.com")
    await _add_feedback(db_session, broker.id, "top1", "compare", 5, 5, 5)

    model = RewardModel()
    report = await model.score_outputs(db_session, days=7)

    assert "top1" in report["top_output_ids"]
    assert report["best_agent"] == "compare"


@pytest.mark.anyio
async def test_empty_feedback(db_session: AsyncSession):
    model = RewardModel()
    report = await model.score_outputs(db_session, days=7)

    assert report["overall_avg"] == 0.0
    assert report["agents"] == []
    assert report["top_output_ids"] == []
    assert report["bottom_output_ids"] == []
    assert report["worst_agent"] is None
    assert report["best_agent"] is None


@pytest.mark.anyio
async def test_score_outputs_filter_by_agent_type(db_session: AsyncSession):
    broker = await _create_broker(db_session, "reward4@test.com")
    await _add_feedback(db_session, broker.id, "c1", "compare", 5, 5, 5)
    await _add_feedback(db_session, broker.id, "t1", "translate", 2, 2, 2)

    model = RewardModel()
    report = await model.score_outputs(db_session, agent_type="compare", days=7)

    assert len(report["agents"]) == 1
    assert report["agents"][0]["agent_type"] == "compare"
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_reward_model.py -v`

---

## Task 5: Prompt Updater

**File:** Create `healthflow/feedback/prompt_updater.py`

- [ ] Create `healthflow/feedback/prompt_updater.py`:

```python
import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import ActionHistory, Feedback, PromptVariant
from healthflow.models.schemas import AgentFeedbackStats


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
```

- [ ] Create prompt updater tests in `healthflow/tests/test_prompt_updater.py`:

```python
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import ActionHistory, Broker, Client, Feedback, PromptVariant
from healthflow.feedback.prompt_updater import PromptUpdater


async def _setup_broker_client(db: AsyncSession):
    broker = Broker(
        id=uuid.uuid4(),
        email=f"pu-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="hashed",
        full_name="PU Tester",
    )
    db.add(broker)
    await db.flush()

    client = Client(
        id=uuid.uuid4(),
        broker_id=broker.id,
        full_name="Test Client",
        zip_code="90210",
        age=45,
        income_level="medium",
    )
    db.add(client)
    await db.flush()
    return broker, client


@pytest.mark.anyio
async def test_generate_few_shot_with_history(db_session: AsyncSession):
    broker, client = await _setup_broker_client(db_session)

    # Create an action history entry
    action_id = uuid.uuid4()
    action = ActionHistory(
        id=action_id,
        broker_id=broker.id,
        client_id=client.id,
        action_type="compare",
        request_data={"zip_code": "90210"},
        response_summary={"plans": ["Plan A"]},
    )
    db_session.add(action)
    await db_session.flush()

    # Create feedback referencing that action
    fb = Feedback(
        broker_id=broker.id,
        output_id=str(action_id),
        agent_type="compare",
        accuracy=5,
        clarity=5,
        helpfulness=5,
    )
    db_session.add(fb)
    await db_session.flush()

    updater = PromptUpdater()
    result = await updater.generate_few_shot(db_session, "compare", top_n=3)

    assert "compare" in result.lower() or "Example" in result
    assert len(result) > 0


@pytest.mark.anyio
async def test_generate_few_shot_empty(db_session: AsyncSession):
    updater = PromptUpdater()
    result = await updater.generate_few_shot(db_session, "compare")
    assert result == ""


@pytest.mark.anyio
async def test_create_variant(db_session: AsyncSession):
    # Create a control variant first
    control = PromptVariant(
        id=uuid.uuid4(),
        agent_type="compare",
        variant_name="control",
        prompt_template="You are a plan comparison agent.",
        is_active=True,
        traffic_pct=100,
    )
    db_session.add(control)
    await db_session.flush()

    updater = PromptUpdater()
    new_variant = await updater.create_variant(
        db=db_session,
        agent_type="compare",
        prompt_template="You are an improved plan comparison agent with examples.",
        traffic_pct=20,
    )

    assert new_variant.traffic_pct == 20
    assert new_variant.is_active is True
    assert "updated_v" in new_variant.variant_name

    # Refresh control to check adjusted traffic
    await db_session.refresh(control)
    assert control.traffic_pct == 80


@pytest.mark.anyio
async def test_get_active_variant(db_session: AsyncSession):
    v1 = PromptVariant(
        id=uuid.uuid4(),
        agent_type="translate",
        variant_name="control",
        prompt_template="Control prompt",
        is_active=True,
        traffic_pct=80,
    )
    v2 = PromptVariant(
        id=uuid.uuid4(),
        agent_type="translate",
        variant_name="updated_v1",
        prompt_template="Updated prompt",
        is_active=True,
        traffic_pct=20,
    )
    db_session.add_all([v1, v2])
    await db_session.flush()

    updater = PromptUpdater()
    chosen = await updater.get_active_variant(db_session, "translate")

    assert chosen is not None
    assert chosen.agent_type == "translate"
    assert chosen.variant_name in ("control", "updated_v1")


@pytest.mark.anyio
async def test_get_active_variant_none(db_session: AsyncSession):
    updater = PromptUpdater()
    chosen = await updater.get_active_variant(db_session, "nonexistent")
    assert chosen is None
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_prompt_updater.py -v`

---

## Task 6: Feedback Router (API Endpoints)

**File:** Create `healthflow/feedback/router.py`

- [ ] Create `healthflow/feedback/router.py`:

```python
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
        broker_id=broker.id,
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
```

- [ ] Create route tests in `healthflow/tests/test_feedback_routes.py`:

```python
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker
from healthflow.auth.security import hash_password, create_access_token


async def _create_broker_and_token(db: AsyncSession):
    """Helper: create a broker and return (broker, access_token)."""
    broker_id = uuid.uuid4()
    broker = Broker(
        id=broker_id,
        email=f"route-{broker_id.hex[:6]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="Route Tester",
    )
    db.add(broker)
    await db.commit()

    token = create_access_token({"sub": str(broker_id), "type": "access"})
    return broker, token


@pytest.mark.anyio
async def test_submit_feedback(client: AsyncClient, db_session: AsyncSession):
    broker, token = await _create_broker_and_token(db_session)
    resp = await client.post(
        "/feedback",
        json={
            "output_id": "sess-100",
            "agent_type": "compare",
            "accuracy": 5,
            "clarity": 4,
            "helpfulness": 4,
            "comment": "Nice work",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["accuracy"] == 5
    assert data["agent_type"] == "compare"
    assert data["broker_id"] == str(broker.id)


@pytest.mark.anyio
async def test_submit_feedback_invalid_rating(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    resp = await client.post(
        "/feedback",
        json={
            "output_id": "sess-100",
            "agent_type": "compare",
            "accuracy": 0,
            "clarity": 4,
            "helpfulness": 4,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_list_feedback(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    # Submit two
    for i in range(2):
        await client.post(
            "/feedback",
            json={
                "output_id": f"sess-{i}",
                "agent_type": "compare",
                "accuracy": 4,
                "clarity": 4,
                "helpfulness": 4,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/feedback",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.anyio
async def test_list_feedback_filter(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    await client.post(
        "/feedback",
        json={"output_id": "s1", "agent_type": "compare", "accuracy": 4, "clarity": 4, "helpfulness": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/feedback",
        json={"output_id": "s2", "agent_type": "translate", "accuracy": 3, "clarity": 3, "helpfulness": 3},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/feedback?agent_type=compare",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["agent_type"] == "compare"


@pytest.mark.anyio
async def test_get_analytics(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    await client.post(
        "/feedback",
        json={"output_id": "a1", "agent_type": "compare", "accuracy": 5, "clarity": 5, "helpfulness": 5},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/feedback/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_feedback"] == 1
    assert len(data["agents"]) == 1


@pytest.mark.anyio
async def test_reward_score(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)
    await client.post(
        "/feedback",
        json={"output_id": "r1", "agent_type": "compare", "accuracy": 5, "clarity": 5, "helpfulness": 5},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/feedback/reward-score",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert "overall_avg" in data


@pytest.mark.anyio
async def test_weekly_report(client: AsyncClient, db_session: AsyncSession):
    _, token = await _create_broker_and_token(db_session)

    resp = await client.get(
        "/feedback/weekly-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "worst_agent" in data
    assert "best_agent" in data


@pytest.mark.anyio
async def test_feedback_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/feedback",
        json={"output_id": "x", "agent_type": "compare", "accuracy": 3, "clarity": 3, "helpfulness": 3},
    )
    assert resp.status_code == 401

    resp = await client.get("/feedback")
    assert resp.status_code == 401

    resp = await client.get("/feedback/analytics")
    assert resp.status_code == 401
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_feedback_routes.py -v`

---

## Task 7: Wire into Main App

**Files:** `healthflow/main.py`, `frontend/vite.config.js`

- [ ] Add feedback router import to `healthflow/main.py` (after line 9):

```python
from healthflow.feedback.router import feedback_router
```

- [ ] Add `app.include_router(feedback_router)` to `healthflow/main.py` (after line 41, the `history_router` include):

```python
app.include_router(feedback_router)
```

The resulting imports section should look like:

```python
from healthflow.api.routes import router
from healthflow.auth.router import auth_router
from healthflow.api.client_router import client_router
from healthflow.api.history_router import history_router
from healthflow.feedback.router import feedback_router
```

And the router includes section:

```python
app.include_router(router)
app.include_router(auth_router)
app.include_router(client_router)
app.include_router(history_router)
app.include_router(feedback_router)
```

- [ ] Add `/feedback` proxy to `frontend/vite.config.js` (after the `/history` line):

```javascript
      '/feedback': 'http://localhost:8000',
```

- [ ] Verify routes are registered by running:

```bash
cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -c "
from healthflow.main import app
routes = [r.path for r in app.routes]
assert '/feedback' in routes or any('/feedback' in str(r.path) for r in app.routes), 'feedback route missing'
print('Feedback routes registered successfully')
for r in app.routes:
    if hasattr(r, 'path') and 'feedback' in str(r.path):
        print(f'  {r.path}')
"
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/ -k "test_" --co -q 2>/dev/null | grep feedback` to confirm test collection works.

---

## Task 8: Integration Tests

**File:** Create `healthflow/tests/test_feedback_integration.py`

- [ ] Create `healthflow/tests/test_feedback_integration.py`:

```python
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker, PromptVariant
from healthflow.auth.security import hash_password, create_access_token
from healthflow.feedback.collector import FeedbackCollector
from healthflow.feedback.reward_model import RewardModel
from healthflow.feedback.prompt_updater import PromptUpdater


async def _create_broker_and_token(db: AsyncSession):
    broker_id = uuid.uuid4()
    broker = Broker(
        id=broker_id,
        email=f"integ-{broker_id.hex[:6]}@test.com",
        hashed_password=hash_password("testpass123"),
        full_name="Integration Tester",
    )
    db.add(broker)
    await db.commit()
    token = create_access_token({"sub": str(broker_id), "type": "access"})
    return broker, token


@pytest.mark.anyio
async def test_end_to_end_feedback_to_report(client: AsyncClient, db_session: AsyncSession):
    """Submit feedback -> get analytics -> run reward score -> verify report."""
    broker, token = await _create_broker_and_token(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Submit feedback for multiple agents
    for agent in ["compare", "translate"]:
        for i in range(3):
            score = 5 if agent == "compare" else 2
            resp = await client.post(
                "/feedback",
                json={
                    "output_id": f"{agent}-{i}",
                    "agent_type": agent,
                    "accuracy": score,
                    "clarity": score,
                    "helpfulness": score,
                },
                headers=headers,
            )
            assert resp.status_code == 201

    # Step 2: Get analytics
    resp = await client.get("/feedback/analytics", headers=headers)
    assert resp.status_code == 200
    analytics = resp.json()
    assert analytics["total_feedback"] == 6
    assert len(analytics["agents"]) == 2

    # Step 3: Run reward score
    resp = await client.post("/feedback/reward-score", headers=headers)
    assert resp.status_code == 200
    report = resp.json()

    # Step 4: Verify report
    assert report["best_agent"] == "compare"
    assert report["worst_agent"] == "translate"
    assert report["low_score_count"] >= 1  # translate outputs avg 2.0 < 3.0
    assert len(report["top_output_ids"]) >= 1  # compare outputs avg 5.0 > 4.5


@pytest.mark.anyio
async def test_ab_variant_routing(db_session: AsyncSession):
    """Create variants and verify weighted routing works."""
    updater = PromptUpdater()

    # Create control variant
    control = PromptVariant(
        id=uuid.uuid4(),
        agent_type="appeal",
        variant_name="control",
        prompt_template="Control prompt for appeal",
        is_active=True,
        traffic_pct=100,
    )
    db_session.add(control)
    await db_session.flush()

    # Create updated variant (20% traffic)
    new_variant = await updater.create_variant(
        db=db_session,
        agent_type="appeal",
        prompt_template="Improved prompt with examples",
        traffic_pct=20,
    )

    # Verify traffic split
    await db_session.refresh(control)
    assert control.traffic_pct == 80
    assert new_variant.traffic_pct == 20

    # Run routing 100 times to verify both variants get selected
    selections = {"control": 0, new_variant.variant_name: 0}
    for _ in range(100):
        chosen = await updater.get_active_variant(db_session, "appeal")
        assert chosen is not None
        selections[chosen.variant_name] = selections.get(chosen.variant_name, 0) + 1

    # Both variants should be selected at least once in 100 runs
    assert selections["control"] > 0, "Control variant never selected"
    assert selections[new_variant.variant_name] > 0, "Updated variant never selected"


@pytest.mark.anyio
async def test_weekly_report_with_mixed_feedback(client: AsyncClient, db_session: AsyncSession):
    """Weekly report with a mix of high and low feedback across agents."""
    broker, token = await _create_broker_and_token(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # High-quality compare feedback
    for i in range(5):
        await client.post(
            "/feedback",
            json={
                "output_id": f"good-{i}",
                "agent_type": "compare",
                "accuracy": 5,
                "clarity": 5,
                "helpfulness": 5,
                "comment": "Excellent",
            },
            headers=headers,
        )

    # Low-quality translate feedback
    for i in range(3):
        await client.post(
            "/feedback",
            json={
                "output_id": f"bad-{i}",
                "agent_type": "translate",
                "accuracy": 1,
                "clarity": 2,
                "helpfulness": 1,
            },
            headers=headers,
        )

    # Medium calculate feedback
    for i in range(4):
        await client.post(
            "/feedback",
            json={
                "output_id": f"mid-{i}",
                "agent_type": "calculate",
                "accuracy": 3,
                "clarity": 3,
                "helpfulness": 4,
            },
            headers=headers,
        )

    # Get weekly report
    resp = await client.get("/feedback/weekly-report", headers=headers)
    assert resp.status_code == 200
    report = resp.json()

    assert report["best_agent"] == "compare"
    assert report["worst_agent"] == "translate"
    assert report["overall_avg"] > 0
    assert len(report["agents"]) == 3

    # Verify top outputs are from compare (all scored 5.0)
    assert len(report["top_output_ids"]) >= 1

    # Verify bottom outputs are from translate (avg ~1.33)
    assert len(report["bottom_output_ids"]) >= 1
```

**Verification:** Run `cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_feedback_integration.py -v`

---

## Final Verification

Run the full feedback test suite:

```bash
cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/test_feedback_models.py healthflow/tests/test_feedback_schemas.py healthflow/tests/test_feedback_collector.py healthflow/tests/test_reward_model.py healthflow/tests/test_prompt_updater.py healthflow/tests/test_feedback_routes.py healthflow/tests/test_feedback_integration.py -v
```

Then run the full project test suite to ensure no regressions:

```bash
cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/python -m pytest healthflow/tests/ -v
```

## Files Created/Modified Summary

| Action | File |
|--------|------|
| Modified | `healthflow/database/models.py` — add `Feedback` and `PromptVariant` models, `feedbacks` relationship on `Broker` |
| Modified | `healthflow/models/schemas.py` — add `FeedbackCreate`, `FeedbackResponse`, `AgentFeedbackStats`, `FeedbackAnalytics`, `WeeklyReport` |
| Modified | `healthflow/main.py` — import and include `feedback_router` |
| Modified | `frontend/vite.config.js` — add `/feedback` proxy |
| Created | `healthflow/feedback/__init__.py` — empty package marker |
| Created | `healthflow/feedback/collector.py` — `FeedbackCollector` class |
| Created | `healthflow/feedback/reward_model.py` — `RewardModel` class |
| Created | `healthflow/feedback/prompt_updater.py` — `PromptUpdater` class |
| Created | `healthflow/feedback/router.py` — FastAPI feedback endpoints |
| Created | `healthflow/tests/test_feedback_models.py` |
| Created | `healthflow/tests/test_feedback_schemas.py` |
| Created | `healthflow/tests/test_feedback_collector.py` |
| Created | `healthflow/tests/test_reward_model.py` |
| Created | `healthflow/tests/test_prompt_updater.py` |
| Created | `healthflow/tests/test_feedback_routes.py` |
| Created | `healthflow/tests/test_feedback_integration.py` |
