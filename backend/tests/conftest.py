import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_session
from app.core.config import get_settings
from app.db.session import engine as app_engine
from app.main import app
from app.models import User


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine():
    # Background tasks use the app's global engine; its pooled connections
    # are bound to this test's event loop and must not leak into the next
    # test's loop.
    yield
    await app_engine.dispose()


@pytest_asyncio.fixture
async def session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def ensure_dev_user(session):
    settings = get_settings()
    existing = await session.execute(select(User).where(User.id == settings.dev_user_id))
    if existing.scalar_one_or_none() is None:
        session.add(
            User(
                id=settings.dev_user_id,
                email="dev@stridesense.local",
                source_priority={},
            )
        )
        await session.commit()
