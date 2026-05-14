import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from healthflow.database.tenant_filter import install_raw_sql_guard, install_tenant_filter

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///healthflow.db",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Install the tenant isolation listeners on the production engine and session
# factory. Done at import time so any code path that uses the default factory
# is automatically protected.
install_raw_sql_guard(engine)
install_tenant_filter(async_session_factory)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession scoped to the request, commit on success.

    Cleanup contract: this generator's teardown (commit + close) runs
    AFTER any auth dependency's teardown, including `get_current_broker`'s
    ContextVar reset. Code in this teardown must NOT emit SELECTs against
    tenant-scoped tables (Client, ActionHistory, Feedback) — there's no
    current_broker_id at that point. With `expire_on_commit=False` (set
    on the session factory above), commit does not fire SELECTs, so the
    contract holds.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_with_factory(
    factory: async_sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    """Variant of get_db that accepts a custom session factory (used in tests)."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_test_session_factory() -> async_sessionmaker:
    """Create an in-memory SQLite engine + session factory for testing."""
    from healthflow.database.models import Base

    test_engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    return factory
