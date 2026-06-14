import asyncio

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from rq import Queue
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import a11ywatch.models.tables  # noqa: F401  (register ORM models on Base.metadata)
from a11ywatch.api.deps import get_scan_queue
from a11ywatch.core.config import settings
from a11ywatch.core.db import Base, get_session
from a11ywatch.main import app

TEST_DB_NAME = "a11ywatch_test"
_base_url = make_url(settings.database_url)
TEST_DB_URL = _base_url.set(database=TEST_DB_NAME).render_as_string(hide_password=False)


async def _create_db_if_missing() -> None:
    import asyncpg

    admin = await asyncpg.connect(
        host=_base_url.host,
        port=_base_url.port,
        user=_base_url.username,
        password=_base_url.password,
        database="postgres",
    )
    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", TEST_DB_NAME)
        if not exists:
            await admin.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db():
    asyncio.run(_create_db_if_missing())


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _get_session():
        async with session_factory() as session:
            yield session

    def _get_scan_queue():
        return Queue("scans", connection=fakeredis.FakeStrictRedis())

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_scan_queue] = _get_scan_queue
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client):
    creds = {"email": "owner@example.com", "password": "secret123"}
    await client.post("/api/v1/auth/register", json=creds)
    token = (await client.post("/api/v1/auth/login", json=creds)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
