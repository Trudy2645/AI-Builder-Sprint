from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.providers.base import (
    AIProviderInvalidResponseError,
    AIProviderPermanentError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
)
from app.ai.providers.fake import FakeAIProvider
from app.ai.schemas import FileSearchHit, FileSearchResult
from app.api.dependencies import get_contract_generation_service
from app.core.auth import get_current_user
from app.domain.contract_generation.service import ContractGenerationService
from app.integrations.auth import AuthenticatedUser
from app.repositories.contract_generation import (
    ContractGenerationClaim,
    ContractGenerationIdempotencyConflictError,
    ContractGenerationInProgressError,
    ContractGenerationInputRecord,
    ContractGenerationMembershipRecord,
    ContractGenerationRecord,
    ContractGenerationStateConflictError,
    ContractGenerationVersionConflictError,
    GeneratedClauseRecord,
)

SELLER_ID = UUID("b1000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("b1000000-0000-0000-0000-000000000002")
ORGANIZATION_ID = UUID("b2000000-0000-0000-0000-000000000001")
LISTING_ID = UUID("b3000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("b4000000-0000-0000-0000-000000000001")


def complete_terms() -> dict[str, Any]:
    return {
        "service_start_date": date(2026, 8, 1),
        "service_end_date": date(2026, 8, 31),
        "supply_quantity": 30,
        "supply_quantity_description": "주말 객실 최대 30실",
        "quantity_unit": "room",
        "minimum_quantity": 10,
        "maximum_quantity": 30,
        "people_per_unit": 2,
        "base_price_amount_minor": 145000,
        "currency": "KRW",
        "price_unit": "room_night",
        "minimum_people": 20,
        "maximum_people": 60,
        "cancellation_policy": "체크인 7일 전까지 무료 취소",
        "no_show_policy": "당일 미이용은 객실 요금 100% 부과",
        "refund_policy": "취소 시점에 따라 환불",
        "settlement_policy": "월 마감 후 15일 이내 지급",
        "safety_policy": "시설 안전점검 제공",
        "compensation_policy": "셀러 귀책 시 환불",
        "liability_policy": "과실에 따른 책임 부담",
        "termination_policy": "중대한 위반 시 해지",
        "special_terms": "인원은 14일 전 확정",
    }


def valid_draft() -> dict[str, Any]:
    return {
        "clauses": [
            {
                "clause_key": "service",
                "title": "공급 기간 및 수량",
                "body": (
                    "공급 기간은 2026-08-01부터 2026-08-31까지이며 "
                    "주말 객실 최대 30실로 한다. quantity_unit은 room, 최소 10, 최대 30이며 "
                    "객실당 인원은 2명, 최소 인원은 20명, 최대 인원은 60명으로 한다."
                ),
            },
            {
                "clause_key": "price",
                "title": "공급 단가",
                "body": "공급 단가는 145,000 KRW이며 price_unit은 room_night로 한다.",
            },
            {
                "clause_key": "policies",
                "title": "계약 조건",
                "body": (
                    "체크인 7일 전까지 무료 취소. 당일 미이용은 객실 요금 100% 부과. "
                    "취소 시점에 따라 환불. 월 마감 후 15일 이내 지급. 시설 안전점검 제공. "
                    "셀러 귀책 시 환불. 과실에 따른 책임 부담. 중대한 위반 시 해지. "
                    "인원은 14일 전 확정."
                ),
            },
        ]
    }


class FakeContractGenerationRepository:
    def __init__(self) -> None:
        self.memberships = {
            (SELLER_ID, ORGANIZATION_ID): ContractGenerationMembershipRecord(
                organization_id=ORGANIZATION_ID,
                organization_type="seller",
            )
        }
        self.listing = ContractGenerationInputRecord(
            id=LISTING_ID,
            seller_organization_id=ORGANIZATION_ID,
            organization_name="해운대 오션스테이",
            title="부산 여름 객실 공급 계약",
            category="accommodation",
            district="해운대구",
            language="ko-KR",
            status="draft",
            current_version_id=VERSION_ID,
            current_version_no=1,
            terms=complete_terms(),
        )
        self.idempotency: dict[str, tuple[str, ContractGenerationRecord | None]] = {}
        self.versions = {VERSION_ID: "existing immutable input version"}
        self.jobs: dict[UUID, str] = {}
        self.failures: list[str] = []
        self.force_in_progress = False
        self.complete_error: Exception | None = None

    async def get_membership(self, user_id: UUID, organization_id: UUID):
        return self.memberships.get((user_id, organization_id))

    async def get_input(self, listing_id: UUID):
        return self.listing if listing_id == LISTING_ID else None

    async def claim_generation(
        self,
        *,
        expected_version_no: int,
        idempotency_key: str,
        request_hash: str,
        **_: Any,
    ) -> ContractGenerationClaim:
        existing = self.idempotency.get(idempotency_key)
        if existing:
            if existing[0] != request_hash:
                raise ContractGenerationIdempotencyConflictError
            if existing[1] is None or self.force_in_progress:
                raise ContractGenerationInProgressError
            return ContractGenerationClaim(None, existing[1])
        if self.listing.current_version_no != expected_version_no:
            raise ContractGenerationVersionConflictError
        if self.listing.status != "draft":
            raise ContractGenerationStateConflictError
        job_id = uuid4()
        self.idempotency[idempotency_key] = (request_hash, None)
        self.jobs[job_id] = "processing"
        self.listing = replace(self.listing, status="processing")
        return ContractGenerationClaim(job_id, None)

    async def complete_generation(
        self,
        *,
        listing: ContractGenerationInputRecord,
        job_id: UUID,
        idempotency_key: str,
        request_hash: str,
        clauses,
        body: str,
        **_: Any,
    ) -> ContractGenerationRecord:
        if self.complete_error is not None:
            raise self.complete_error
        version_id = uuid4()
        records = [
            GeneratedClauseRecord(
                id=uuid4(),
                clause_order=order,
                clause_key=clause.clause_key,
                title=clause.title,
                body=clause.body,
            )
            for order, clause in enumerate(clauses, start=1)
        ]
        record = ContractGenerationRecord(
            listing_id=listing.id,
            job_id=job_id,
            listing_version_id=version_id,
            version_no=listing.current_version_no + 1,
            status="ready",
            clauses=records,
        )
        self.versions[version_id] = body
        self.jobs[job_id] = "succeeded"
        self.listing = replace(
            self.listing,
            status="ready",
            current_version_id=version_id,
            current_version_no=record.version_no,
        )
        self.idempotency[idempotency_key] = (request_hash, record)
        return record

    async def fail_generation(
        self,
        *,
        job_id: UUID,
        idempotency_key: str,
        failure_code: str,
        **_: Any,
    ) -> None:
        self.jobs[job_id] = "failed"
        self.failures.append(failure_code)
        self.listing = replace(self.listing, status="draft")
        self.idempotency.pop(idempotency_key, None)


def build_context(*, template_store: str | None = "template-store"):
    repository = FakeContractGenerationRepository()
    provider = FakeAIProvider()
    provider.queue_structured_output("contract_generate", valid_draft())
    provider.search_result = FileSearchResult(
        hits=[
            FileSearchHit(
                file_id="approved-template-1",
                score=0.9,
                excerpt="승인된 숙박 계약 템플릿",
                metadata={"source_type": "approved_template"},
            )
        ]
    )
    service = ContractGenerationService(
        repository,
        provider,
        provider,
        provider_name="fake",
        model_name="solar-pro3",
        prompt_version="busan-link-v1",
        template_vector_store_id=template_store,
    )
    return repository, provider, service


@pytest.fixture
def generation_context(app: FastAPI):
    context = build_context()
    app.dependency_overrides[get_contract_generation_service] = lambda: context[2]
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )
    return context


def headers(key: str = "generate-contract-1") -> dict[str, str]:
    return {"X-Organization-Id": str(ORGANIZATION_ID), "Idempotency-Key": key}


def generate(client: TestClient, *, base_version_no: int = 1, key: str = "generate-contract-1"):
    return client.post(
        f"/api/v1/seller/listings/{LISTING_ID}/generate",
        headers=headers(key),
        json={"base_version_no": base_version_no},
    )


def test_generate_creates_new_immutable_version_and_ready_listing(
    client: TestClient, generation_context
) -> None:
    repository, provider, _ = generation_context

    response = generate(client)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["version_no"] == 2
    assert [clause["clause_order"] for clause in data["clauses"]] == [1, 2, 3]
    assert repository.versions[VERSION_ID] == "existing immutable input version"
    assert repository.listing.status == "ready"
    assert provider.calls[0][0] == "file_search"
    assert provider.calls[1] == ("language_model", "contract_generate")
    context = provider.structured_requests[0].input_data["approved_template_context"]
    assert context[0]["usage"] == "drafting_reference_not_legal_evidence"


def test_same_input_and_idempotency_key_returns_same_result_without_second_ai_call(
    client: TestClient, generation_context
) -> None:
    _, provider, _ = generation_context

    first = generate(client)
    repeated = generate(client)

    assert repeated.status_code == 200
    assert repeated.json()["data"] == first.json()["data"]
    assert [call[0] for call in provider.calls].count("language_model") == 1


def test_same_key_with_different_input_conflicts(client: TestClient, generation_context) -> None:
    generate(client)

    response = generate(client, base_version_no=2)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_missing_terms_are_rejected_before_ai_call(client: TestClient, generation_context) -> None:
    repository, provider, _ = generation_context
    repository.listing.terms["cancellation_policy"] = None

    response = generate(client)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AI_INPUT_INSUFFICIENT"
    assert "cancellation_policy" in response.json()["error"]["details"]["missing_fields"]
    assert provider.calls == []


def test_version_and_state_conflicts_are_rejected(client: TestClient, generation_context) -> None:
    repository, _, _ = generation_context
    version_conflict = generate(client, base_version_no=2, key="version-conflict")
    repository.listing = replace(repository.listing, status="ready")
    state_conflict = generate(client, key="state-conflict")

    assert version_conflict.status_code == 409
    assert version_conflict.json()["error"]["code"] == "VERSION_CONFLICT"
    assert state_conflict.status_code == 409
    assert state_conflict.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_other_user_cannot_generate(app: FastAPI, client: TestClient, generation_context) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OTHER_ID, "other@example.test"
    )

    response = generate(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORG_ACCESS_DENIED"


@pytest.mark.parametrize(
    ("error", "status_code", "error_code", "failure_code"),
    [
        (AIProviderTimeoutError(), 504, "AI_PROVIDER_TIMEOUT", "AI_PROVIDER_TIMEOUT"),
        (
            AIProviderRateLimitError(),
            503,
            "AI_PROVIDER_RATE_LIMITED",
            "AI_PROVIDER_RATE_LIMITED",
        ),
        (
            AIProviderTemporaryError(),
            503,
            "AI_PROVIDER_TEMPORARY_FAILURE",
            "AI_PROVIDER_TEMPORARY_FAILURE",
        ),
        (
            AIProviderPermanentError(),
            502,
            "AI_PROVIDER_REJECTED_REQUEST",
            "AI_PROVIDER_REJECTED_REQUEST",
        ),
        (
            AIProviderInvalidResponseError(),
            502,
            "AI_GENERATION_INVALID",
            "AI_GENERATION_INVALID",
        ),
    ],
)
def test_provider_failures_restore_draft_without_sensitive_details(
    app: FastAPI,
    client: TestClient,
    error: Exception,
    status_code: int,
    error_code: str,
    failure_code: str,
) -> None:
    repository, provider, service = build_context(template_store=None)
    provider.queue_failure("contract_generate", error)  # type: ignore[arg-type]
    app.dependency_overrides[get_contract_generation_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )

    response = generate(client)

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert "145000" not in response.json()["error"]["message"]
    assert response.json()["error"]["details"] == {}
    assert repository.listing.status == "draft"
    assert repository.failures == [failure_code]


def test_generated_extra_number_or_changed_date_is_rejected(
    app: FastAPI, client: TestClient
) -> None:
    repository, provider, service = build_context(template_store=None)
    invalid = valid_draft()
    invalid["clauses"][0]["body"] += " 추가 수수료는 999원이며 2026-08-02부터 적용한다."
    provider._structured_outputs["contract_generate"].clear()
    provider.queue_structured_output("contract_generate", invalid)
    app.dependency_overrides[get_contract_generation_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )

    response = generate(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_GENERATION_INVALID"
    assert repository.listing.status == "draft"
    assert len(repository.versions) == 1


def test_missing_input_price_in_generated_body_is_rejected(
    app: FastAPI, client: TestClient
) -> None:
    repository, provider, service = build_context(template_store=None)
    invalid = valid_draft()
    invalid["clauses"][1]["body"] = "통화는 KRW이며 price_unit은 room_night로 한다."
    provider._structured_outputs["contract_generate"].clear()
    provider.queue_structured_output("contract_generate", invalid)
    app.dependency_overrides[get_contract_generation_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )

    response = generate(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_GENERATION_INVALID"
    assert repository.listing.status == "draft"


def test_model_article_numbers_are_removed_before_code_assigns_clause_order(
    app: FastAPI, client: TestClient
) -> None:
    repository, provider, service = build_context(template_store=None)
    numbered = valid_draft()
    numbered["clauses"][0]["title"] = "제1조 공급 기간 및 수량"
    provider._structured_outputs["contract_generate"].clear()
    provider.queue_structured_output("contract_generate", numbered)
    app.dependency_overrides[get_contract_generation_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )

    response = generate(client)

    assert response.status_code == 200
    assert response.json()["data"]["clauses"][0]["title"] == "공급 기간 및 수량"
    generated_version = response.json()["data"]["listing_version_id"]
    assert repository.versions[UUID(generated_version)].startswith("제1조 공급 기간 및 수량")


def test_in_progress_idempotent_request_returns_conflict(
    client: TestClient, generation_context
) -> None:
    repository, _, service = generation_context
    repository.idempotency["generate-contract-1"] = (
        service._request_hash(LISTING_ID, 1),
        None,
    )
    repository.force_in_progress = True

    response = generate(client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"


def test_version_change_before_save_restores_draft_and_returns_conflict(
    client: TestClient, generation_context
) -> None:
    repository, _, _ = generation_context
    repository.complete_error = ContractGenerationVersionConflictError()

    response = generate(client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    assert repository.listing.status == "draft"
    assert repository.failures == ["VERSION_CONFLICT"]


def test_generation_without_configured_template_store_does_not_search_files(
    app: FastAPI, client: TestClient
) -> None:
    _, provider, service = build_context(template_store=None)
    app.dependency_overrides[get_contract_generation_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )

    response = generate(client)

    assert response.status_code == 200
    assert all(call[0] != "file_search" for call in provider.calls)


def test_unapproved_search_hit_is_not_added_to_generation_context(
    client: TestClient, generation_context
) -> None:
    _, provider, _ = generation_context
    provider.search_result = FileSearchResult(
        hits=[
            FileSearchHit(
                file_id="unreviewed-file",
                excerpt="검수되지 않은 계약 문구",
                metadata={"source_type": "uploaded_contract"},
            )
        ]
    )

    response = generate(client)

    assert response.status_code == 200
    assert provider.structured_requests[0].input_data["approved_template_context"] == []
