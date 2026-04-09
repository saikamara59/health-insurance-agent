import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from healthflow.database.models import Base, Broker, Client, ActionHistory


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_broker(db_session):
    broker = Broker(
        email="test@example.com",
        hashed_password="fakehash",
        full_name="Test Broker",
    )
    db_session.add(broker)
    await db_session.commit()

    result = await db_session.execute(select(Broker).where(Broker.email == "test@example.com"))
    saved = result.scalar_one()
    assert saved.email == "test@example.com"
    assert saved.full_name == "Test Broker"
    assert saved.role == "broker"
    assert saved.is_active is True
    assert saved.id is not None
    assert isinstance(saved.created_at, datetime)


@pytest.mark.asyncio
async def test_create_client_linked_to_broker(db_session):
    broker = Broker(
        email="broker@example.com",
        hashed_password="fakehash",
        full_name="Test Broker",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    client = Client(
        broker_id=broker.id,
        full_name="Jane Doe",
        zip_code="10001",
        age=45,
        income_level="medium",
        doctors=[{"name": "Dr. Chen", "npi": "1234567890"}],
        prescriptions=["Metformin", "Lisinopril"],
        procedures=["MRI"],
    )
    db_session.add(client)
    await db_session.commit()

    result = await db_session.execute(select(Client).where(Client.broker_id == broker.id))
    saved = result.scalar_one()
    assert saved.full_name == "Jane Doe"
    assert saved.zip_code == "10001"
    assert saved.age == 45
    assert saved.income_level == "medium"
    assert saved.doctors == [{"name": "Dr. Chen", "npi": "1234567890"}]
    assert saved.prescriptions == ["Metformin", "Lisinopril"]
    assert saved.procedures == ["MRI"]
    assert saved.broker_id == broker.id


@pytest.mark.asyncio
async def test_create_action_history(db_session):
    broker = Broker(
        email="broker2@example.com",
        hashed_password="fakehash",
        full_name="Broker Two",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    client = Client(
        broker_id=broker.id,
        full_name="John Smith",
        zip_code="90210",
        age=30,
        income_level="high",
        doctors=[],
        prescriptions=[],
        procedures=[],
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    action = ActionHistory(
        broker_id=broker.id,
        client_id=client.id,
        action_type="compare",
        request_data={"zip_code": "90210", "age": 30},
        response_summary={"plans_found": 3},
    )
    db_session.add(action)
    await db_session.commit()

    result = await db_session.execute(
        select(ActionHistory).where(ActionHistory.broker_id == broker.id)
    )
    saved = result.scalar_one()
    assert saved.action_type == "compare"
    assert saved.request_data == {"zip_code": "90210", "age": 30}
    assert saved.response_summary == {"plans_found": 3}
    assert saved.client_id == client.id


@pytest.mark.asyncio
async def test_jsonb_stores_complex_data(db_session):
    broker = Broker(
        email="broker3@example.com",
        hashed_password="fakehash",
        full_name="Broker Three",
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)

    complex_doctors = [
        {"name": "Dr. Chen", "npi": "1234567890"},
        {"name": "Dr. Patel", "npi": "0987654321"},
    ]
    complex_prescriptions = ["Metformin", "Lisinopril", "Atorvastatin"]

    client = Client(
        broker_id=broker.id,
        full_name="Complex Client",
        zip_code="60601",
        age=55,
        income_level="low",
        doctors=complex_doctors,
        prescriptions=complex_prescriptions,
        procedures=["MRI", "Blood work", "CT Scan"],
    )
    db_session.add(client)
    await db_session.commit()

    result = await db_session.execute(select(Client).where(Client.full_name == "Complex Client"))
    saved = result.scalar_one()
    assert len(saved.doctors) == 2
    assert saved.doctors[0]["npi"] == "1234567890"
    assert len(saved.prescriptions) == 3
    assert "Atorvastatin" in saved.prescriptions
    assert len(saved.procedures) == 3


@pytest.mark.asyncio
async def test_broker_unique_email(db_session):
    broker1 = Broker(
        email="unique@example.com",
        hashed_password="fakehash",
        full_name="Broker One",
    )
    db_session.add(broker1)
    await db_session.commit()

    broker2 = Broker(
        email="unique@example.com",
        hashed_password="fakehash2",
        full_name="Broker Two",
    )
    db_session.add(broker2)
    with pytest.raises(Exception):
        await db_session.commit()
