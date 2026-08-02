from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_ai_job_service
from app.core.auth import get_current_user
from app.domain.ai_jobs.service import AIJobService
from app.integrations.auth import AuthenticatedUser
from app.repositories.ai_jobs import AIJobMembershipRecord, AIJobRecord

SELLER_ID = UUID("a1000000-0000-0000-0000-000000000001")
OTHER_USER_ID = UUID("a1000000-0000-0000-0000-000000000002")
BUYER_ID = UUID("a1000000-0000-0000-0000-000000000003")
ORGANIZATION_ID = UUID("a2000000-0000-0000-0000-000000000001")
JOB_ID = UUID("a3000000-0000-0000-0000-000000000001")
RESULT_ID = UUID("a4000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 1, 12, tzinfo=UTC)


class FakeAIJobRepository:
    def __init__(self) -> None:
        self.jobs = {
            JOB_ID: AIJobRecord(
                id=JOB_ID,
                job_type="document_parse",
                status="processing",
                failure_code=None,
                result_metadata={
                    "progress": 35,
                    "result_resource_type": "document",
                    "result_resource_id": str(RESULT_ID),
                },
                created_at=NOW,
                started_at=NOW,
                completed_at=None,
                seller_organization_id=ORGANIZATION_ID,
                buyer_user_id=BUYER_ID,
            )
        }
        self.memberships = {
            (SELLER_ID, ORGANIZATION_ID): AIJobMembershipRecord(
                organization_id=ORGANIZATION_ID,
                organization_type="seller",
            )
        }

    async def get_job(self, job_id: UUID):
        return self.jobs.get(job_id)

    async def get_membership(self, user_id: UUID, organization_id: UUID):
        return self.memberships.get((user_id, organization_id))


@pytest.fixture
def ai_job_context(app: FastAPI):
    repository = FakeAIJobRepository()
    app.dependency_overrides[get_ai_job_service] = lambda: AIJobService(repository)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )
    return repository


def test_seller_can_poll_owned_ai_job(
    app: FastAPI, client: TestClient, ai_job_context: FakeAIJobRepository
) -> None:
    response = client.get(
        f"/api/v1/ai-jobs/{JOB_ID}",
        headers={"X-Organization-Id": str(ORGANIZATION_ID)},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": str(JOB_ID),
        "task_type": "document_parse",
        "status": "processing",
        "progress": 35,
        "result_resource_type": "document",
        "result_resource_id": str(RESULT_ID),
        "failure_code": None,
        "created_at": "2026-08-01T12:00:00Z",
        "started_at": "2026-08-01T12:00:00Z",
        "completed_at": None,
    }


def test_buyer_can_poll_contract_ai_job_without_organization_header(
    app: FastAPI, client: TestClient, ai_job_context: FakeAIJobRepository
) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        BUYER_ID, "buyer@example.test"
    )

    response = client.get(f"/api/v1/ai-jobs/{JOB_ID}")

    assert response.status_code == 200


def test_other_user_cannot_poll_ai_job(
    app: FastAPI, client: TestClient, ai_job_context: FakeAIJobRepository
) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OTHER_USER_ID, "other@example.test"
    )

    response = client.get(
        f"/api/v1/ai-jobs/{JOB_ID}",
        headers={"X-Organization-Id": str(ORGANIZATION_ID)},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AI_JOB_ACCESS_DENIED"


def test_ai_job_polling_requires_authentication(
    app: FastAPI, client: TestClient, ai_job_context: FakeAIJobRepository
) -> None:
    del app.dependency_overrides[get_current_user]

    response = client.get(f"/api/v1/ai-jobs/{JOB_ID}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_missing_ai_job_returns_not_found(
    app: FastAPI, client: TestClient, ai_job_context: FakeAIJobRepository
) -> None:
    response = client.get(
        "/api/v1/ai-jobs/a3000000-0000-0000-0000-000000000099",
        headers={"X-Organization-Id": str(ORGANIZATION_ID)},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AI_JOB_NOT_FOUND"


def test_ai_job_schema_is_exposed_in_openapi(
    client: TestClient, ai_job_context: FakeAIJobRepository
) -> None:
    schema = client.get("/openapi.json").json()

    assert "/api/v1/ai-jobs/{job_id}" in schema["paths"]
    assert "AIJobView" in schema["components"]["schemas"]
