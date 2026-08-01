import json
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
from app.ai.schemas import (
    DocumentInput,
    DocumentParseResult,
    LanguageModelRequest,
    ParsedBlock,
    ParsedPage,
)


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
                    "coordinates": [
                        {"x": 0.1, "y": 0.2},
                        {"x": 0.5, "y": 0.2},
                        {"x": 0.5, "y": 0.4},
                        {"x": 0.1, "y": 0.4},
                    ],
                }
            ],
        }
        return httpx.Response(status_code, request=request, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await provider(client, sleeps=sleeps).parse_document(document())

    assert result.markdown == "# 계약"
    assert result.pages[0].blocks[0].content == "제1조 계약의 목적"
    assert result.pages[0].blocks[0].bbox is not None
    assert result.pages[0].blocks[0].bbox.width == pytest.approx(0.4)
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


@pytest.mark.asyncio
async def test_upstage_maps_universal_extraction_values_and_provenance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/information-extraction"
        assert request.headers["content-type"] == "application/json"
        body = request.read()
        request_json = httpx.Response(200, content=body).json()
        assert request_json["model"] == "information-extract"
        assert request_json["messages"][0]["content"][0]["image_url"]["url"].startswith(
            "data:application/octet-stream;base64,"
        )
        assert (
            "price_amount_minor"
            in request_json["response_format"]["json_schema"]["schema"]["properties"]
        )
        assert request_json["location"] is True
        assert request_json["confidence"] is True
        return httpx.Response(
            200,
            request=request,
            headers={"x-request-id": "extract-request"},
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"price_amount_minor":145000,"price_currency":"KRW"}',
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "additional_values",
                                        "arguments": json.dumps(
                                            {
                                                "additional_values": {
                                                    "price_amount_minor": {
                                                        "confidence": "high",
                                                        "page": 2,
                                                        "coordinates": [
                                                            {"x": 0.1, "y": 0.2},
                                                            {"x": 0.4, "y": 0.2},
                                                            {"x": 0.4, "y": 0.3},
                                                            {"x": 0.1, "y": 0.3},
                                                        ],
                                                    },
                                                    "price_currency": {
                                                        "confidence": "low",
                                                        "page": 2,
                                                    },
                                                }
                                            }
                                        ),
                                    }
                                }
                            ],
                        }
                    }
                ]
            },
        )

    parsed = DocumentParseResult(
        pages=[
            ParsedPage(
                page_number=2,
                blocks=[
                    ParsedBlock(
                        block_id="price",
                        block_type="paragraph",
                        content="객실당 145,000원 (KRW)",
                        page_number=2,
                    )
                ],
            )
        ]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await provider(client).extract_information(document(), parsed)

    amount = result.price.fields["amount_minor"]
    assert amount.value == 145000
    assert amount.confidence == 1.0
    assert amount.source_page == 2
    assert amount.source_quote == "객실당 145,000원 (KRW)"
    assert amount.bbox is not None
    assert amount.bbox.model_dump() == {
        "x": 0.1,
        "y": 0.2,
        "width": pytest.approx(0.3),
        "height": pytest.approx(0.1),
    }
    assert result.price.fields["currency"].confidence == 0.0
    assert result.refund.missing is True
    assert result.provider_request_id == "extract-request"
