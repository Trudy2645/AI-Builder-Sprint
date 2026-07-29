from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.errors import AppError


@lru_cache
def get_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(database_url), expire_on_commit=False)


async def get_database_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    if not settings.database_url:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_NOT_CONFIGURED",
            message="Database connection is not configured.",
        )
    factory = get_session_factory(settings.database_url)
    async with factory() as session:
        yield session
