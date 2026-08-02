from typing import Any

from app.ai.prompts.v1.public_summary import PUBLIC_SUMMARY_SYSTEM_PROMPT
from app.ai.providers.base import LanguageModelProvider
from app.ai.schemas.providers import LanguageModelRequest
from app.ai.schemas.public_summary import PublicSummaryOutput


async def generate_public_summary(
    language_model: LanguageModelProvider,
    *,
    listing: dict[str, Any],
    terms: dict[str, Any],
    clauses: list[dict[str, Any]],
    prompt_version: str,
) -> PublicSummaryOutput:
    return await language_model.generate_structured(
        LanguageModelRequest(
            task_type="public_summary",
            system_prompt=PUBLIC_SUMMARY_SYSTEM_PROMPT,
            input_data={"listing": listing, "terms": terms, "clauses": clauses},
            prompt_version=prompt_version,
            reasoning_effort="low",
        ),
        PublicSummaryOutput,
    )


__all__ = ["generate_public_summary"]
