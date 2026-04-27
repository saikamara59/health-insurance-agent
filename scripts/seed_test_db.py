"""Reset the test DB schema. Run inside the backend container by docker-compose.test.yml.

Per-worker data is provisioned lazily via POST /__test/reset (see
healthflow/api/test_router.py). This script only ensures a clean schema
exists at stack startup.
"""
import asyncio

from healthflow.database.config import engine
from healthflow.database.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(main())
