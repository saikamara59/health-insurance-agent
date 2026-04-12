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
