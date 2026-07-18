from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_current_user_id, get_session
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


@pytest_asyncio.fixture
async def isolated_user(session):
    """A throwaway user, wired into get_current_user_id for the client.

    Integration tests MUST use this instead of the dev user: the dev
    database holds real imported data and real OAuth connections, and
    test writes/cleanups must never touch them. Deleting the user at
    teardown cascades away everything the test created.
    """
    user = User(
        id=uuid4(),
        email=f"test-{uuid4().hex}@stridesense.local",
        source_priority={},
    )
    session.add(user)
    await session.commit()
    app.dependency_overrides[get_current_user_id] = lambda: user.id
    yield user
    app.dependency_overrides.pop(get_current_user_id, None)
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()


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
