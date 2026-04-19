import pytest
from sqlalchemy import select

from healthflow.database.models import Broker, Client
from healthflow.seed_data import TEST_BROKER, TEST_CLIENTS, seed_db


@pytest.mark.anyio
async def test_seed_db_creates_test_broker(db_session):
    await seed_db(db_session)
    await db_session.commit()
    result = await db_session.execute(select(Broker).where(Broker.email == TEST_BROKER["email"]))
    broker = result.scalar_one()
    assert broker.full_name == TEST_BROKER["full_name"]


@pytest.mark.anyio
async def test_seed_db_creates_test_clients(db_session):
    await seed_db(db_session)
    await db_session.commit()
    result = await db_session.execute(select(Client))
    clients = result.scalars().all()
    assert len(clients) == len(TEST_CLIENTS)
    names = {c.full_name for c in clients}
    assert names == {c["full_name"] for c in TEST_CLIENTS}


@pytest.mark.anyio
async def test_seed_db_clients_belong_to_test_broker(db_session):
    await seed_db(db_session)
    await db_session.commit()
    broker_result = await db_session.execute(select(Broker).where(Broker.email == TEST_BROKER["email"]))
    broker = broker_result.scalar_one()
    client_result = await db_session.execute(select(Client))
    clients = client_result.scalars().all()
    assert all(c.broker_id == broker.id for c in clients)
