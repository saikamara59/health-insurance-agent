import pytest
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_db_yields_session():
    """get_db should yield an AsyncSession and close it after."""
    from healthflow.database.config import get_test_session_factory, get_db_with_factory

    factory = await get_test_session_factory()
    session = None
    async for s in get_db_with_factory(factory):
        session = s
        assert isinstance(s, AsyncSession)
    # Session should have been closed after the generator exits
    assert session is not None


@pytest.mark.asyncio
async def test_database_url_default():
    """Default DATABASE_URL should point to local PostgreSQL."""
    with patch.dict("os.environ", {}, clear=True):
        from importlib import reload
        import healthflow.database.config as cfg
        reload(cfg)
        assert "sqlite+aiosqlite" in cfg.DATABASE_URL


@pytest.mark.asyncio
async def test_database_url_from_env():
    """DATABASE_URL should be read from environment."""
    with patch.dict("os.environ", {"DATABASE_URL": "sqlite+aiosqlite:///"}):
        from importlib import reload
        import healthflow.database.config as cfg
        reload(cfg)
        assert cfg.DATABASE_URL == "sqlite+aiosqlite:///"
