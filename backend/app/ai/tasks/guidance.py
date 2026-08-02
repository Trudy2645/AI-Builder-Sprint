from app.ai.prompts.v1.guidance import (
    CHANGE_SUMMARY_SYSTEM_PROMPT,
    CONTRACT_ASSISTANT_SYSTEM_PROMPT,
    CONTRACT_TRANSLATION_SYSTEM_PROMPT,
    REVISION_GUIDANCE_SYSTEM_PROMPT,
    REVISION_SUGGESTION_SYSTEM_PROMPT,
)
from app.ai.providers.base import LanguageModelProvider
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
from app.ai.schemas.providers import LanguageModelRequest
from app.ai.schemas.public_summary import PublicSummaryOutput


async def generate_revision_guidance(
    provider: LanguageModelProvider,
    payload: RevisionGuidanceRequest,
    prompt_version: str,
    rag_context: list[dict[str, object]] | None = None,
) -> RevisionGuidanceOutput:
    return await provider.generate_structured(
        LanguageModelRequest(
            task_type="revision_draft",
            system_prompt=REVISION_GUIDANCE_SYSTEM_PROMPT,
            input_data={
                **payload.model_dump(mode="json"),
                "rag_context": rag_context or [],
            },
            prompt_version=f"{prompt_version}:seller-revision-guidance-v2",
            reasoning_effort="medium",
        ),
        RevisionGuidanceOutput,
    )


async def generate_revision_suggestion(
    provider: LanguageModelProvider,
    payload: RevisionSuggestionRequest,
    prompt_version: str,
) -> RevisionSuggestionOutput:
    return await provider.generate_structured(
        LanguageModelRequest(
            task_type="revision_draft",
            system_prompt=REVISION_SUGGESTION_SYSTEM_PROMPT,
            input_data=payload.model_dump(mode="json"),
            prompt_version=f"{prompt_version}:revision-suggestion-v1",
            reasoning_effort="medium",
        ),
        RevisionSuggestionOutput,
    )


async def generate_change_summary(
    provider: LanguageModelProvider,
    payload: ChangeSummaryRequest,
    prompt_version: str,
) -> PublicSummaryOutput:
    return await provider.generate_structured(
        LanguageModelRequest(
            task_type="public_summary",
            system_prompt=CHANGE_SUMMARY_SYSTEM_PROMPT,
            input_data=payload.model_dump(mode="json"),
            prompt_version=prompt_version,
            reasoning_effort="low",
        ),
        PublicSummaryOutput,
    )


async def generate_contract_translation(
    provider: LanguageModelProvider,
    payload: ContractTranslationRequest,
    prompt_version: str,
) -> ContractTranslationOutput:
    return await provider.generate_structured(
        LanguageModelRequest(
            task_type="localize_explain",
            system_prompt=CONTRACT_TRANSLATION_SYSTEM_PROMPT,
            input_data=payload.model_dump(mode="json"),
            prompt_version=f"{prompt_version}:contract-translation-v1",
            reasoning_effort="low",
        ),
        ContractTranslationOutput,
    )


async def generate_contract_assistant(
    provider: LanguageModelProvider,
    payload: ContractAssistantRequest,
    prompt_version: str,
) -> ContractAssistantOutput:
    return await provider.generate_structured(
        LanguageModelRequest(
            task_type="contract_review",
            system_prompt=CONTRACT_ASSISTANT_SYSTEM_PROMPT,
            input_data=payload.model_dump(mode="json"),
            prompt_version=f"{prompt_version}:buyer-contract-assistant-v1",
            reasoning_effort="medium",
        ),
        ContractAssistantOutput,
    )
