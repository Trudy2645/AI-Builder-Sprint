from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.upstage import UpstageAIProvider
from app.core.auth import get_auth_account_provider
from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.core.errors import AppError
from app.domain.ai_jobs.service import AIJobService
from app.domain.auth_accounts.service import AuthAccountService, DemoLoginConfig
from app.domain.contracts.service import ContractService
from app.domain.document_processing.service import DocumentProcessingService
from app.domain.documents.service import DocumentService
from app.domain.listings.service import PublicListingService
from app.domain.notifications.service import NotificationService
from app.domain.pricing.service import PriceCalculator, PriceEstimateService
from app.domain.profiles.service import ProfileService
from app.domain.revisions.service import RevisionService
from app.domain.seller_listings.service import SellerListingService
from app.integrations.auth import AuthAccountProvider
from app.integrations.exchange_rates import ExchangeRateProvider, FakeExchangeRateProvider
from app.integrations.modusign import ModusignClient
from app.integrations.storage import StorageProvider, SupabaseStorageProvider
from app.repositories.ai_jobs import AIJobRepository, SqlAlchemyAIJobRepository
from app.repositories.auth_accounts import (
    RegistrationRepository,
    SqlAlchemyRegistrationRepository,
)
from app.repositories.contracts import ContractRepository, SqlAlchemyContractRepository
from app.repositories.document_processing import (
    DocumentProcessingRepository,
    SqlAlchemyDocumentProcessingRepository,
)
from app.repositories.documents import DocumentRepository, SqlAlchemyDocumentRepository
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


def get_ai_job_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> AIJobRepository:
    return SqlAlchemyAIJobRepository(session)


def get_ai_job_service(
    repository: Annotated[AIJobRepository, Depends(get_ai_job_repository)],
) -> AIJobService:
    return AIJobService(repository)


def get_ai_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FakeAIProvider | UpstageAIProvider:
    if settings.ai_provider == "fake":
        return FakeAIProvider()
    if not settings.upstage_api_key:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AI_PROVIDER_UNAVAILABLE",
            message="The AI provider is not configured.",
        )
    return UpstageAIProvider(
        api_key=settings.upstage_api_key,
        document_base_url=settings.upstage_document_base_url,
        chat_base_url=settings.upstage_chat_base_url,
        agent_base_url=settings.upstage_agent_base_url,
        chat_model=settings.upstage_chat_model,
        timeout_seconds=settings.ai_request_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )


def get_document_processing_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DocumentProcessingRepository:
    return SqlAlchemyDocumentProcessingRepository(session)


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


def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> DocumentRepository:
    return SqlAlchemyDocumentRepository(session)


def get_storage_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> StorageProvider:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="STORAGE_PROVIDER_UNAVAILABLE",
            message="The Storage provider is not configured.",
        )
    return SupabaseStorageProvider(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        timeout_seconds=settings.storage_request_timeout_seconds,
    )


def get_document_processing_service(
    repository: Annotated[
        DocumentProcessingRepository, Depends(get_document_processing_repository)
    ],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    provider: Annotated[FakeAIProvider | UpstageAIProvider, Depends(get_ai_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentProcessingService:
    return DocumentProcessingService(
        repository,
        storage,
        provider,
        provider,
        provider_name=settings.ai_provider,
        prompt_version=settings.ai_prompt_version,
        max_document_size_bytes=settings.document_max_size_bytes,
    )


def get_document_service(
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentService:
    return DocumentService(
        repository,
        storage,
        max_size_bytes=settings.document_max_size_bytes,
        download_url_expires_seconds=settings.document_download_url_expires_seconds,
    )


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
