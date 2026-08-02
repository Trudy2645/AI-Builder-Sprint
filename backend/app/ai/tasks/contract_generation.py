from __future__ import annotations

from typing import Any

from app.ai.prompts.v1.contract_generation import CONTRACT_GENERATION_SYSTEM_PROMPT
from app.ai.providers.base import FileSearchProvider, LanguageModelProvider
from app.ai.schemas import (
    FileSearchRequest,
    GeneratedContractDraft,
    LanguageModelRequest,
)


async def generate_contract_draft(
    *,
    language_model: LanguageModelProvider,
    file_search: FileSearchProvider,
    listing: dict[str, Any],
    terms: dict[str, Any],
    prompt_version: str,
    template_vector_store_id: str | None,
) -> GeneratedContractDraft:
    template_context: list[dict[str, Any]] = []
    if template_vector_store_id:
        result = await file_search.search_files(
            FileSearchRequest(
                vector_store_id=template_vector_store_id,
                query=(
                    f"{listing['category']} 관광 공급 계약 템플릿 "
                    "가격 기간 수량 취소 노쇼 정산 안전 책임"
                ),
                filters={
                    "source_type": "approved_template",
                    "contract_category": listing["category"],
                    "party_type": "B2C_individual",
                },
                top_k=5,
            )
        )
        template_context = [
            {
                "file_id": hit.file_id,
                "chunk_id": hit.chunk_id,
                "excerpt": hit.excerpt[:2000],
                "metadata": hit.metadata,
                "usage": "drafting_reference_not_legal_evidence",
            }
            for hit in result.hits
            if hit.metadata.get("source_type") == "approved_template"
        ]
    return await language_model.generate_structured(
        LanguageModelRequest(
            task_type="contract_generate",
            system_prompt=CONTRACT_GENERATION_SYSTEM_PROMPT,
            input_data={
                "listing": listing,
                "terms": terms,
                "approved_template_context": template_context,
            },
            prompt_version=prompt_version,
            reasoning_effort="medium",
        ),
        GeneratedContractDraft,
    )


__all__ = ["generate_contract_draft"]
