"""Endpoint tests for POST /temporal/plan.

Uses the existing `client` fixture + monkeypatches TemporalAwarenessAgent
in the routes module so no Anthropic calls happen.
"""
from datetime import date
from unittest.mock import MagicMock

import pytest

from healthflow.agents.temporal_awareness.schemas import (
    Action,
    ActionPlan,
    EventType,
)


async def _register_and_login(client, email="temporal@example.com", password="Cromulent42!"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Temporal Tester"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _fake_plan() -> ActionPlan:
    return ActionPlan(
        event_type=EventType.SEP_JOB_LOSS,
        trigger_date=date(2026, 5, 1),
        deadline=date(2026, 6, 30),
        days_remaining=60,
        urgency="low",
        actions=[
            Action(step=1, description="Compare available SEP plans for the new ZIP", target_date=date(2026, 5, 15)),
            Action(step=2, description="Submit application before the SEP window closes", target_date=date(2026, 6, 20)),
        ],
    )


@pytest.mark.asyncio
async def test_plan_with_structured_event(client, monkeypatch):
    from healthflow.agents.temporal_awareness import routes as routes_mod

    fake_agent = MagicMock()
    fake_agent.generate_plan.return_value = _fake_plan()
    monkeypatch.setattr(routes_mod, "TemporalAwarenessAgent", lambda: fake_agent)

    access = await _register_and_login(client)
    resp = await client.post(
        "/temporal/plan",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "event": {
                "event_type": "sep_job_loss",
                "trigger_date": "2026-05-01",
            },
            "today": "2026-05-01",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["event_type"] == "sep_job_loss"
    assert body["deadline"] == "2026-06-30"
    assert body["days_remaining"] == 60
    assert body["urgency"] == "low"
    assert len(body["actions"]) == 2


@pytest.mark.asyncio
async def test_plan_with_natural_language_description(client, monkeypatch):
    from healthflow.agents.temporal_awareness import routes as routes_mod

    fake_agent = MagicMock()
    fake_agent.generate_plan.return_value = _fake_plan()
    monkeypatch.setattr(routes_mod, "TemporalAwarenessAgent", lambda: fake_agent)

    access = await _register_and_login(client, email="nl@example.com")
    resp = await client.post(
        "/temporal/plan",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "description": "I lost my job two weeks ago, what do I need to do?",
            "today": "2026-05-15",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["event_type"] == "sep_job_loss"
    # Confirm the agent saw the description, not a structured event.
    sent = fake_agent.generate_plan.call_args.args[0]
    assert sent.description is not None
    assert sent.event is None


@pytest.mark.asyncio
async def test_plan_requires_bearer(client):
    resp = await client.post(
        "/temporal/plan",
        json={"description": "any text", "today": "2026-05-01"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_plan_rejects_both_event_and_description(client, monkeypatch):
    from healthflow.agents.temporal_awareness import routes as routes_mod

    fake_agent = MagicMock()
    monkeypatch.setattr(routes_mod, "TemporalAwarenessAgent", lambda: fake_agent)

    access = await _register_and_login(client, email="dup@example.com")
    resp = await client.post(
        "/temporal/plan",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "event": {"event_type": "sep_birth", "trigger_date": "2026-05-01"},
            "description": "also some text",
        },
    )

    assert resp.status_code == 422
    fake_agent.generate_plan.assert_not_called()


@pytest.mark.asyncio
async def test_plan_rejects_neither_event_nor_description(client, monkeypatch):
    from healthflow.agents.temporal_awareness import routes as routes_mod

    fake_agent = MagicMock()
    monkeypatch.setattr(routes_mod, "TemporalAwarenessAgent", lambda: fake_agent)

    access = await _register_and_login(client, email="none@example.com")
    resp = await client.post(
        "/temporal/plan",
        headers={"Authorization": f"Bearer {access}"},
        json={"today": "2026-05-01"},
    )

    assert resp.status_code == 422
    fake_agent.generate_plan.assert_not_called()
