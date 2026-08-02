from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeAIProvider
from app.ai.schemas.providers import FileSearchHit, FileSearchResult
from app.api.dependencies import get_ai_guidance_service
from app.core.auth import get_current_user
from app.domain.ai_guidance.service import AIGuidanceService
from app.integrations.auth import AuthenticatedUser


def test_translates_contract_title_and_clauses(app: FastAPI) -> None:
    provider = FakeAIProvider()
    provider.queue_structured_output(
        "localize_explain",
        {
            "locale": "en-US",
            "title": "Busan Accommodation Contract",
            "clauses": [
                {
                    "id": "clause-1",
                    "title": "Cancellation",
                    "body": "Cancellation is free up to seven days before use.",
                }
            ],
        },
    )
    service = AIGuidanceService(provider, prompt_version="busan-link-v1")
    app.dependency_overrides[get_ai_guidance_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        UUID("a1000000-0000-0000-0000-000000000001"),
        "buyer@example.test",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai-guidance/contract-translation",
            headers={"Idempotency-Key": "translate-contract-en"},
            json={
                "target_locale": "en-US",
                "title": "부산 숙박 계약",
                "clauses": [
                    {
                        "id": "clause-1",
                        "title": "취소 조건",
                        "body": "이용 7일 전까지 무료 취소할 수 있습니다.",
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Busan Accommodation Contract"
    assert provider.structured_requests[0].task_type == "localize_explain"
    assert provider.structured_requests[0].reasoning_effort == "low"


def test_rejects_translation_that_changes_clause_references(app: FastAPI) -> None:
    provider = FakeAIProvider()
    provider.queue_structured_output(
        "localize_explain",
        {
            "locale": "ja-JP",
            "title": "釜山宿泊契約",
            "clauses": [
                {"id": "changed-id", "title": "取消条件", "body": "本文"}
            ],
        },
    )
    service = AIGuidanceService(provider, prompt_version="busan-link-v1")
    app.dependency_overrides[get_ai_guidance_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        UUID("a1000000-0000-0000-0000-000000000001"),
        "buyer@example.test",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai-guidance/contract-translation",
            headers={"Idempotency-Key": "translate-contract-ja"},
            json={
                "target_locale": "ja-JP",
                "title": "부산 숙박 계약",
                "clauses": [
                    {"id": "clause-1", "title": "취소 조건", "body": "본문"}
                ],
            },
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_SCHEMA_INVALID"


def test_reviews_public_contract_for_buyer(app: FastAPI) -> None:
    provider = FakeAIProvider()
    provider.queue_structured_output(
        "contract_review",
        {
            "findings": [
                {
                    "clause_id": "clause-1",
                    "severity": "high",
                    "explanation": "취소 수수료 기준을 확인해야 합니다.",
                    "suggested_text": "취소 시점별 환불 비율을 명확히 기재해 주세요.",
                }
            ]
        },
    )
    service = AIGuidanceService(provider, prompt_version="busan-link-v1")
    app.dependency_overrides[get_ai_guidance_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        UUID("a1000000-0000-0000-0000-000000000001"),
        "buyer@example.test",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai-guidance/contract-assistant",
            headers={"Idempotency-Key": "review-contract"},
            json={
                "title": "부산 숙박 계약",
                "clauses": [
                    {"id": "clause-1", "title": "취소 조건", "body": "환불 불가"}
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["findings"][0]["severity"] == "high"
    assert provider.structured_requests[0].task_type == "contract_review"
    assert provider.structured_requests[0].reasoning_effort == "medium"


def test_generates_revision_suggestion(app: FastAPI) -> None:
    provider = FakeAIProvider()
    provider.queue_structured_output(
        "revision_draft",
        {"suggestion": "이용일 7일 전까지 취소 시 계약금 전액을 환불한다."},
    )
    service = AIGuidanceService(provider, prompt_version="busan-link-v1")
    app.dependency_overrides[get_ai_guidance_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        UUID("a1000000-0000-0000-0000-000000000001"),
        "buyer@example.test",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai-guidance/revision-suggestion",
            headers={"Idempotency-Key": "revision-suggestion"},
            json={
                "request_type": "modify",
                "clause_id": "clause-1",
                "clause_title": "취소 조건",
                "original_text": "취소할 수 없다.",
                "reason": "무료 취소 기간이 필요합니다.",
            },
        )

    assert response.status_code == 200
    assert "7일 전" in response.json()["data"]["suggestion"]
    assert provider.structured_requests[0].task_type == "revision_draft"


def test_generates_rag_augmented_seller_revision_guidance(app: FastAPI) -> None:
    provider = FakeAIProvider()
    provider.search_result = FileSearchResult(
        hits=[
            FileSearchHit(
                file_id="official-cancellation-guide",
                score=0.91,
                excerpt="취소 및 환불 조건은 시점별 기준을 명확히 정하는 것이 바람직하다.",
            )
        ]
    )
    provider.queue_structured_output(
        "revision_draft",
        {
            "items": [
                {
                    "id": "revision-item-1",
                    "impact": "전액 환불 범위가 확대되어 셀러의 취소 비용 부담이 커질 수 있습니다.",
                    "recommendation": "이용일 7일 전까지 취소 시 계약금 전액을 환불한다.",
                    "rejection_reason": (
                        "무료 취소 필요성은 이해하지만 실제 발생 비용을 고려해 "
                        "전액 환불 요청은 수락하기 어렵습니다."
                    ),
                }
            ]
        },
    )
    service = AIGuidanceService(
        provider,
        prompt_version="busan-link-v1",
        file_search_provider=provider,
        official_vector_store_id="official-store",
        template_vector_store_id="template-store",
        case_vector_store_id="case-store",
    )
    app.dependency_overrides[get_ai_guidance_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        UUID("a1000000-0000-0000-0000-000000000001"),
        "seller@example.test",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai-guidance/revision-impact",
            headers={"Idempotency-Key": "seller-revision-impact"},
            json={
                "items": [
                    {
                        "id": "revision-item-1",
                        "clause_title": "취소 조건",
                        "original_text": "취소 시 환불하지 않는다.",
                        "requested_text": "이용일 7일 전까지 전액 환불한다.",
                        "reason": "무료 취소 기간이 필요합니다.",
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert "실제 발생 비용" in response.json()["data"]["items"][0]["rejection_reason"]
    assert [request.vector_store_id for request in provider.search_requests] == [
        "official-store",
        "template-store",
        "case-store",
    ]
    request = provider.structured_requests[0]
    assert request.prompt_version.endswith(":seller-revision-guidance-v2")
    assert request.input_data["rag_context"][0]["corpus"] == "official"
    assert "무료 취소 기간" in provider.search_requests[0].query
