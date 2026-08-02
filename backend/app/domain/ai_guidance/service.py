from fastapi import status

from app.ai.providers.base import (
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    FileSearchProvider,
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
from app.ai.schemas.providers import FileSearchRequest
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
    def __init__(
        self,
        provider: LanguageModelProvider,
        *,
        prompt_version: str,
        file_search_provider: FileSearchProvider | None = None,
        official_vector_store_id: str | None = None,
        template_vector_store_id: str | None = None,
        case_vector_store_id: str | None = None,
        minimum_evidence_score: float = 0.3,
    ) -> None:
        self._provider = provider
        self._prompt_version = prompt_version
        self._file_search_provider = file_search_provider
        self._revision_vector_stores = (
            ("official", official_vector_store_id),
            ("template", template_vector_store_id),
            ("case", case_vector_store_id),
        )
        self._minimum_evidence_score = minimum_evidence_score

    async def revision_guidance(self, payload: RevisionGuidanceRequest) -> RevisionGuidanceOutput:
        try:
            result = await generate_revision_guidance(
                self._provider,
                payload,
                self._prompt_version,
                await self._revision_rag_context(payload),
            )
            source_ids = [item.id for item in payload.items]
            result_ids = [item.id for item in result.items]
            if result_ids != source_ids:
                raise ValueError("The revision guidance changed or reordered item references.")
            return result
        except Exception as exc:
            self._raise_provider_error(exc)

    async def _revision_rag_context(
        self, payload: RevisionGuidanceRequest
    ) -> list[dict[str, object]]:
        if self._file_search_provider is None:
            return []
        query = "\n".join(
            f"{item.clause_title}: {item.reason}\n요청 문구: {item.requested_text}"
            for item in payload.items
        )[:2000]
        context: list[dict[str, object]] = []
        for corpus, vector_store_id in self._revision_vector_stores:
            if not vector_store_id:
                continue
            try:
                result = await self._file_search_provider.search_files(
                    FileSearchRequest(
                        query=query,
                        vector_store_id=vector_store_id,
                        top_k=3,
                    )
                )
            except Exception:
                # Retrieval is supporting context; guidance should survive one failed store.
                continue
            for hit in result.hits:
                if hit.score is not None and hit.score < self._minimum_evidence_score:
                    continue
                context.append(
                    {
                        "corpus": corpus,
                        "score": hit.score,
                        "excerpt": hit.excerpt[:1200],
                    }
                )
        return context[:9]

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
