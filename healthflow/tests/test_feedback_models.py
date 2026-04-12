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
