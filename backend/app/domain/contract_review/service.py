from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Literal, NoReturn
from uuid import UUID

from fastapi import status
from pydantic import ValidationError

from app.ai.agents import ContractReviewAgent, ContractReviewAgentInvalidOutputError
from app.ai.prompts.v1.contract_review import CONTRACT_REVIEW_PROMPT_VERSION
from app.ai.providers.base import (
    AIProviderInvalidResponseError,
    AIProviderPermanentError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    FileSearchProvider,
    LanguageModelProvider,
)
from app.ai.tasks.contract_review_rules import review_contract_rules
from app.ai.tools.contract_review import ContractReviewToolRejectedError, ContractReviewTools
from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.rag.locator import EvidenceLocator
from app.repositories.contract_review import (
    ContractReviewIdempotencyConflictError,
    ContractReviewRepository,
    ContractReviewRepositoryError,
    ContractReviewTargetRecord,
    FindingActionConflictError,
    FindingActionContext,
    FindingActionNotFoundError,
    FindingActionVersionConflictError,
    FindingReviewJob,
    FindingSuggestionConflictError,
    StoredReviewRun,
)
from app.schemas.contract_review import (
    ContractReviewAccepted,
    ContractReviewFindingResponse,
    ContractReviewRequest,
    ContractReviewRunResponse,
    FindingApplyRequest,
    FindingApplyResponse,
    FindingDismissRequest,
    FindingDismissResponse,
)


@dataclass(frozen=True, slots=True)
class StartedContractReview:
    response: ContractReviewAccepted
    should_schedule: bool
    target: ContractReviewTargetRecord
    viewer_role: Literal["buyer", "seller"]


@dataclass(frozen=True, slots=True)
class ScheduledFindingReview:
    job: FindingReviewJob
    target: ContractReviewTargetRecord


@dataclass(frozen=True, slots=True)
class StartedFindingApply:
    response: FindingApplyResponse
    reviews: list[ScheduledFindingReview]


class ContractReviewService:
    def __init__(
        self,
        repository: ContractReviewRepository,
        language_model: LanguageModelProvider,
        file_search: FileSearchProvider,
        *,
        provider_name: str,
        model_name: str,
        prompt_version: str,
        official_vector_store_id: str | None,
        template_vector_store_id: str | None,
        case_vector_store_id: str | None = None,
        evidence_locator: EvidenceLocator | None = None,
        minimum_evidence_score: float = 0.3,
        max_iterations: int = 2,
    ) -> None:
        self._repository = repository
        self._language_model = language_model
        self._file_search = file_search
        self._provider_name = provider_name
        self._model_name = model_name
        self._prompt_version = f"{prompt_version}:{CONTRACT_REVIEW_PROMPT_VERSION}"
        self._official_vector_store_id = official_vector_store_id
        self._template_vector_store_id = template_vector_store_id
        self._case_vector_store_id = case_vector_store_id
        self._evidence_locator = evidence_locator
        self._minimum_evidence_score = minimum_evidence_score
        self._max_iterations = max_iterations

    async def start_listing_review(
        self,
        listing_id: UUID,
        payload: ContractReviewRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> StartedContractReview:
        organization_id = self._organization_id(organization_header)
        target = await self._listing_target(listing_id, payload.version_id)
        if target.seller_organization_id != organization_id or not await self._member(
            actor.id, organization_id
        ):
            self._forbidden()
        return await self._claim(target, payload, actor, idempotency_key)

    async def start_contract_review(
        self,
        contract_id: UUID,
        payload: ContractReviewRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> StartedContractReview:
        target = await self._contract_target(contract_id, payload.version_id)
        actual_role: Literal["buyer", "seller"]
        if target.buyer_user_id == actor.id and organization_header is None:
            actual_role = "buyer"
        else:
            organization_id = self._organization_id(organization_header)
            if target.seller_organization_id != organization_id or not await self._member(
                actor.id, organization_id
            ):
                self._forbidden()
            actual_role = "seller"
        if payload.viewer_role != actual_role:
            self._raise(
                status.HTTP_403_FORBIDDEN,
                "REVIEW_VIEWER_ROLE_FORBIDDEN",
                "The requested viewer role does not match the authenticated contract party.",
            )
        return await self._claim(target, payload, actor, idempotency_key)

    async def run(
        self,
        *,
        job_id: UUID,
        target: ContractReviewTargetRecord,
        viewer_role: Literal["buyer", "seller"],
    ) -> None:
        run_id: UUID | None = None
        try:
            rules = review_contract_rules(
                category=target.category, terms=target.terms, clauses=target.clauses
            )
            input_sha256 = self._hash(
                {
                    "target_type": target.target_type,
                    "version_id": str(target.version_id),
                    "viewer_role": viewer_role,
                    "category": target.category,
                    "terms": target.terms,
                    "clauses": [
                        {
                            "id": str(item.id),
                            "title": item.title,
                            "body": item.body,
                            "source_location": item.source_location,
                        }
                        for item in target.clauses
                    ],
                }
            )
            run_id = await self._repository.mark_processing(
                job_id=job_id,
                target=target,
                viewer_role=viewer_role,
                model_name=self._model_name,
                prompt_version=self._prompt_version,
                input_sha256=input_sha256,
                max_iterations=self._max_iterations,
            )
            tools = ContractReviewTools(
                clauses=target.clauses,
                category=target.category,
                provider=self._file_search,
                official_vector_store_id=self._official_vector_store_id,
                template_vector_store_id=self._template_vector_store_id,
                case_vector_store_id=self._case_vector_store_id,
                activity_subtype=target.terms.get("activity_subtype"),
                evidence_locator=self._evidence_locator,
                minimum_evidence_score=self._minimum_evidence_score,
                as_of=self._effective_date(target.terms),
                max_searches=self._max_iterations,
            )
            agent = ContractReviewAgent(
                self._language_model,
                tools,
                model_name=self._model_name,
                prompt_version=self._prompt_version,
                max_search_iterations=self._max_iterations,
            )
            result = await agent.run(
                target_type=target.target_type,
                target_id=target.version_id,
                viewer_role=viewer_role,
                category=target.category,
                clauses=target.clauses,
                terms=target.terms,
                rule_findings=rules,
            )
            await self._repository.complete_review(
                job_id=job_id,
                analysis_run_id=run_id,
                target=target,
                findings=result.findings,
                evidence=result.evidence,
                iterations_used=result.iterations_used,
                stop_reason=result.stop_reason,
                execution_metadata={
                    "schema_version": "contract-review-v1",
                    "tool_sequence": result.tool_sequence,
                    "search_count": result.iterations_used,
                    "rule_finding_count": len(rules),
                },
            )
        except Exception as exc:
            try:
                await self._repository.fail_review(
                    job_id=job_id,
                    analysis_run_id=run_id,
                    failure_code=self._failure_code(exc),
                )
            except ContractReviewRepositoryError:
                pass

    async def get_run(
        self,
        run_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> ContractReviewRunResponse:
        try:
            run = await self._repository.get_run(run_id)
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)
        if run is None:
            self._raise(status.HTTP_404_NOT_FOUND, "ANALYSIS_NOT_FOUND", "Analysis was not found.")
        await self._authorize_run(run, actor, organization_header)
        return self._run_response(run)

    @staticmethod
    def _effective_date(terms: dict) -> date:
        value = terms.get("service_start_date") or terms.get("start_date")
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                pass
        return date.today()

    async def apply_finding(
        self,
        finding_id: UUID,
        payload: FindingApplyRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> StartedFindingApply:
        context = await self._finding_context(finding_id)
        await self._authorize_finding_action(context, actor, organization_header)
        self._validate_idempotency_key(idempotency_key)
        request_hash = self._hash(
            {"finding_id": str(finding_id), **payload.model_dump(mode="json")}
        )
        try:
            applied = await self._repository.apply_finding(
                finding_id=finding_id,
                actor_user_id=actor.id,
                base_version_no=payload.base_version_no,
                suggested_text_hash=payload.suggested_text_hash,
                edited_text=payload.edited_text,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                provider=self._provider_name,
                model_name=self._model_name,
                prompt_version=self._prompt_version,
            )
        except ContractReviewIdempotencyConflictError as exc:
            self._raise(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was already used with another finding action.",
                exc,
            )
        except FindingActionNotFoundError as exc:
            self._finding_not_found(exc)
        except FindingActionConflictError as exc:
            self._finding_not_actionable(exc)
        except FindingActionVersionConflictError as exc:
            self._raise(
                status.HTTP_409_CONFLICT,
                "VERSION_CONFLICT",
                "The finding version is no longer the current version.",
                exc,
            )
        except FindingSuggestionConflictError as exc:
            self._raise(
                status.HTTP_409_CONFLICT,
                "SUGGESTED_TEXT_CONFLICT",
                "suggested_text_hash does not match the reviewed suggestion.",
                exc,
            )
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)

        reviews: list[ScheduledFindingReview] = []
        if not applied.replayed:
            target = await self._action_target(applied)
            reviews = [ScheduledFindingReview(job=job, target=target) for job in applied.jobs]
        return StartedFindingApply(
            response=FindingApplyResponse(
                finding_id=applied.finding_id,
                target_type=applied.target_type,
                resource_id=applied.resource_id,
                previous_version_id=applied.previous_version_id,
                version_id=applied.version_id,
                version_no=applied.version_no,
                analysis_job_ids=[job.job_id for job in applied.jobs],
                replayed=applied.replayed,
            ),
            reviews=reviews,
        )

    async def dismiss_finding(
        self,
        finding_id: UUID,
        payload: FindingDismissRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> FindingDismissResponse:
        context = await self._finding_context(finding_id)
        await self._authorize_finding_action(context, actor, organization_header)
        self._validate_idempotency_key(idempotency_key)
        request_hash = self._hash(
            {"finding_id": str(finding_id), **payload.model_dump(mode="json")}
        )
        try:
            dismissed = await self._repository.dismiss_finding(
                finding_id=finding_id,
                actor_user_id=actor.id,
                reason=payload.reason,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        except ContractReviewIdempotencyConflictError as exc:
            self._raise(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was already used with another finding action.",
                exc,
            )
        except FindingActionNotFoundError as exc:
            self._finding_not_found(exc)
        except FindingActionConflictError as exc:
            self._finding_not_actionable(exc)
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)
        return FindingDismissResponse(
            finding_id=dismissed.finding_id,
            replayed=dismissed.replayed,
        )

    async def _claim(
        self,
        target: ContractReviewTargetRecord,
        payload: ContractReviewRequest,
        actor: AuthenticatedUser,
        idempotency_key: str,
    ) -> StartedContractReview:
        if not idempotency_key.strip():
            self._raise(
                status.HTTP_400_BAD_REQUEST,
                "VALIDATION_ERROR",
                "Idempotency-Key cannot be blank.",
            )
        request_hash = self._hash(
            {
                "version_id": str(payload.version_id),
                "viewer_role": payload.viewer_role,
                "analysis_types": sorted(set(payload.analysis_types)),
                "model_name": self._model_name,
                "prompt_version": self._prompt_version,
            }
        )
        try:
            claim = await self._repository.claim_review(
                target=target,
                actor_user_id=actor.id,
                viewer_role=payload.viewer_role,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                provider=self._provider_name,
                model_name=self._model_name,
                prompt_version=self._prompt_version,
            )
        except ContractReviewIdempotencyConflictError as exc:
            self._raise(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key was already used with another review request.",
                exc,
            )
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)
        return StartedContractReview(
            response=ContractReviewAccepted(
                job_id=claim.job_id,
                status=claim.status,  # type: ignore[arg-type]
                max_iterations=self._max_iterations,
            ),
            should_schedule=claim.should_schedule,
            target=target,
            viewer_role=payload.viewer_role,
        )

    async def _authorize_run(
        self,
        run: StoredReviewRun,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> None:
        if run.target_type == "listing_version":
            target = await self._listing_target(run.resource_id, run.target_id)
            organization_id = self._organization_id(organization_header)
            if target.seller_organization_id != organization_id or not await self._member(
                actor.id, organization_id
            ):
                self._forbidden()
            return
        target = await self._contract_target(run.resource_id, run.target_id)
        if run.viewer_role == "buyer":
            if target.buyer_user_id != actor.id:
                self._forbidden()
            return
        organization_id = self._organization_id(organization_header)
        if target.seller_organization_id != organization_id or not await self._member(
            actor.id, organization_id
        ):
            self._forbidden()

    async def _finding_context(self, finding_id: UUID) -> FindingActionContext:
        try:
            context = await self._repository.get_finding_action_context(finding_id)
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)
        if context is None:
            self._finding_not_found()
        return context

    async def _authorize_finding_action(
        self,
        context: FindingActionContext,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> None:
        organization_id = self._organization_id(organization_header)
        if context.seller_organization_id != organization_id or not await self._member(
            actor.id, organization_id
        ):
            self._forbidden()

    async def _action_target(self, applied) -> ContractReviewTargetRecord:
        if applied.target_type == "listing_version":
            return await self._listing_target(applied.resource_id, applied.version_id)
        return await self._contract_target(applied.resource_id, applied.version_id)

    async def _listing_target(
        self, listing_id: UUID, version_id: UUID
    ) -> ContractReviewTargetRecord:
        try:
            target = await self._repository.get_listing_target(listing_id, version_id)
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)
        if target is None:
            self._raise(status.HTTP_404_NOT_FOUND, "VERSION_NOT_FOUND", "Version was not found.")
        return target

    async def _contract_target(
        self, contract_id: UUID, version_id: UUID
    ) -> ContractReviewTargetRecord:
        try:
            target = await self._repository.get_contract_target(contract_id, version_id)
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)
        if target is None:
            self._raise(status.HTTP_404_NOT_FOUND, "VERSION_NOT_FOUND", "Version was not found.")
        return target

    async def _member(self, user_id: UUID, organization_id: UUID) -> bool:
        try:
            return await self._repository.is_seller_member(user_id, organization_id)
        except ContractReviewRepositoryError as exc:
            self._database_unavailable(exc)

    @staticmethod
    def _run_response(run: StoredReviewRun) -> ContractReviewRunResponse:
        return ContractReviewRunResponse(
            id=run.id,
            job_id=run.job_id,
            target_type=run.target_type,  # type: ignore[arg-type]
            target_id=run.target_id,
            viewer_role=run.viewer_role,  # type: ignore[arg-type]
            status=run.status,  # type: ignore[arg-type]
            execution_mode=run.execution_mode,  # type: ignore[arg-type]
            agent_name=run.agent_name,  # type: ignore[arg-type]
            max_iterations=run.max_iterations,  # type: ignore[arg-type]
            iterations_used=run.iterations_used,
            stop_reason=run.stop_reason,  # type: ignore[arg-type]
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            findings=[
                ContractReviewFindingResponse(
                    id=finding.id,
                    clause_id=finding.clause_id,
                    category=finding.category,
                    severity=finding.severity,  # type: ignore[arg-type]
                    importance=finding.importance,  # type: ignore[arg-type]
                    title=finding.title,
                    explanation=finding.explanation,
                    suggested_text=finding.suggested_text,
                    suggested_text_hash=(
                        f"sha256:{finding.suggested_text_sha256}"
                        if finding.suggested_text_sha256
                        else None
                    ),
                    grounding_status=finding.grounding_status,  # type: ignore[arg-type]
                    confidence=finding.confidence,
                    source_location=finding.source_location,
                    evidence=finding.evidence,
                    disclaimer=finding.disclaimer,
                    is_public=finding.is_public,
                    viewer_role=run.viewer_role,
                    model_name=run.model_name,
                    prompt_version=run.prompt_version,
                )
                for finding in run.findings
            ],
        )

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
    def _hash(value: dict) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _validate_idempotency_key(value: str) -> None:
        if not value.strip():
            ContractReviewService._raise(
                status.HTTP_400_BAD_REQUEST,
                "VALIDATION_ERROR",
                "Idempotency-Key cannot be blank.",
            )

    @staticmethod
    def _finding_not_found(cause: Exception | None = None) -> NoReturn:
        ContractReviewService._raise(
            status.HTTP_404_NOT_FOUND,
            "FINDING_NOT_FOUND",
            "Finding was not found.",
            cause,
        )

    @staticmethod
    def _finding_not_actionable(cause: Exception | None = None) -> NoReturn:
        ContractReviewService._raise(
            status.HTTP_409_CONFLICT,
            "FINDING_NOT_ACTIONABLE",
            "Only an open finding with suggested text can be acted on.",
            cause,
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
        if isinstance(
            exc,
            (
                AIProviderInvalidResponseError,
                ContractReviewToolRejectedError,
                ContractReviewAgentInvalidOutputError,
                ValidationError,
            ),
        ):
            return "AI_REVIEW_INVALID"
        return "AI_REVIEW_FAILED"

    @staticmethod
    def _forbidden() -> NoReturn:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="You do not have access to this analysis.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="The database is unavailable.",
        ) from exc

    @staticmethod
    def _raise(
        status_code: int, code: str, message: str, cause: Exception | None = None
    ) -> NoReturn:
        error = AppError(status_code=status_code, code=code, message=message)
        if cause:
            raise error from cause
        raise error
