from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_auth_account_provider
from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.domain.auth_accounts.service import AuthAccountService, DemoLoginConfig
from app.domain.contracts.service import ContractService
from app.domain.listings.service import PublicListingService
from app.domain.notifications.service import NotificationService
from app.domain.pricing.service import PriceCalculator, PriceEstimateService
from app.domain.profiles.service import ProfileService
from app.domain.revisions.service import RevisionService
from app.domain.seller_listings.service import SellerListingService
from app.integrations.auth import AuthAccountProvider
from app.integrations.exchange_rates import ExchangeRateProvider, FakeExchangeRateProvider
from app.repositories.auth_accounts import (
    RegistrationRepository,
    SqlAlchemyRegistrationRepository,
)
from app.repositories.contracts import ContractRepository, SqlAlchemyContractRepository
from app.repositories.listings import PublicListingRepository, SqlAlchemyPublicListingRepository
from app.repositories.notifications import (
    NotificationRepository,
    SqlAlchemyNotificationRepository,
)
from app.repositories.pricing import PriceTermsRepository, SqlAlchemyPriceTermsRepository
from app.repositories.profiles import ProfileRepository, SqlAlchemyProfileRepository
from app.repositories.revisions import RevisionRepository, SqlAlchemyRevisionRepository
from app.repositories.seller_listings import (
    SellerListingRepository,
    SqlAlchemySellerListingRepository,
)


def get_registration_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> RegistrationRepository:
    return SqlAlchemyRegistrationRepository(session)


def get_auth_account_service(
    repository: Annotated[RegistrationRepository, Depends(get_registration_repository)],
    provider: Annotated[AuthAccountProvider, Depends(get_auth_account_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthAccountService:
    return AuthAccountService(
        repository,
        provider,
        demo_config=DemoLoginConfig(
            enabled=settings.demo_login_enabled,
            buyer_email=settings.demo_buyer_email,
            buyer_password=settings.demo_buyer_password,
            seller_email=settings.demo_seller_email,
            seller_password=settings.demo_seller_password,
        ),
        password_reset_redirect_url=settings.auth_password_reset_redirect_url,
    )


def get_auth_session_service(
    provider: Annotated[AuthAccountProvider, Depends(get_auth_account_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthAccountService:
    return AuthAccountService(
        None,
        provider,
        demo_config=DemoLoginConfig(
            enabled=settings.demo_login_enabled,
            buyer_email=settings.demo_buyer_email,
            buyer_password=settings.demo_buyer_password,
            seller_email=settings.demo_seller_email,
            seller_password=settings.demo_seller_password,
        ),
        password_reset_redirect_url=settings.auth_password_reset_redirect_url,
    )


def get_public_listing_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> PublicListingRepository:
    return SqlAlchemyPublicListingRepository(session)


def get_public_listing_service(
    repository: Annotated[PublicListingRepository, Depends(get_public_listing_repository)],
) -> PublicListingService:
    return PublicListingService(repository)


def get_notification_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> NotificationRepository:
    return SqlAlchemyNotificationRepository(session)


def get_notification_service(
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
) -> NotificationService:
    return NotificationService(repository)


def get_price_terms_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> PriceTermsRepository:
    return SqlAlchemyPriceTermsRepository(session)


def get_exchange_rate_provider() -> ExchangeRateProvider:
    return FakeExchangeRateProvider()


def get_price_estimate_service(
    repository: Annotated[PriceTermsRepository, Depends(get_price_terms_repository)],
    exchange_rate_provider: Annotated[ExchangeRateProvider, Depends(get_exchange_rate_provider)],
) -> PriceEstimateService:
    return PriceEstimateService(repository, exchange_rate_provider)


def get_contract_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ContractRepository:
    return SqlAlchemyContractRepository(session)


def get_contract_service(
    repository: Annotated[ContractRepository, Depends(get_contract_repository)],
    exchange_rate_provider: Annotated[ExchangeRateProvider, Depends(get_exchange_rate_provider)],
) -> ContractService:
    return ContractService(repository, PriceCalculator(exchange_rate_provider))


def get_revision_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> RevisionRepository:
    return SqlAlchemyRevisionRepository(session)


def get_revision_service(
    repository: Annotated[RevisionRepository, Depends(get_revision_repository)],
) -> RevisionService:
    return RevisionService(repository)


def get_seller_listing_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> SellerListingRepository:
    return SqlAlchemySellerListingRepository(session)


def get_seller_listing_service(
    repository: Annotated[SellerListingRepository, Depends(get_seller_listing_repository)],
) -> SellerListingService:
    return SellerListingService(repository)


def get_profile_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> ProfileRepository:
    return SqlAlchemyProfileRepository(session)


def get_profile_service(
    repository: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileService:
    return ProfileService(repository)
