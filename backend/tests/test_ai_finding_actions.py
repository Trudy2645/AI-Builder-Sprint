from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeAIProvider
from app.ai.tasks.contract_review_rules import ReviewClauseInput
from app.api.dependencies import get_contract_review_service
from app.core.auth import get_current_user
from app.domain.contract_review.service import ContractReviewService
from app.integrations.auth import AuthenticatedUser
from app.repositories.contract_review import (
    ContractReviewIdempotencyConflictError,
    ContractReviewTargetRecord,
    FindingActionConflictError,
    FindingActionContext,
    FindingActionVersionConflictError,
    FindingApplyRecord,
    FindingDismissRecord,
    FindingReviewJob,
    FindingSuggestionConflictError,
)

SELLER_ID = UUID("d1000000-0000-0000-0000-000000000001")
BUYER_ID = UUID("d1000000-0000-0000-0000-000000000002")
ORGANIZATION_ID = UUID("d2000000-0000-0000-0000-000000000001")
LISTING_ID = UUID("d3000000-0000-0000-0000-000000000001")
OLD_VERSION_ID = UUID("d4000000-0000-0000-0000-000000000001")
NEW_VERSION_ID = UUID("d4000000-0000-0000-0000-000000000002")
CLAUSE_ID = UUID("d5000000-0000-0000-0000-000000000001")
FINDING_ID = UUID("d6000000-0000-0000-0000-000000000001")
SUGGESTED_TEXT = "체크인 7일 전까지는 위약금 없이 취소할 수 있습니다."
SUGGESTED_HASH = hashlib.sha256(SUGGESTED_TEXT.encode()).hexdigest()


def review_target(version_id: UUID = OLD_VERSION_ID, version_no: int = 2):
    return ContractReviewTargetRecord(
        target_type="listing_version",
        resource_id=LISTING_ID,
        version_id=version_id,
        version_no=version_no,
        category="accommodation",
        seller_organization_id=ORGANIZATION_ID,
        buyer_user_id=None,
        terms={"cancellation_policy": "취소 시 환불하지 않습니다."},
        clauses=[
            ReviewClauseInput(
                id=CLAUSE_ID,
                clause_order=1,
                clause_key="cancellation",
                title="취소 및 환불",
                body="취소 시 환불하지 않습니다.",
                source_location={"page": 1},
            )
        ],
    )


class FakeFindingActionRepository:
    def __init__(self) -> None:
        self.members = {(SELLER_ID, ORGANIZATION_ID)}
        self.context = FindingActionContext(
            finding_id=FINDING_ID,
            finding_status="open",
            target_type="listing_version",
            resource_id=LISTING_ID,
            version_id=OLD_VERSION_ID,
            version_no=2,
            current_version_id=OLD_VERSION_ID,
            current_version_no=2,
            resource_status="ready",
            seller_organization_id=ORGANIZATION_ID,
            buyer_user_id=None,
            viewer_role="seller",
            clause_id=CLAUSE_ID,
            title="취소 조항을 보완하세요",
            suggested_text=SUGGESTED_TEXT,
            suggested_text_sha256=SUGGESTED_HASH,
        )
        self.targets = {
            OLD_VERSION_ID: review_target(),
            NEW_VERSION_ID: review_target(NEW_VERSION_ID, 3),
        }
        self.actions: dict[tuple[str, str], tuple[str, Any]] = {}
        self.applied_text: str | None = None
        self.version_creations = 0
        self.audit_events: list[str] = []
        self.completed_reviews = 0
        self.failed_reviews = 0
        self.force_version_conflict = False

    async def get_finding_action_context(self, finding_id: UUID):
        return self.context if finding_id == FINDING_ID else None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        return (user_id, organization_id) in self.members

    async def get_listing_target(self, listing_id: UUID, version_id: UUID):
        if listing_id != LISTING_ID:
            return None
        return self.targets.get(version_id)

    async def get_contract_target(self, contract_id: UUID, version_id: UUID):
        return None

    async def apply_finding(
        self,
        *,
        finding_id: UUID,
        base_version_no: int,
        suggested_text_hash: str,
        edited_text: str | None,
        idempotency_key: str,
        request_hash: str,
        **_: Any,
    ) -> FindingApplyRecord:
        key = ("apply", idempotency_key)
        existing = self.actions.get(key)
        if existing:
            if existing[0] != request_hash:
                raise ContractReviewIdempotencyConflictError
            return replace(existing[1], replayed=True)
        if self.force_version_conflict or base_version_no != self.context.current_version_no:
            raise FindingActionVersionConflictError
        if suggested_text_hash.removeprefix("sha256:") != SUGGESTED_HASH:
            raise FindingSuggestionConflictError
        if self.context.finding_status != "open" or self.context.suggested_text is None:
            raise FindingActionConflictError
        if self.context.resource_status not in {"draft", "ready", "published", "paused"}:
            raise FindingActionConflictError
        self.version_creations += 1
        self.applied_text = edited_text or SUGGESTED_TEXT
        self.context = replace(
            self.context,
            finding_status="applied",
            current_version_id=NEW_VERSION_ID,
            current_version_no=3,
        )
        record = FindingApplyRecord(
            finding_id=finding_id,
            target_type="listing_version",
            resource_id=LISTING_ID,
            previous_version_id=OLD_VERSION_ID,
            version_id=NEW_VERSION_ID,
            version_no=3,
            jobs=[
                FindingReviewJob(uuid4(), "seller"),
                FindingReviewJob(uuid4(), "buyer"),
            ],
            replayed=False,
        )
        self.actions[key] = (request_hash, record)
        self.audit_events.append("ai_finding_applied")
        return record

    async def dismiss_finding(
        self,
        *,
        finding_id: UUID,
        reason: str,
        idempotency_key: str,
        request_hash: str,
        **_: Any,
    ) -> FindingDismissRecord:
        key = ("dismiss", idempotency_key)
        existing = self.actions.get(key)
        if existing:
            if existing[0] != request_hash:
                raise ContractReviewIdempotencyConflictError
            return replace(existing[1], replayed=True)
        if self.context.finding_status != "open":
            raise FindingActionConflictError
        self.context = replace(self.context, finding_status="dismissed")
        record = FindingDismissRecord(finding_id=finding_id, replayed=False)
        self.actions[key] = (request_hash, record)
        self.audit_events.append(f"ai_finding_dismissed:{reason}")
        return record

    async def mark_processing(self, **_: Any) -> UUID:
        return uuid4()

    async def complete_review(self, **_: Any) -> None:
        self.completed_reviews += 1

    async def fail_review(self, **_: Any) -> None:
        self.failed_reviews += 1


def review_submission() -> dict[str, Any]:
    return {
        "tool_calls": [
            {
                "name": "submit_review",
                "arguments": {
                    "findings": [
                        {
                            "clause_id": str(CLAUSE_ID),
                            "category": "cancellation",
                            "severity": "low",
                            "importance": "high",
                            "title": "취소 기준 확인",
                            "explanation": "취소 기준을 계약 전에 확인하세요.",
                            "suggested_text": None,
                            "grounding_status": "insufficient_evidence",
                            "confidence": 0.5,
                            "source_location": {"page": 1},
                            "evidence_ids": [],
                            "disclaimer": "법률 자문이 아닌 검토 보조 의견입니다.",
                            "is_public": False,
                        }
                    ]
                },
            }
        ]
    }


def action_context(app: FastAPI, actor_id: UUID = SELLER_ID, *, queue_reviews: bool = True):
    repository = FakeFindingActionRepository()
    provider = FakeAIProvider()
    if queue_reviews:
        provider.queue_structured_output("contract_review", review_submission())
        provider.queue_structured_output("contract_review", review_submission())
    service = ContractReviewService(
        repository,
        provider,
        provider,
        provider_name="fake",
        model_name="solar-pro3",
        prompt_version="busan-link-v1",
        official_vector_store_id=None,
        template_vector_store_id=None,
    )
    app.dependency_overrides[get_contract_review_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        actor_id, "actor@example.test"
    )
    return repository


def headers(key: str) -> dict[str, str]:
    return {
        "X-Organization-Id": str(ORGANIZATION_ID),
        "Idempotency-Key": key,
    }


def apply_payload(**changes: Any) -> dict[str, Any]:
    payload = {
        "base_version_no": 2,
        "suggested_text_hash": f"sha256:{SUGGESTED_HASH}",
        "edited_text": None,
    }
    payload.update(changes)
    return payload


def test_apply_creates_new_version_and_reanalyzes_both_roles(app: FastAPI) -> None:
    repository = action_context(app)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("apply-once"),
            json=apply_payload(),
        )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["previous_version_id"] == str(OLD_VERSION_ID)
    assert data["version_id"] == str(NEW_VERSION_ID)
    assert data["version_no"] == 3
    assert len(data["analysis_job_ids"]) == 2
    assert repository.version_creations == 1
    assert repository.completed_reviews == 2
    assert repository.audit_events == ["ai_finding_applied"]
    assert repository.targets[OLD_VERSION_ID].clauses[0].body == "취소 시 환불하지 않습니다."


def test_apply_uses_edited_text_but_validates_original_suggestion_hash(app: FastAPI) -> None:
    repository = action_context(app)
    edited = "체크인 10일 전까지는 위약금 없이 취소할 수 있습니다."
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("edited"),
            json=apply_payload(edited_text=edited),
        )
    assert response.status_code == 202
    assert repository.applied_text == edited


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (apply_payload(base_version_no=1), "VERSION_CONFLICT"),
        (apply_payload(suggested_text_hash="0" * 64), "SUGGESTED_TEXT_CONFLICT"),
    ],
)
def test_apply_rejects_stale_version_or_suggestion_hash(
    app: FastAPI, payload: dict[str, Any], code: str
) -> None:
    action_context(app)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers(code),
            json=payload,
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


def test_apply_is_idempotent_and_does_not_create_another_version(app: FastAPI) -> None:
    repository = action_context(app)
    with TestClient(app) as client:
        first = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("replay"),
            json=apply_payload(),
        )
        second = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("replay"),
            json=apply_payload(),
        )
    assert first.status_code == second.status_code == 202
    assert second.json()["data"]["replayed"] is True
    assert repository.version_creations == 1
    assert repository.completed_reviews == 2


def test_apply_tracks_reanalysis_provider_failure_without_rolling_back_version(
    app: FastAPI,
) -> None:
    repository = action_context(app, queue_reviews=False)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("provider-failure"),
            json=apply_payload(),
        )
    assert response.status_code == 202
    assert repository.version_creations == 1
    assert repository.failed_reviews == 2


def test_finding_actions_require_seller_organization_membership(app: FastAPI) -> None:
    repository = action_context(app, actor_id=BUYER_ID)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("buyer-direct-apply"),
            json=apply_payload(),
        )
    assert response.status_code == 403
    assert repository.version_creations == 0


def test_apply_rejects_archived_resource(app: FastAPI) -> None:
    repository = action_context(app)
    repository.context = replace(repository.context, resource_status="archived")
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/apply",
            headers=headers("archived"),
            json=apply_payload(),
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FINDING_NOT_ACTIONABLE"
    assert repository.version_creations == 0


def test_dismiss_marks_finding_without_creating_version(app: FastAPI) -> None:
    repository = action_context(app)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai-findings/{FINDING_ID}/dismiss",
            headers=headers("dismiss"),
            json={"reason": "현재 운영 정책에 이미 반영되어 있습니다."},
        )
    assert response.status_code == 200
    assert response.json()["data"]["finding_status"] == "dismissed"
    assert repository.version_creations == 0
    assert repository.context.current_version_id == OLD_VERSION_ID
    assert repository.audit_events[0].startswith("ai_finding_dismissed:")


def test_dismiss_replay_and_payload_conflict(app: FastAPI) -> None:
    repository = action_context(app)
    endpoint = f"/api/v1/ai-findings/{FINDING_ID}/dismiss"
    with TestClient(app) as client:
        first = client.post(endpoint, headers=headers("dismiss-replay"), json={"reason": "중복"})
        replay = client.post(endpoint, headers=headers("dismiss-replay"), json={"reason": "중복"})
        conflict = client.post(endpoint, headers=headers("dismiss-replay"), json={"reason": "변경"})
    assert first.status_code == replay.status_code == 200
    assert replay.json()["data"]["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert len(repository.audit_events) == 1


def test_finding_action_openapi_schemas_are_registered(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert "FindingApplyRequest" in schemas
    assert "FindingApplyResponse" in schemas
    assert "FindingDismissRequest" in schemas
    assert "FindingDismissResponse" in schemas
