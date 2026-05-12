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
