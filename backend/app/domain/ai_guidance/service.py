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
    RevisionGuidanceOutput,
    RevisionGuidanceRequest,
)
from app.ai.schemas.public_summary import PublicSummaryOutput
from app.ai.tasks.guidance import generate_change_summary, generate_revision_guidance
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

    async def change_summary(self, payload: ChangeSummaryRequest) -> PublicSummaryOutput:
        try:
            return await generate_change_summary(self._provider, payload, self._prompt_version)
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
