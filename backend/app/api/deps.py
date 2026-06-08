from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_current_user_id() -> UUID:
    """Phase 1: returns the hardcoded dev user. Phase 3 swaps in real auth."""
    return get_settings().dev_user_id


# Type aliases used by route handlers — keeps the signatures readable
SessionDep = Depends(get_session)
UserIdDep = Depends(get_current_user_id)
