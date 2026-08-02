from fastapi import status

from app.ai.providers.base import (
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    LanguageModelProvider,
)
from app.ai.schemas.guidance import (
    ChangeSummaryRequest,
    ContractAssistantOutput,
    ContractAssistantRequest,
    ContractTranslationOutput,
    ContractTranslationRequest,
    RevisionGuidanceOutput,
    RevisionGuidanceRequest,
    RevisionSuggestionOutput,
    RevisionSuggestionRequest,
)
from app.ai.schemas.public_summary import PublicSummaryOutput
from app.ai.tasks.guidance import (
    generate_change_summary,
    generate_contract_assistant,
    generate_contract_translation,
    generate_revision_guidance,
    generate_revision_suggestion,
)
from app.core.errors import AppError


class AIGuidanceService:
    def __init__(self, provider: LanguageModelProvider, *, prompt_version: str) -> None:
        self._provider = provider
        self._prompt_version = prompt_version

    async def revision_guidance(self, payload: RevisionGuidanceRequest) -> RevisionGuidanceOutput:
        try:
            return await generate_revision_guidance(self._provider, payload, self._prompt_version)
        except Exception as exc:
            self._raise_provider_error(exc)

    async def revision_suggestion(
        self, payload: RevisionSuggestionRequest
    ) -> RevisionSuggestionOutput:
        try:
            return await generate_revision_suggestion(
                self._provider, payload, self._prompt_version
            )
        except Exception as exc:
            self._raise_provider_error(exc)

    async def change_summary(self, payload: ChangeSummaryRequest) -> PublicSummaryOutput:
        try:
            return await generate_change_summary(self._provider, payload, self._prompt_version)
        except Exception as exc:
            self._raise_provider_error(exc)

    async def contract_translation(
        self, payload: ContractTranslationRequest
    ) -> ContractTranslationOutput:
        try:
            translated = await generate_contract_translation(
                self._provider, payload, self._prompt_version
            )
            source_ids = [clause.id for clause in payload.clauses]
            translated_ids = [clause.id for clause in translated.clauses]
            if translated.locale != payload.target_locale or translated_ids != source_ids:
                raise ValueError("The translated contract changed its locale or clause references.")
            return translated
        except Exception as exc:
            self._raise_provider_error(exc)

    async def contract_assistant(
        self, payload: ContractAssistantRequest
    ) -> ContractAssistantOutput:
        try:
            result = await generate_contract_assistant(
                self._provider, payload, self._prompt_version
            )
            source_ids = {clause.id for clause in payload.clauses}
            finding_ids = [finding.clause_id for finding in result.findings]
            if len(finding_ids) != len(set(finding_ids)) or not set(finding_ids) <= source_ids:
                raise ValueError("The contract review changed or duplicated clause references.")
            return result
        except Exception as exc:
            self._raise_provider_error(exc)

    @staticmethod
    def _raise_provider_error(exc: Exception) -> None:
        if isinstance(exc, AIProviderTimeoutError):
            code, http_status = "AI_PROVIDER_TIMEOUT", status.HTTP_504_GATEWAY_TIMEOUT
        elif isinstance(exc, AIProviderRateLimitError):
            code, http_status = "AI_PROVIDER_RATE_LIMITED", status.HTTP_503_SERVICE_UNAVAILABLE
        elif isinstance(exc, AIProviderTemporaryError):
            code, http_status = "AI_PROVIDER_TEMPORARY_FAILURE", status.HTTP_503_SERVICE_UNAVAILABLE
        elif isinstance(exc, (AIProviderInvalidResponseError, ValueError)):
            code, http_status = "AI_SCHEMA_INVALID", status.HTTP_502_BAD_GATEWAY
        elif isinstance(exc, AIProviderError):
            code, http_status = "AI_PROVIDER_REJECTED_REQUEST", status.HTTP_502_BAD_GATEWAY
        else:
            code, http_status = "AI_GUIDANCE_FAILED", status.HTTP_502_BAD_GATEWAY
        raise AppError(
            status_code=http_status,
            code=code,
            message="AI guidance could not be generated.",
        ) from exc
