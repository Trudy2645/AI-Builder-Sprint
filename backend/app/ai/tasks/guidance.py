from app.ai.prompts.v1.guidance import (
    CHANGE_SUMMARY_SYSTEM_PROMPT,
    REVISION_GUIDANCE_SYSTEM_PROMPT,
)
from app.ai.providers.base import LanguageModelProvider
from app.ai.schemas.guidance import (
    ChangeSummaryRequest,
    RevisionGuidanceOutput,
    RevisionGuidanceRequest,
)
from app.ai.schemas.providers import LanguageModelRequest
from app.ai.schemas.public_summary import PublicSummaryOutput


async def generate_revision_guidance(
    provider: LanguageModelProvider,
    payload: RevisionGuidanceRequest,
    prompt_version: str,
) -> RevisionGuidanceOutput:
    return await provider.generate_structured(
        LanguageModelRequest(
            task_type="revision_draft",
            system_prompt=REVISION_GUIDANCE_SYSTEM_PROMPT,
            input_data=payload.model_dump(mode="json"),
            prompt_version=prompt_version,
            reasoning_effort="medium",
        ),
        RevisionGuidanceOutput,
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
