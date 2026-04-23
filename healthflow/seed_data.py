"""Canonical test seed data and DB-direct seeder for the e2e test stack.

Used by `healthflow/api/test_router.py`'s reset endpoint. Distinct from the
top-level `seed.py` (which is an HTTP-based broker tool).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


TEST_BROKER = {
    "email": "broker@healthflow.test",
    "password": "TestBroker123!",
    "full_name": "E2E Test Broker",
}

TEST_CLIENTS = [
    {
        "full_name": "Eleanor Rigby",
        "zip_code": "10001",
        "age": 67,
        "income_level": "low",
        "doctors": [{"name": "Dr. Smith"}],
        "prescriptions": ["Metformin"],
        "procedures": ["Annual physical"],
    },
    {
        "full_name": "Julian Miller",
        "zip_code": "10001",
        "age": 42,
        "income_level": "medium",
        "doctors": [{"name": "Dr. Jones"}],
        "prescriptions": ["Ozempic"],
        "procedures": ["MRI"],
    },
    {
        "full_name": "Marcus Chen",
        "zip_code": "94102",
        "age": 58,
        "income_level": "high",
        "doctors": [{"name": "Dr. Patel"}],
        "prescriptions": ["Atorvastatin"],
        "procedures": ["Blood work"],
    },
]


async def seed_db(session: AsyncSession) -> None:
    """Insert TEST_BROKER and TEST_CLIENTS into a fresh schema.

    Caller is responsible for committing.
    """
    broker = Broker(
        email=TEST_BROKER["email"],
        hashed_password=hash_password(TEST_BROKER["password"]),
        full_name=TEST_BROKER["full_name"],
    )
    session.add(broker)
    await session.flush()

    for client_data in TEST_CLIENTS:
        client = Client(
            broker_id=broker.id,
            full_name=client_data["full_name"],
            zip_code=client_data["zip_code"],
            age=client_data["age"],
            income_level=client_data["income_level"],
            doctors=client_data["doctors"],
            prescriptions=client_data["prescriptions"],
            procedures=client_data["procedures"],
        )
        session.add(client)
    await session.flush()
