from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.core.errors import AppError
from app.domain.listings.service import PublicListingService
from app.domain.profiles.service import ProfileService
from app.integrations.modusign import ModusignClient
from app.repositories.profiles import ProfileRepository, SqlAlchemyProfileRepository
from app.repositories.public_listings import (
    PublicListingRepository,
    SqlAlchemyPublicListingRepository,
)


def get_profile_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ProfileRepository:
    return SqlAlchemyProfileRepository(session)


def get_profile_service(
    repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileService:
    return ProfileService(repository)


def get_public_listing_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> PublicListingRepository:
    return SqlAlchemyPublicListingRepository(session)


def get_public_listing_service(
    repository: Annotated[PublicListingRepository, Depends(get_public_listing_repository)],
) -> PublicListingService:
    return PublicListingService(repository)


def get_modusign_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ModusignClient:
    if not settings.modusign_api_key or not settings.modusign_auth_email:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODUSIGN_NOT_CONFIGURED",
            message="Modusign integration is not configured.",
        )
    return ModusignClient(
        base_url=settings.modusign_base_url,
        api_key=settings.modusign_api_key,
        auth_email=settings.modusign_auth_email,
        timeout_seconds=settings.modusign_timeout_seconds,
    )
