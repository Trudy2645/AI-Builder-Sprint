from __future__ import annotations

import hashlib
import json
import re
from typing import Any, NoReturn
from uuid import UUID

from fastapi import status

from app.ai.providers.base import (
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderPermanentError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    FileSearchProvider,
    LanguageModelProvider,
)
from app.ai.tasks.contract_generation import generate_contract_draft
from app.ai.tasks.public_summary import generate_public_summary
from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.repositories.contract_generation import (
    ContractGenerationIdempotencyConflictError,
    ContractGenerationInProgressError,
    ContractGenerationInputRecord,
    ContractGenerationNotFoundError,
    ContractGenerationRecord,
    ContractGenerationRepository,
    ContractGenerationRepositoryError,
    ContractGenerationStateConflictError,
    ContractGenerationVersionConflictError,
    NewGeneratedClause,
    json_safe_terms,
)
from app.schemas.contract_generation import (
    ContractGenerationRequest,
    ContractGenerationResponse,
    GeneratedListingClause,
)

_REQUIRED_TERMS = (
    "service_start_date",
    "service_end_date",
    "base_price_amount_minor",
    "currency",
    "price_unit",
    "cancellation_policy",
    "no_show_policy",
    "settlement_policy",
)
_PRESERVED_TEXT_TERMS = ("supply_quantity_description",)
_PRESERVED_UNIT_TERMS = ("currency", "price_unit", "quantity_unit")
_PRESERVED_NUMBER_TERMS = (
    "supply_quantity",
    "minimum_quantity",
    "maximum_quantity",
    "people_per_unit",
    "base_price_amount_minor",
    "minimum_people",
    "maximum_people",
)
_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?")
_ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_ARTICLE_PREFIX = re.compile(r"^(?:제\s*\d+\s*조|article\s+\d+)\s*[:.·\-]?\s*", re.IGNORECASE)


class ContractGenerationService:
    def __init__(
        self,
        repository: ContractGenerationRepository,
        language_model: LanguageModelProvider,
        file_search: FileSearchProvider,
        *,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        template_vector_store_id: str | None,
    ) -> None:
        self._repository = repository
        self._language_model = language_model
        self._file_search = file_search
        self._provider_name = provider_name
        self._model_name = model_name
        self._prompt_version = prompt_version
        self._template_vector_store_id = template_vector_store_id

    async def generate(
        self,
        listing_id: UUID,
        payload: ContractGenerationRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> ContractGenerationResponse:
        organization_id = await self._authorize(actor, organization_header)
        listing = await self._get_listing(listing_id, organization_id)
        self._validate_required_input(listing)
        request_hash = self._request_hash(listing_id, payload.base_version_no)
        try:
            claim = await self._repository.claim_generation(
                listing_id=listing.id,
                organization_id=organization_id,
                actor_user_id=actor.id,
                expected_version_no=payload.base_version_no,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                provider=self._provider_name,
                model_name=self._model_name,
                prompt_version=self._prompt_version,
            )
        except ContractGenerationIdempotencyConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_CONFLICT",
                message="The Idempotency-Key was already used with different input.",
            ) from exc
        except ContractGenerationInProgressError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_IN_PROGRESS",
                message="The same contract generation request is still processing.",
            ) from exc
        except ContractGenerationVersionConflictError as exc:
            self._version_conflict(exc)
        except ContractGenerationStateConflictError as exc:
            self._invalid_transition(exc)
        except ContractGenerationNotFoundError as exc:
            self._not_found(exc)
        except ContractGenerationRepositoryError as exc:
            self._database_unavailable(exc)
        if claim.cached is not None:
            return self._response(claim.cached)
        if claim.job_id is None:
            raise AssertionError("A new generation claim must contain a job ID.")
        job_id = claim.job_id
        try:
            terms = json_safe_terms(listing.terms)
            draft = await generate_contract_draft(
                language_model=self._language_model,
                file_search=self._file_search,
                listing={
                    "title": listing.title,
                    "seller": listing.organization_name,
                    "category": listing.category,
                    "district": listing.district,
                    "language": listing.language,
                },
                terms=terms,
                prompt_version=self._prompt_version,
                template_vector_store_id=self._template_vector_store_id,
            )
            clauses = [
                NewGeneratedClause(
                    clause.clause_key,
                    self._clean_title(clause.title),
                    clause.body,
                )
                for clause in draft.clauses
            ]
            self._validate_preserved_terms(
                terms,
                {"clauses": [{"title": clause.title, "body": clause.body} for clause in clauses]},
            )
            body = "\n\n".join(
                f"제{index}조 {clause.title}\n{clause.body}"
                for index, clause in enumerate(clauses, start=1)
            )
            summary = await generate_public_summary(
                self._language_model,
                listing={
                    "title": listing.title,
                    "seller": listing.organization_name,
                    "category": listing.category,
                    "district": listing.district,
                },
                terms=terms,
                clauses=[{"title": clause.title, "body": clause.body} for clause in clauses],
                prompt_version=self._prompt_version,
            )
        except Exception as exc:
            await self._fail_and_raise(listing, job_id, idempotency_key, exc)
        try:
            record = await self._repository.complete_generation(
                listing=listing,
                actor_user_id=actor.id,
                job_id=job_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                clauses=clauses,
                body=body,
                ai_summary="\n".join(summary.lines),
                result_metadata={
                    "clause_count": len(clauses),
                    "public_summary_line_count": len(summary.lines),
                    "template_context_used": bool(self._template_vector_store_id),
                },
            )
            return self._response(record)
        except ContractGenerationVersionConflictError as exc:
            await self._safe_fail(listing, job_id, idempotency_key, "VERSION_CONFLICT")
            self._version_conflict(exc)
        except ContractGenerationStateConflictError as exc:
            await self._safe_fail(listing, job_id, idempotency_key, "INVALID_STATE_TRANSITION")
            self._invalid_transition(exc)
        except ContractGenerationIdempotencyConflictError as exc:
            await self._safe_fail(listing, job_id, idempotency_key, "IDEMPOTENCY_CONFLICT")
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_CONFLICT",
                message="The generation request could not be committed idempotently.",
            ) from exc
        except ContractGenerationNotFoundError as exc:
            await self._safe_fail(listing, job_id, idempotency_key, "LISTING_NOT_FOUND")
            self._not_found(exc)
        except ContractGenerationRepositoryError as exc:
            await self._safe_fail(listing, job_id, idempotency_key, "DATABASE_WRITE_FAILED")
            self._database_unavailable(exc)

    async def _fail_and_raise(
        self,
        listing: ContractGenerationInputRecord,
        job_id: UUID,
        idempotency_key: str,
        exc: Exception,
    ) -> NoReturn:
        failure_code, error = self._provider_failure(exc)
        await self._safe_fail(listing, job_id, idempotency_key, failure_code)
        raise error from exc

    async def _safe_fail(
        self,
        listing: ContractGenerationInputRecord,
        job_id: UUID,
        idempotency_key: str,
        failure_code: str,
    ) -> None:
        try:
            await self._repository.fail_generation(
                listing=listing,
                job_id=job_id,
                idempotency_key=idempotency_key,
                failure_code=failure_code,
            )
        except ContractGenerationRepositoryError as exc:
            self._database_unavailable(exc)

    async def _authorize(self, actor: AuthenticatedUser, organization_header: str | None) -> UUID:
        if organization_header is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required for seller organization APIs.",
            )
        try:
            organization_id = UUID(organization_header)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="X-Organization-Id must be a UUID.",
            ) from exc
        try:
            membership = await self._repository.get_membership(actor.id, organization_id)
        except ContractGenerationRepositoryError as exc:
            self._database_unavailable(exc)
        if membership is None or membership.organization_type != "seller":
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ORG_ACCESS_DENIED",
                message="You do not have access to this seller organization.",
            )
        return organization_id

    async def _get_listing(
        self, listing_id: UUID, organization_id: UUID
    ) -> ContractGenerationInputRecord:
        try:
            listing = await self._repository.get_input(listing_id)
        except ContractGenerationRepositoryError as exc:
            self._database_unavailable(exc)
        if listing is None or listing.seller_organization_id != organization_id:
            self._not_found()
        return listing

    @staticmethod
    def _validate_required_input(listing: ContractGenerationInputRecord) -> None:
        missing = [
            field
            for field in _REQUIRED_TERMS
            if (value := listing.terms.get(field)) is None
            or (isinstance(value, str) and not value.strip())
        ]
        if (
            not listing.terms.get("supply_quantity_description")
            and listing.terms.get("supply_quantity") is None
        ):
            missing.append("supply_quantity_description")
        for field, value in (
            ("title", listing.title),
            ("district", listing.district),
            ("seller", listing.organization_name),
        ):
            if not value.strip():
                missing.insert(0, field)
        if missing:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="AI_INPUT_INSUFFICIENT",
                message="Required listing terms are missing for contract generation.",
                details={"missing_fields": missing},
            )

    @classmethod
    def _validate_preserved_terms(cls, terms: dict[str, Any], generated: dict[str, Any]) -> None:
        generated_text = "\n".join(
            f"{clause['title']}\n{clause['body']}" for clause in generated["clauses"]
        )
        input_text = json.dumps(terms, ensure_ascii=False, sort_keys=True)
        allowed_numbers = cls._numbers(input_text)
        generated_numbers = cls._numbers(generated_text)
        if not generated_numbers.issubset(allowed_numbers):
            raise AIProviderInvalidResponseError
        allowed_dates = set(_ISO_DATE.findall(input_text))
        generated_dates = set(_ISO_DATE.findall(generated_text))
        if not generated_dates.issubset(allowed_dates):
            raise AIProviderInvalidResponseError
        for field in ("service_start_date", "service_end_date"):
            value = terms.get(field)
            if value is not None and str(value) not in generated_text:
                raise AIProviderInvalidResponseError
        for field in _PRESERVED_NUMBER_TERMS:
            value = terms.get(field)
            if value is not None and cls._normalize_number(str(value)) not in generated_numbers:
                raise AIProviderInvalidResponseError
        for field in (*_PRESERVED_TEXT_TERMS, *_PRESERVED_UNIT_TERMS):
            value = terms.get(field)
            if isinstance(value, str) and value.strip() and value not in generated_text:
                raise AIProviderInvalidResponseError

    @classmethod
    def _numbers(cls, value: str) -> set[str]:
        return {cls._normalize_number(match) for match in _NUMBER.findall(value)}

    @staticmethod
    def _normalize_number(value: str) -> str:
        normalized = value.replace(",", "")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized

    @staticmethod
    def _clean_title(value: str) -> str:
        cleaned = _ARTICLE_PREFIX.sub("", value).strip()
        if not cleaned:
            raise AIProviderInvalidResponseError
        return cleaned

    def _request_hash(self, listing_id: UUID, base_version_no: int) -> str:
        canonical = json.dumps(
            {
                "listing_id": str(listing_id),
                "base_version_no": base_version_no,
                "model_name": self._model_name,
                "prompt_version": self._prompt_version,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _response(record: ContractGenerationRecord) -> ContractGenerationResponse:
        return ContractGenerationResponse(
            listing_id=record.listing_id,
            job_id=record.job_id,
            listing_version_id=record.listing_version_id,
            version_no=record.version_no,
            status="ready",
            clauses=[
                GeneratedListingClause(
                    id=clause.id,
                    clause_order=clause.clause_order,
                    clause_key=clause.clause_key,
                    title=clause.title,
                    body=clause.body,
                )
                for clause in record.clauses
            ],
        )

    @staticmethod
    def _provider_failure(exc: Exception) -> tuple[str, AppError]:
        if isinstance(exc, AIProviderTimeoutError):
            return "AI_PROVIDER_TIMEOUT", AppError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="AI_PROVIDER_TIMEOUT",
                message="The AI provider timed out.",
            )
        if isinstance(exc, AIProviderRateLimitError):
            return "AI_PROVIDER_RATE_LIMITED", AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="AI_PROVIDER_RATE_LIMITED",
                message="The AI provider is temporarily rate limited.",
            )
        if isinstance(exc, AIProviderTemporaryError):
            return "AI_PROVIDER_TEMPORARY_FAILURE", AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="AI_PROVIDER_TEMPORARY_FAILURE",
                message="The AI provider is temporarily unavailable.",
            )
        if isinstance(exc, AIProviderPermanentError):
            return "AI_PROVIDER_REJECTED_REQUEST", AppError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="AI_PROVIDER_REJECTED_REQUEST",
                message="The AI provider rejected the generation request.",
            )
        if isinstance(exc, (AIProviderInvalidResponseError, AIProviderError)):
            return "AI_GENERATION_INVALID", AppError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="AI_GENERATION_INVALID",
                message="The generated contract did not pass schema or invariant validation.",
            )
        if isinstance(
            exc,
            (
                ContractGenerationVersionConflictError,
                ContractGenerationStateConflictError,
                ContractGenerationIdempotencyConflictError,
                ContractGenerationNotFoundError,
                ContractGenerationRepositoryError,
            ),
        ):
            return "DATABASE_WRITE_FAILED", AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="DATABASE_UNAVAILABLE",
                message="Database connection is unavailable.",
            )
        return "AI_GENERATION_FAILED", AppError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="AI_GENERATION_FAILED",
            message="Contract generation failed.",
        )

    @staticmethod
    def _not_found(exc: Exception | None = None) -> NoReturn:
        error = AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="LISTING_NOT_FOUND",
            message="Seller listing was not found.",
        )
        if exc is None:
            raise error
        raise error from exc

    @staticmethod
    def _version_conflict(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="VERSION_CONFLICT",
            message="The listing version changed before generation started.",
        ) from exc

    @staticmethod
    def _invalid_transition(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message="A contract can only be generated from a draft listing.",
        ) from exc

    @staticmethod
    def _database_unavailable(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
