from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_seller_listing_service
from app.core.auth import get_auth_provider, get_current_user
from app.domain.seller_listings.service import SellerListingService
from app.integrations.auth import AuthenticatedUser, FakeAuthProvider
from app.repositories.seller_listings import (
    NewSellerListingClause,
    SellerListingClauseRecord,
    SellerListingCreatedRecord,
    SellerListingDocumentAccessError,
    SellerListingHasContractsError,
    SellerListingIdempotencyConflictError,
    SellerListingMembershipRecord,
    SellerListingNotFoundError,
    SellerListingRecord,
    SellerListingRepositoryError,
    SellerListingStateConflictError,
    SellerListingVersionConflictError,
)

SELLER_ID = UUID("b1000000-0000-0000-0000-000000000001")
OTHER_SELLER_ID = UUID("b1000000-0000-0000-0000-000000000002")
ORGANIZATION_ID = UUID("b2000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID("b2000000-0000-0000-0000-000000000002")
HERO_DOCUMENT_ID = UUID("b3000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


def complete_terms() -> dict[str, object]:
    return {
        "service_start_date": "2026-08-01",
        "service_end_date": "2026-08-31",
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
        "no_show_policy": "당일 미이용은 환불 불가",
        "refund_policy": "취소 시점에 따라 환불",
        "settlement_policy": "월 마감 후 15일 이내",
        "safety_policy": "시설 안전점검 제공",
        "compensation_policy": "셀러 귀책 시 환불",
        "liability_policy": "과실에 따른 책임 부담",
        "termination_policy": "중대한 위반 시 해지",
        "special_terms": "인원은 14일 전 확정",
    }


class FakeSellerListingRepository:
    def __init__(self) -> None:
        self.memberships = {
            (SELLER_ID, ORGANIZATION_ID): SellerListingMembershipRecord(
                organization_id=ORGANIZATION_ID,
                organization_type="seller",
                verification_status="verified",
                role="member",
            ),
            (OTHER_SELLER_ID, OTHER_ORGANIZATION_ID): SellerListingMembershipRecord(
                organization_id=OTHER_ORGANIZATION_ID,
                organization_type="seller",
                verification_status="verified",
                role="owner",
            ),
        }
        self.records: dict[UUID, SellerListingRecord] = {}
        self.clauses: dict[UUID, list[SellerListingClauseRecord]] = {}
        self.idempotency: dict[tuple[UUID, str], tuple[str, SellerListingCreatedRecord]] = {}
        self.version_bodies: dict[UUID, str] = {}
        self.ready_documents = {HERO_DOCUMENT_ID}
        self.audit_events: list[str] = []
        self.unavailable = False

    def _check_available(self) -> None:
        if self.unavailable:
            raise SellerListingRepositoryError

    async def get_membership(self, user_id: UUID, organization_id: UUID):
        self._check_available()
        return self.memberships.get((user_id, organization_id))

    async def list_seller_listings(self, organization_id: UUID):
        self._check_available()
        return [
            record
            for record in self.records.values()
            if record.seller_organization_id == organization_id
        ]

    async def get_seller_listing(self, listing_id: UUID):
        self._check_available()
        return self.records.get(listing_id)

    async def list_listing_clauses(self, listing_version_id: UUID):
        self._check_available()
        return self.clauses.get(listing_version_id, [])

    async def create_listing(
        self,
        *,
        organization_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
        creation_method: str,
        title: str,
        category: str,
        district: str,
        language: str,
    ) -> SellerListingCreatedRecord:
        self._check_available()
        key = (organization_id, idempotency_key)
        existing = self.idempotency.get(key)
        if existing:
            if existing[0] != request_hash:
                raise SellerListingIdempotencyConflictError
            return existing[1]
        listing_id = uuid4()
        version_id = uuid4()
        record = SellerListingRecord(
            id=listing_id,
            seller_organization_id=organization_id,
            organization_name="Ocean Stay",
            verification_status="verified",
            title=title,
            display_title=None,
            display_company_name=None,
            district=district,
            category=category,
            language=language,
            status="draft",
            creation_method=creation_method,
            seller_description=None,
            public_headline=None,
            ai_summary=None,
            hero_document_id=None,
            current_version_id=version_id,
            current_version_no=1,
            current_version_title=title,
            current_version_body="",
            current_version_created_at=NOW,
            contract_request_count=0,
            contract_count=0,
            attention_required_count=0,
            service_start_date=None,
            service_end_date=None,
            supply_quantity=None,
            supply_quantity_description=None,
            quantity_unit=None,
            minimum_quantity=None,
            maximum_quantity=None,
            people_per_unit=None,
            base_price_amount_minor=None,
            currency=None,
            price_unit=None,
            minimum_people=None,
            maximum_people=None,
            cancellation_policy=None,
            no_show_policy=None,
            refund_policy=None,
            settlement_policy=None,
            safety_policy=None,
            compensation_policy=None,
            liability_policy=None,
            termination_policy=None,
            special_terms=None,
            price_display_basis=None,
            contract_availability_note=None,
            published_at=None,
            paused_at=None,
            created_at=NOW,
            updated_at=NOW,
        )
        self.records[listing_id] = record
        self.clauses[version_id] = []
        self.version_bodies[version_id] = ""
        created = SellerListingCreatedRecord(listing_id, "draft", 1)
        self.idempotency[key] = (request_hash, created)
        self.audit_events.append("listing_created")
        return created

    async def update_listing_terms(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        changes: dict,
        structured_data: dict,
        body: str,
        clauses: list[NewSellerListingClause],
    ) -> SellerListingRecord:
        self._check_available()
        record = self.records.get(listing_id)
        if record is None or record.seller_organization_id != organization_id:
            raise SellerListingNotFoundError
        if record.current_version_no != base_version_no:
            raise SellerListingVersionConflictError
        if record.status not in {"draft", "ready", "published", "paused"}:
            raise SellerListingStateConflictError
        if record.contract_count:
            raise SellerListingHasContractsError
        version_id = uuid4()
        new_status = "draft" if record.status == "ready" else record.status
        updated = replace(
            record,
            **changes,
            current_version_id=version_id,
            current_version_no=base_version_no + 1,
            current_version_body=body,
            current_version_created_at=NOW,
            status=new_status,
        )
        self.records[listing_id] = updated
        self.clauses[version_id] = [
            SellerListingClauseRecord(
                id=uuid4(),
                clause_order=index,
                clause_key=clause.clause_key,
                title=clause.title,
                body=clause.body,
            )
            for index, clause in enumerate(clauses, start=1)
        ]
        self.version_bodies[version_id] = body
        self.audit_events.append("listing_terms_updated")
        return updated

    async def update_listing_presentation(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        listing_changes: dict,
        term_changes: dict,
    ) -> SellerListingRecord:
        self._check_available()
        record = self.records.get(listing_id)
        if record is None or record.seller_organization_id != organization_id:
            raise SellerListingNotFoundError
        if record.status not in {"draft", "ready", "published", "paused"}:
            raise SellerListingStateConflictError
        hero_document_id = listing_changes.get("hero_document_id")
        if hero_document_id is not None and hero_document_id not in self.ready_documents:
            raise SellerListingDocumentAccessError
        updated = replace(record, **listing_changes, **term_changes)
        self.records[listing_id] = updated
        if listing_changes or term_changes:
            self.audit_events.append("listing_presentation_updated")
        return updated

    async def complete_listing(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        expected_version_id: UUID,
    ) -> SellerListingRecord:
        self._check_available()
        record = self.records.get(listing_id)
        if record is None or record.seller_organization_id != organization_id:
            raise SellerListingNotFoundError
        if record.current_version_id != expected_version_id:
            raise SellerListingVersionConflictError
        if record.status == "ready":
            return record
        if record.status != "draft":
            raise SellerListingStateConflictError
        updated = replace(record, status="ready")
        self.records[listing_id] = updated
        self.audit_events.extend(["listing_processing", "listing_completed"])
        return updated

    async def transition_listing(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        target_status: str,
    ) -> SellerListingRecord:
        self._check_available()
        record = self.records.get(listing_id)
        if record is None or record.seller_organization_id != organization_id:
            raise SellerListingNotFoundError
        allowed = {
            "published": {"ready", "paused", "published"},
            "paused": {"published", "paused"},
            "archived": {"draft", "ready", "paused", "archived"},
        }
        if record.status not in allowed[target_status]:
            raise SellerListingStateConflictError
        if record.status == target_status:
            return record
        updated = replace(
            record,
            status=target_status,
            published_at=(NOW if target_status == "published" else record.published_at),
            paused_at=(NOW if target_status == "paused" else None),
        )
        self.records[listing_id] = updated
        self.audit_events.append(f"listing_{target_status}")
        return updated


@pytest.fixture
def listing_repository() -> FakeSellerListingRepository:
    return FakeSellerListingRepository()


@pytest.fixture
def listing_client(app: FastAPI, listing_repository: FakeSellerListingRepository) -> TestClient:
    service = SellerListingService(listing_repository)
    app.dependency_overrides[get_seller_listing_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )
    return TestClient(app)


def headers(organization_id: UUID = ORGANIZATION_ID) -> dict[str, str]:
    return {"X-Organization-Id": str(organization_id)}


def create_listing(client: TestClient, key: str = "listing-create-1") -> UUID:
    response = client.post(
        "/api/v1/seller/listings",
        headers={**headers(), "Idempotency-Key": key},
        json={
            "creation_method": "manual",
            "title": "2026 부산 여름 객실 공급",
            "category": "accommodation",
            "district": "해운대구",
            "language": "ko-KR",
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["data"]["listing_id"])


def save_complete_terms(client: TestClient, listing_id: UUID, base: int = 1):
    return client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={"base_version_no": base, "terms": complete_terms()},
    )


def test_create_list_and_get_draft(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)

    listing_list = listing_client.get("/api/v1/seller/listings", headers=headers())
    detail = listing_client.get(f"/api/v1/seller/listings/{listing_id}", headers=headers())

    assert listing_list.status_code == 200
    assert listing_list.json()["data"][0]["status"] == "draft"
    assert listing_list.json()["data"][0]["contract_available"] is False
    assert listing_list.json()["data"][0]["attention_required_count"] == 0
    assert detail.status_code == 200
    assert detail.json()["data"]["current_version"]["version_no"] == 1
    assert "cancellation_policy" in detail.json()["data"]["missing_fields"]


def test_create_is_idempotent_and_rejects_key_reuse(
    listing_client: TestClient, listing_repository: FakeSellerListingRepository
) -> None:
    first_id = create_listing(listing_client, "same-key")
    second_id = create_listing(listing_client, "same-key")
    conflict = listing_client.post(
        "/api/v1/seller/listings",
        headers={**headers(), "Idempotency-Key": "same-key"},
        json={
            "creation_method": "manual",
            "title": "다른 공고",
            "category": "tour",
            "district": "중구",
            "language": "ko-KR",
        },
    )

    assert first_id == second_id
    assert len(listing_repository.records) == 1
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_terms_draft_creates_new_immutable_version(
    listing_client: TestClient, listing_repository: FakeSellerListingRepository
) -> None:
    listing_id = create_listing(listing_client)
    first_version_id = listing_repository.records[listing_id].current_version_id

    response = save_complete_terms(listing_client, listing_id)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["current_version"]["version_no"] == 2
    assert len(data["current_version"]["clauses"]) == 9
    assert listing_repository.version_bodies[first_version_id] == ""
    assert data["missing_fields"] == []


def test_terms_reject_stale_base_version(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)
    assert save_complete_terms(listing_client, listing_id).status_code == 200

    response = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={"base_version_no": 1, "terms": {"supply_quantity": 40}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_complete_returns_missing_fields(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)

    response = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/complete", headers=headers()
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LISTING_NOT_PUBLISHABLE"
    assert "clauses" in response.json()["error"]["details"]["missing_fields"]


def test_complete_publish_pause_resume_and_archive_flow(
    listing_client: TestClient,
) -> None:
    listing_id = create_listing(listing_client)
    assert save_complete_terms(listing_client, listing_id).status_code == 200

    completed = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/complete", headers=headers()
    )
    published = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/publish", headers=headers()
    )
    invalid_archive = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/archive", headers=headers()
    )
    paused = listing_client.post(f"/api/v1/seller/listings/{listing_id}/pause", headers=headers())
    resumed = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/publish", headers=headers()
    )
    listing_client.post(f"/api/v1/seller/listings/{listing_id}/pause", headers=headers())
    archived = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/archive", headers=headers()
    )

    assert completed.json()["data"]["status"] == "ready"
    assert published.json()["data"]["status"] == "published"
    assert invalid_archive.status_code == 409
    assert paused.json()["data"]["status"] == "paused"
    assert resumed.json()["data"]["status"] == "published"
    assert archived.json()["data"]["status"] == "archived"


def test_pending_seller_can_publish(
    listing_client: TestClient, listing_repository: FakeSellerListingRepository
) -> None:
    listing_id = create_listing(listing_client)
    save_complete_terms(listing_client, listing_id)
    listing_client.post(f"/api/v1/seller/listings/{listing_id}/complete", headers=headers())
    membership = listing_repository.memberships[(SELLER_ID, ORGANIZATION_ID)]
    listing_repository.memberships[(SELLER_ID, ORGANIZATION_ID)] = replace(
        membership, verification_status="pending"
    )
    listing_repository.records[listing_id] = replace(
        listing_repository.records[listing_id], verification_status="pending"
    )

    response = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/publish", headers=headers()
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "published"


def test_other_organization_cannot_read_listing(app: FastAPI, listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OTHER_SELLER_ID, "other@example.test"
    )

    response = listing_client.get(
        f"/api/v1/seller/listings/{listing_id}", headers=headers(OTHER_ORGANIZATION_ID)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LISTING_NOT_FOUND"


def test_seller_organization_header_and_membership_are_required(
    app: FastAPI, listing_client: TestClient
) -> None:
    listing_id = create_listing(listing_client)
    missing_header = listing_client.get(f"/api/v1/seller/listings/{listing_id}")
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OTHER_SELLER_ID, "other@example.test"
    )
    wrong_membership = listing_client.get(
        f"/api/v1/seller/listings/{listing_id}", headers=headers()
    )

    assert missing_header.status_code == 400
    assert missing_header.json()["error"]["code"] == "ORGANIZATION_HEADER_REQUIRED"
    assert wrong_membership.status_code == 403
    assert wrong_membership.json()["error"]["code"] == "ORG_ACCESS_DENIED"


def test_draft_cannot_publish_before_complete(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)
    assert save_complete_terms(listing_client, listing_id).status_code == 200

    response = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/publish", headers=headers()
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_terms_validate_period_and_people_ranges(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)

    invalid_period = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={
            "base_version_no": 1,
            "terms": {
                "service_start_date": "2026-09-01",
                "service_end_date": "2026-08-01",
            },
        },
    )
    invalid_people = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={
            "base_version_no": 1,
            "terms": {"minimum_people": 40, "maximum_people": 20},
        },
    )

    assert invalid_period.status_code == 400
    assert invalid_period.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid_people.status_code == 400
    assert invalid_people.json()["error"]["code"] == "VALIDATION_ERROR"


def test_terms_validate_supply_quantity_range(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)

    response = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={
            "base_version_no": 1,
            "terms": {"minimum_quantity": 40, "maximum_quantity": 20},
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("terms", "error_code"),
    [
        ({"quantity_unit": "guest"}, "UNSUPPORTED_QUANTITY_UNIT"),
        ({"price_unit": "package"}, "UNSUPPORTED_PRICE_UNIT"),
        (
            {"quantity_unit": "seat", "price_unit": "vehicle"},
            "UNSUPPORTED_QUANTITY_UNIT",
        ),
    ],
)
def test_terms_reject_unsupported_or_mismatched_units(
    listing_client: TestClient,
    terms: dict[str, str],
    error_code: str,
) -> None:
    listing_id = create_listing(listing_client)

    response = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={"base_version_no": 1, "terms": terms},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == error_code


def test_seat_terms_can_complete_and_publish(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)
    terms = complete_terms()
    terms.update(
        {
            "supply_quantity_description": "투어 좌석 30석",
            "quantity_unit": "seat",
            "price_unit": "seat",
        }
    )

    saved = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={"base_version_no": 1, "terms": terms},
    )
    completed = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/complete", headers=headers()
    )
    published = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/publish", headers=headers()
    )

    assert saved.status_code == 200
    assert completed.json()["data"]["status"] == "ready"
    assert published.json()["data"]["status"] == "published"


def test_frontend_listing_fields_are_enough_to_complete_and_publish(
    listing_client: TestClient,
) -> None:
    listing_id = create_listing(listing_client)
    terms = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={
            "base_version_no": 1,
            "terms": {
                "service_start_date": "2026-08-01",
                "service_end_date": "2026-08-31",
                "supply_quantity_description": "주말 객실 최대 30실",
                "quantity_unit": "room",
                "minimum_quantity": 10,
                "maximum_quantity": 30,
                "base_price_amount_minor": 145000,
                "currency": "KRW",
                "price_unit": "room_night",
                "cancellation_policy": "체크인 7일 전까지 무료 취소",
                "no_show_policy": "객실 1박 요금 청구",
                "settlement_policy": "매월 말 마감 후 익월 15일 지급",
                "liability_policy": "각 당사자의 귀책 사유에 따른다",
                "termination_policy": "30일 전 서면 통지로 해지 가능",
                "special_terms": "성수기 별도 협의",
            },
        },
    )
    presentation = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/presentation",
        headers=headers(),
        json={"public_headline": "성수기 주말 객실을 안정적으로 확보하세요."},
    )
    completed = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/complete", headers=headers()
    )
    published = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/publish", headers=headers()
    )

    assert terms.status_code == 200
    assert terms.json()["data"]["missing_fields"] == []
    assert presentation.json()["data"]["public_headline"].startswith("성수기")
    assert completed.json()["data"]["status"] == "ready"
    assert published.json()["data"]["status"] == "published"


def test_contract_request_blocks_risky_term_change(
    listing_client: TestClient, listing_repository: FakeSellerListingRepository
) -> None:
    listing_id = create_listing(listing_client)
    save_complete_terms(listing_client, listing_id)
    listing_repository.records[listing_id] = replace(
        listing_repository.records[listing_id], contract_count=1
    )

    response = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/terms",
        headers=headers(),
        json={"base_version_no": 2, "terms": {"base_price_amount_minor": 160000}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LISTING_HAS_CONTRACTS"


def test_presentation_validates_hero_document_ownership(
    listing_client: TestClient,
) -> None:
    listing_id = create_listing(listing_client)
    denied = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/presentation",
        headers=headers(),
        json={"hero_document_id": str(uuid4())},
    )
    accepted = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/presentation",
        headers=headers(),
        json={
            "hero_document_id": str(HERO_DOCUMENT_ID),
            "display_title": "여름 객실 단체 상품",
            "price_display_basis": "30명·2박 기준",
        },
    )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "DOCUMENT_ACCESS_DENIED"
    assert accepted.status_code == 200
    assert accepted.json()["data"]["display_title"] == "여름 객실 단체 상품"


def test_archived_listing_is_immutable(listing_client: TestClient) -> None:
    listing_id = create_listing(listing_client)
    archived = listing_client.post(
        f"/api/v1/seller/listings/{listing_id}/archive", headers=headers()
    )
    changed = listing_client.patch(
        f"/api/v1/seller/listings/{listing_id}/presentation",
        headers=headers(),
        json={"display_title": "변경 시도"},
    )

    assert archived.status_code == 200
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_database_failure_is_safe(
    listing_client: TestClient, listing_repository: FakeSellerListingRepository
) -> None:
    listing_repository.unavailable = True

    response = listing_client.get("/api/v1/seller/listings", headers=headers())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "SQL" not in response.text


def test_seller_listing_api_requires_authentication(
    app: FastAPI, listing_repository: FakeSellerListingRepository
) -> None:
    app.dependency_overrides[get_seller_listing_service] = lambda: SellerListingService(
        listing_repository
    )
    app.dependency_overrides[get_auth_provider] = lambda: FakeAuthProvider({})
    with TestClient(app) as client:
        response = client.get("/api/v1/seller/listings", headers=headers())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
