"""Tests for per-worker seed provisioning."""
import pytest
from sqlalchemy import select

from healthflow.database.models import Broker, Client
from healthflow.seed_data import (
    TEST_CLIENTS,
    seed_for_worker,
    worker_email,
)


def test_worker_email_is_deterministic():
    assert worker_email("e2e-worker-0") == "e2e-worker-0@healthflow.test"
    assert worker_email("e2e-worker-3") == "e2e-worker-3@healthflow.test"


@pytest.mark.anyio
async def test_seed_for_worker_creates_broker_and_clients(db_session):
    broker = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    assert broker.email == "e2e-worker-0@healthflow.test"
    assert broker.full_name == "E2E Worker 0"

    clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker.id))
    ).scalars().all()
    assert len(clients) == len(TEST_CLIENTS)
    assert {c.full_name for c in clients} == {c["full_name"] for c in TEST_CLIENTS}


@pytest.mark.anyio
async def test_seed_for_worker_is_idempotent_on_broker(db_session):
    broker_a = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()
    broker_b = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    assert broker_a.id == broker_b.id

    brokers = (
        await db_session.execute(
            select(Broker).where(Broker.email == "e2e-worker-0@healthflow.test")
        )
    ).scalars().all()
    assert len(brokers) == 1


@pytest.mark.anyio
async def test_seed_for_worker_replaces_existing_clients(db_session):
    broker = await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    extra = Client(
        broker_id=broker.id,
        full_name="Stale Client",
        zip_code="00000",
        age=30,
        income_level="low",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(extra)
    await db_session.commit()

    await seed_for_worker(db_session, "e2e-worker-0")
    await db_session.commit()

    clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker.id))
    ).scalars().all()
    names = {c.full_name for c in clients}
    assert names == {c["full_name"] for c in TEST_CLIENTS}
    assert "Stale Client" not in names


@pytest.mark.anyio
async def test_seed_for_worker_isolates_brokers(db_session):
    broker_a = await seed_for_worker(db_session, "e2e-worker-0")
    broker_b = await seed_for_worker(db_session, "e2e-worker-1")
    await db_session.commit()

    assert broker_a.id != broker_b.id
    a_clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker_a.id))
    ).scalars().all()
    b_clients = (
        await db_session.execute(select(Client).where(Client.broker_id == broker_b.id))
    ).scalars().all()
    assert len(a_clients) == len(TEST_CLIENTS)
    assert len(b_clients) == len(TEST_CLIENTS)
    assert {c.id for c in a_clients}.isdisjoint({c.id for c in b_clients})
