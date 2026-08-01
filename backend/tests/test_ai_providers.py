from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.ai.jobs import AIJobIdentity, can_transition_ai_job
from app.ai.providers.base import (
    AIProviderInvalidResponseError,
    AIProviderRateLimitError,
)
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.upstage import UpstageAIProvider
from app.ai.schemas import DocumentInput, LanguageModelRequest


class SummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str


def document() -> DocumentInput:
    return DocumentInput(
        filename="contract.pdf",
        mime_type="application/pdf",
        content=b"%PDF fake contract",
    )


def test_ai_job_identity_deduplicates_same_version_task_prompt() -> None:
    version_id = "a5000000-0000-0000-0000-000000000001"
    first = AIJobIdentity(
        task_type="contract_review",
        prompt_version="busan-link-v1",
        model_name="solar-pro3",
        listing_version_id=version_id,
        viewer_role="seller",
    )
    repeated = AIJobIdentity.model_validate(first.model_dump())
    buyer_view = first.model_copy(update={"viewer_role": "buyer"})

    assert first.idempotency_key() == repeated.idempotency_key()
    assert first.idempotency_key() != buyer_view.idempotency_key()
    assert can_transition_ai_job("queued", "processing") is True
    assert can_transition_ai_job("succeeded", "processing") is False


def provider(client: httpx.AsyncClient, *, max_retries: int = 3, sleeps=None):
    async def no_sleep(delay: float) -> None:
        if sleeps is not None:
            sleeps.append(delay)

    return UpstageAIProvider(
        api_key="test-key",
        document_base_url="https://api.upstage.test/v1",
        chat_base_url="https://api.upstage.test/v1",
        agent_base_url="https://api.upstage.test/v2",
        chat_model="solar-pro3",
        timeout_seconds=10,
        max_retries=max_retries,
        client=client,
        sleep=no_sleep,
    )


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic_and_validates_structured_output() -> None:
    fake = FakeAIProvider()
    fake.queue_structured_output("public_summary", {"summary": "핵심 계약 요약"})
    request = LanguageModelRequest(
        task_type="public_summary",
        system_prompt="Return a grounded summary.",
        input_data={"contract": "untrusted text"},
        prompt_version="busan-link-v1",
    )

    parsed = await fake.parse_document(document())
    extracted = await fake.extract_information(document(), parsed)
    generated = await fake.generate_structured(request, SummaryOutput)

    assert parsed.pages[0].page_number == 1
    assert extracted.price.missing is True
    assert extracted.liability.missing is True
    assert generated.summary == "핵심 계약 요약"
    assert fake.calls == [
        ("document_parse", "contract.pdf"),
        ("information_extract", "contract.pdf"),
        ("language_model", "public_summary"),
    ]


@pytest.mark.asyncio
async def test_upstage_retries_429_and_temporary_5xx_with_exponential_backoff() -> None:
    statuses = iter([429, 503, 200])
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status_code = next(statuses)
        payload: dict[str, Any] = {
            "content": {"markdown": "# 계약"},
            "elements": [
                {
                    "id": "clause-1",
                    "category": "paragraph",
                    "content": "제1조 계약의 목적",
                    "page": 1,
                }
            ],
        }
        return httpx.Response(status_code, request=request, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await provider(client, sleeps=sleeps).parse_document(document())

    assert result.markdown == "# 계약"
    assert result.pages[0].blocks[0].content == "제1조 계약의 목적"
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_upstage_stops_after_retry_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request, json={"error": "rate limited"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIProviderRateLimitError):
            await provider(client, max_retries=1).parse_document(document())


@pytest.mark.asyncio
async def test_upstage_rejects_invalid_structured_model_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": '{"unexpected": true}'}}]},
        )

    request = LanguageModelRequest(
        task_type="public_summary",
        system_prompt="Return JSON.",
        input_data={},
        prompt_version="busan-link-v1",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIProviderInvalidResponseError):
            await provider(client).generate_structured(request, SummaryOutput)
