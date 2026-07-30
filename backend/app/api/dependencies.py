from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_database_session
from app.domain.listings.service import PublicListingService
from app.domain.profiles.service import ProfileService
from app.repositories.listings import PublicListingRepository, SqlAlchemyPublicListingRepository
from app.repositories.profiles import ProfileRepository, SqlAlchemyProfileRepository


def get_public_listing_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> PublicListingRepository:
    return SqlAlchemyPublicListingRepository(session)


def get_public_listing_service(
    repository: Annotated[PublicListingRepository, Depends(get_public_listing_repository)],
) -> PublicListingService:
    return PublicListingService(repository)


def get_profile_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ProfileRepository:
    return SqlAlchemyProfileRepository(session)


def get_profile_service(
    repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileService:
    return ProfileService(repository)
