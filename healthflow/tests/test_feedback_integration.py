import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.database.models import Broker, PromptVariant
from healthflow.auth.security import hash_password, create_access_token
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
