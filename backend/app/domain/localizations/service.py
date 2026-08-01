from __future__ import annotations

import hashlib
import json
from typing import NoReturn
from uuid import UUID

from fastapi import status
from pydantic import ValidationError

from app.ai.prompts.v1.localize_explain import LOCALIZE_EXPLAIN_PROMPT_VERSION
from app.ai.providers.base import (
    AIProviderInvalidResponseError,
    AIProviderPermanentError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    LanguageModelProvider,
)
from app.ai.tasks.localize_explain import (
    LocalizationPreservationError,
    build_public_localization_source,
    localization_source_hash,
    localize_public_content,
    validate_localized_content,
)
from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.repositories.localizations import (
    LocalizationIdempotencyConflictError,
    LocalizationRepository,
    LocalizationRepositoryError,
)
from app.schemas.localizations import (
    ListingLocalizationRequest,
    ListingLocalizationResponse,
    LocalizationResult,
)


class LocalizationService:
    def __init__(
        self,
        repository: LocalizationRepository,
        language_model: LanguageModelProvider,
        *,
        provider_name: str,
        model_name: str,
        prompt_version: str,
    ) -> None:
        self._repository = repository
        self._language_model = language_model
        self._provider_name = provider_name
        self._model_name = model_name
        self._prompt_version = f"{prompt_version}:{LOCALIZE_EXPLAIN_PROMPT_VERSION}"

    async def localize_listing(
        self,
        listing_id: UUID,
        payload: ListingLocalizationRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> ListingLocalizationResponse:
        organization_id = self._organization_id(organization_header)
        try:
            if not await self._repository.is_seller_member(actor.id, organization_id):
                self._forbidden()
            record = await self._repository.get_source(listing_id, organization_id)
        except LocalizationRepositoryError as exc:
            self._database_unavailable(exc)
        if record is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOCALIZATION_SOURCE_NOT_FOUND",
                message="A published listing version was not found.",
            )
        if record.listing["version_no"] != payload.base_version_no:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="VERSION_CONFLICT",
                message="base_version_no does not match the published listing version.",
            )
        if record.listing["language"] != "ko-KR":
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="LOCALIZATION_SOURCE_LOCALE_INVALID",
                message="The canonical public localization source must be ko-KR.",
            )
        source = build_public_localization_source(record.listing, record.clauses, record.findings)
        source_hash = localization_source_hash(source)
        batch_request_hash = self._hash(
            {
                "listing_id": str(listing_id),
                "base_version_no": payload.base_version_no,
                "locales": [locale.value for locale in payload.locales],
                "source_hash": source_hash,
            }
        )
        results: list[LocalizationResult] = []
        for locale in payload.locales:
            result = await self._localize_locale(
                listing_id=listing_id,
                version_id=record.listing["current_version_id"],
                locale=locale.value,
                actor=actor,
                idempotency_key=idempotency_key,
                source=source,
                source_hash=source_hash,
                batch_request_hash=batch_request_hash,
            )
            results.append(result)
        return ListingLocalizationResponse(
            listing_id=listing_id,
            listing_version_id=record.listing["current_version_id"],
            source_locale="ko-KR",  # type: ignore[arg-type]
            source_hash=source_hash,
            results=results,
        )

    async def _localize_locale(
        self,
        *,
        listing_id: UUID,
        version_id: UUID,
        locale: str,
        actor: AuthenticatedUser,
        idempotency_key: str,
        source: dict,
        source_hash: str,
        batch_request_hash: str,
    ) -> LocalizationResult:
        del listing_id
        try:
            cached = await self._repository.get_cached(
                version_id, locale, self._prompt_version, source_hash
            )
        except LocalizationRepositoryError:
            return self._failed(locale, "DATABASE_UNAVAILABLE")
        if cached:
            return LocalizationResult(
                locale=locale,  # type: ignore[arg-type]
                status="cached",
                localized_content_id=cached.id,
            )
        request_hash = self._hash(
            {"version_id": str(version_id), "locale": locale, "source_hash": source_hash}
        )
        try:
            claim = await self._repository.claim_job(
                version_id=version_id,
                locale=locale,
                actor_user_id=actor.id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                batch_request_hash=batch_request_hash,
                provider=self._provider_name,
                model_name=self._model_name,
                prompt_version=self._prompt_version,
            )
        except LocalizationIdempotencyConflictError:
            return self._failed(locale, "IDEMPOTENCY_CONFLICT")
        except LocalizationRepositoryError:
            return self._failed(locale, "DATABASE_UNAVAILABLE")
        if not claim.should_run:
            return LocalizationResult(
                locale=locale,  # type: ignore[arg-type]
                status="failed",
                job_id=claim.job_id,
                failure_code="IDEMPOTENCY_REPLAY_UNAVAILABLE",
            )
        try:
            localized = await localize_public_content(
                self._language_model,
                source=source,
                target_locale=locale,
                prompt_version=self._prompt_version,
            )
            validate_localized_content(source, localized, locale)
            saved = await self._repository.save_localization(
                job_id=claim.job_id,
                version_id=version_id,
                locale=locale,
                content=localized.model_dump(mode="json"),
                source_hash=source_hash,
                prompt_version=self._prompt_version,
                model_name=self._model_name,
            )
            return LocalizationResult(
                locale=locale,  # type: ignore[arg-type]
                status="succeeded",
                localized_content_id=saved.id,
                job_id=claim.job_id,
            )
        except Exception as exc:
            failure_code = self._failure_code(exc)
            try:
                await self._repository.fail_job(claim.job_id, failure_code)
            except LocalizationRepositoryError:
                failure_code = "DATABASE_UNAVAILABLE"
            return LocalizationResult(
                locale=locale,  # type: ignore[arg-type]
                status="failed",
                job_id=claim.job_id,
                failure_code=failure_code,
            )

    @staticmethod
    def _failure_code(exc: Exception) -> str:
        if isinstance(exc, AIProviderTimeoutError):
            return "AI_PROVIDER_TIMEOUT"
        if isinstance(exc, AIProviderRateLimitError):
            return "AI_PROVIDER_RATE_LIMITED"
        if isinstance(exc, AIProviderTemporaryError):
            return "AI_PROVIDER_TEMPORARY_ERROR"
        if isinstance(exc, AIProviderPermanentError):
            return "AI_PROVIDER_PERMANENT_ERROR"
        if isinstance(exc, LocalizationPreservationError):
            return "LOCALIZATION_PRESERVATION_FAILED"
        if isinstance(exc, (AIProviderInvalidResponseError, ValidationError, ValueError)):
            return "AI_SCHEMA_INVALID"
        if isinstance(exc, LocalizationRepositoryError):
            return "DATABASE_UNAVAILABLE"
        return "LOCALIZATION_FAILED"

    @staticmethod
    def _failed(locale: str, code: str) -> LocalizationResult:
        return LocalizationResult(
            locale=locale,  # type: ignore[arg-type]
            status="failed",
            failure_code=code,
        )

    @staticmethod
    def _hash(value: dict) -> str:
        raw = json.dumps(value, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _organization_id(value: str | None) -> UUID:
        if value is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required.",
            )
        try:
            return UUID(value)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_INVALID",
                message="X-Organization-Id must be a UUID.",
            ) from exc

    @staticmethod
    def _forbidden() -> NoReturn:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="You do not have access to localize this listing.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="The database is unavailable.",
        ) from exc
