from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeAIProvider
from app.api.dependencies import get_ai_guidance_service
from app.core.auth import get_current_user
from app.domain.ai_guidance.service import AIGuidanceService
from app.integrations.auth import AuthenticatedUser


def test_revision_impact_and_change_summary_use_structured_ai(app: FastAPI) -> None:
    service = AIGuidanceService(
        FakeAIProvider(enable_default_outputs=True), prompt_version="busan-link-v1"
    )
    app.dependency_overrides[get_ai_guidance_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        UUID("b1000000-0000-0000-0000-000000000001"), "seller@example.test"
    )
    with TestClient(app) as client:
        revision = client.post(
            "/api/v1/ai-guidance/revision-impact",
            headers={"Idempotency-Key": "revision-guidance-1"},
            json={
                "items": [
                    {
                        "id": "item-1",
                        "clause_title": "예약 요청 및 확정",
                        "original_text": "셀러가 확인하면 예약이 성립한다.",
                        "requested_text": "확정 통지가 도달하면 예약이 성립한다.",
                        "reason": "확정 시점을 명확히 하고 싶습니다.",
                    }
                ]
            },
        )
        summary = client.post(
            "/api/v1/ai-guidance/change-summary",
            headers={"Idempotency-Key": "change-summary-1"},
            json={
                "changes": [
                    {
                        "title": "예약 요청 및 확정",
                        "before": "셀러가 확인하면 예약이 성립한다.",
                        "after": "확정 통지가 도달하면 예약이 성립한다.",
                    }
                ]
            },
        )

    assert revision.status_code == 200
    assert revision.json()["data"]["items"][0]["id"] == "item-1"
    assert summary.status_code == 200
    assert len(summary.json()["data"]["lines"]) == 3
