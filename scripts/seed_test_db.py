"""Wipe + reseed the test DB. Run inside the backend container by docker-compose.test.yml."""
import asyncio

from healthflow.database.config import engine, get_db
from healthflow.database.models import Base
from healthflow.seed_data import seed_db


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async for session in get_db():
        await seed_db(session)
        await session.commit()
        break


if __name__ == "__main__":
    asyncio.run(main())
