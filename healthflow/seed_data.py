"""Per-worker test seed: idempotently provisions a worker's Broker + canonical clients.

Used by `healthflow/api/test_router.py`'s scoped reset endpoint. The broker is
sticky across resets (we only ever create it, never delete) so JWTs issued to
it stay valid. Clients are wiped and re-inserted on each call.

Distinct from the top-level `seed.py` (an HTTP-based broker tool).
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.security import hash_password
from healthflow.database.models import Broker, Client


WORKER_PASSWORD = "TestWorker123!"

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


def worker_email(worker_id: str) -> str:
    return f"{worker_id}@healthflow.test"


def _worker_full_name(worker_id: str) -> str:
    suffix = worker_id.removeprefix("e2e-worker-")
    return f"E2E Worker {suffix}"


async def seed_for_worker(session: AsyncSession, worker_id: str) -> Broker:
    """Get-or-create the worker's broker, wipe its clients, re-insert canonical set.

    Caller is responsible for committing.
    """
    email = worker_email(worker_id)
    broker = (
        await session.execute(select(Broker).where(Broker.email == email))
    ).scalar_one_or_none()

    if broker is None:
        broker = Broker(
            email=email,
            hashed_password=hash_password(WORKER_PASSWORD),
            full_name=_worker_full_name(worker_id),
        )
        session.add(broker)
        await session.flush()

    await session.execute(delete(Client).where(Client.broker_id == broker.id))

    for client_data in TEST_CLIENTS:
        session.add(
            Client(
                broker_id=broker.id,
                full_name=client_data["full_name"],
                zip_code=client_data["zip_code"],
                age=client_data["age"],
                income_level=client_data["income_level"],
                doctors=client_data["doctors"],
                prescriptions=client_data["prescriptions"],
                procedures=client_data["procedures"],
            )
        )
    await session.flush()
    return broker
