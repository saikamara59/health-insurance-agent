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
