from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from a11ywatch.core.config import settings


@asynccontextmanager
async def worker_session() -> AsyncIterator[AsyncSession]:
    """A fresh NullPool engine + session per ``asyncio.run()``.

    Workers are sync processes that bridge to the async DB via ``asyncio.run()`` (once
    before and once after the sync Playwright engine runs). A pooled engine would reuse
    asyncpg connections across distinct event loops — which errors — so each call gets a
    throwaway NullPool engine that is disposed when done. Also safe across forked RQ jobs.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()
