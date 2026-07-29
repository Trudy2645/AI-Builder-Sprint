from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_database_session
from app.domain.profiles.service import ProfileService
from app.repositories.profiles import ProfileRepository, SqlAlchemyProfileRepository


def get_profile_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ProfileRepository:
    return SqlAlchemyProfileRepository(session)


def get_profile_service(
    repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileService:
    return ProfileService(repository)
