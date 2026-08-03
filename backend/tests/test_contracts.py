from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_contract_service
from app.core.auth import get_current_user
from app.domain.contracts.service import ContractService
from app.domain.pricing.service import PriceCalculator
from app.integrations.auth import AuthenticatedUser
from app.integrations.exchange_rates import FakeExchangeRateProvider
from app.repositories.contracts import (
    ContractClauseRecord,
    ContractCreatedRecord,
    ContractRecord,
    ContractRepositoryUnavailableError,
    ContractRequestSourceRecord,
    ContractStateConflictError,
    IdempotencyConflictError,
    NewContractData,
    SellerListingRequestCountRecord,
)

LISTING_ID = UUID("80000000-0000-0000-0000-000000000001")
CONTRACT_ID = UUID("81000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("82000000-0000-0000-0000-000000000001")
CLAUSE_ID = UUID("83000000-0000-0000-0000-000000000001")
BUYER_ID = UUID("84000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("84000000-0000-0000-0000-000000000002")
OUTSIDER_ID = UUID("84000000-0000-0000-0000-000000000003")
ORGANIZATION_ID = UUID("85000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


def request_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "people": 30,
        "quantity": 15,
        "quantity_unit": "room",
        "nights": 2,
        "start_date": "2026-08-10",
        "end_date": "2026-08-12",
        "currency": "KRW",
        "group_name": "부산 여름여행 모임",
        "signing_capacity": "group_representative",
        "request_message": "금연 객실을 요청합니다.",
        "initial_request_kind": "as_is",
    }
    payload.update(changes)
    return payload


def contract_record(**changes: object) -> ContractRecord:
    values: dict[str, object] = {
        "id": CONTRACT_ID,
        "listing_id": LISTING_ID,
        "listing_title": "부산 객실 공급 계약",
        "buyer_user_id": BUYER_ID,
        "seller_organization_id": ORGANIZATION_ID,
        "status": "seller_review",
        "initial_request_kind": "as_is",
        "request_message": "금연 객실을 요청합니다.",
        "requested_people": 30,
        "buyer_group_name": "부산 여름여행 모임",
        "signing_capacity": "group_representative",
        "amount_minor": 3_000_000,
        "currency": "KRW",
        "service_start_date": date(2026, 8, 10),
        "service_end_date": date(2026, 8, 12),
        "calculation_snapshot": {
            "quantity": 15,
            "quantity_unit": "room",
            "nights": 2,
            "formula": "100000 KRW × 15 room × 2 nights",
        },
        "current_version_id": VERSION_ID,
        "version_no": 1,
        "version_title": "부산 객실 공급 계약",
        "version_body": "공개 공고에서 복사한 계약 본문",
        "buyer_name": "Buyer Snapshot",
        "buyer_country_code": "JP",
        "buyer_group_name_snapshot": "부산 여름여행 모임",
        "buyer_signing_capacity": "group_representative",
        "seller_name": "Seller Snapshot",
        "created_at": NOW,
        "updated_at": NOW,
        "cancelled_at": None,
    }
    values.update(changes)
    return ContractRecord(**values)  # type: ignore[arg-type]


class FakeContractRepository:
    def __init__(self) -> None:
        self.source = ContractRequestSourceRecord(
            listing_id=LISTING_ID,
            listing_status="published",
            listing_expires_at=datetime(2026, 12, 31, tzinfo=UTC),
            seller_organization_id=ORGANIZATION_ID,
            listing_title="부산 객실 공급 계약",
            current_version_id=VERSION_ID,
            service_start_date=date(2026, 8, 1),
            service_end_date=date(2026, 12, 31),
            quantity_unit="room",
            base_price_amount_minor=100_000,
            currency="KRW",
            price_unit="room_night",
            buyer_name="Buyer Snapshot",
            buyer_country_code="JP",
            buyer_phone="private-phone",
            seller_name="Seller Snapshot",
            seller_legal_name="Private Seller Legal Name",
            seller_business_registration_no="private-registration",
        )
        self.records: list[ContractRecord] = [contract_record()]
        self.clauses = [
            ContractClauseRecord(
                id=CLAUSE_ID,
                clause_order=1,
                clause_key="price",
                title="가격",
                body="객실당 1박 가격을 적용합니다.",
            )
        ]
        self.memberships = {(SELLER_ID, ORGANIZATION_ID)}
        self.unread_contract_ids: set[UUID] = set()
        self.listing_request_counts = [
            SellerListingRequestCountRecord(
                listing_id=LISTING_ID,
                listing_title="부산 객실 공급 계약",
                listing_status="published",
                request_count=1,
            )
        ]
        self.idempotency: dict[str, tuple[str, ContractCreatedRecord]] = {}
        self.created_data: list[NewContractData] = []
        self.party_snapshots: list[dict[str, object]] = []
        self.audit_events: list[str] = []
        self.notifications: list[str] = []
        self.copied_versions: list[UUID] = []
        self.copied_clause_counts: list[int] = []
        self.build_calls = 0
        self.fail_after_build = False
        self.unavailable = False

    async def create_contract_request(
        self,
        *,
        listing_id: UUID,
        buyer_user_id: UUID,
        buyer_email: str | None,
        idempotency_key: str,
        request_hash: str,
        build,
    ) -> ContractCreatedRecord:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        if idempotency_key in self.idempotency:
            stored_hash, created = self.idempotency[idempotency_key]
            if stored_hash != request_hash:
                raise IdempotencyConflictError
            return created
        self.build_calls += 1
        data = await build(self.source if listing_id == LISTING_ID else None)
        if self.fail_after_build:
            raise ContractRepositoryUnavailableError
        created = ContractCreatedRecord(contract_id=CONTRACT_ID, status=data.status)
        self.created_data.append(data)
        self.party_snapshots.append(
            {
                "buyer_user_id": buyer_user_id,
                "buyer_organization_id": None,
                "buyer_name": self.source.buyer_name,
                "buyer_country_code": self.source.buyer_country_code,
                "buyer_email": buyer_email,
                "buyer_phone": self.source.buyer_phone,
                "seller_organization_id": self.source.seller_organization_id,
                "seller_name": self.source.seller_name,
                "group_name": data.buyer_group_name,
                "group_size": data.requested_people,
                "signing_capacity": data.signing_capacity,
                "participant_accounts": 0,
            }
        )
        self.audit_events.append("contract_requested")
        self.notifications.append("contract_requested")
        assert self.source.current_version_id is not None
        self.copied_versions.append(self.source.current_version_id)
        self.copied_clause_counts.append(len(self.clauses))
        self.idempotency[idempotency_key] = (request_hash, created)
        return created

    async def get_contract(self, contract_id: UUID) -> ContractRecord | None:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return next((row for row in self.records if row.id == contract_id), None)

    async def list_buyer_contracts(self, buyer_user_id: UUID) -> list[ContractRecord]:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return [row for row in self.records if row.buyer_user_id == buyer_user_id]

    async def list_seller_contracts(self, seller_organization_id: UUID) -> list[ContractRecord]:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return [row for row in self.records if row.seller_organization_id == seller_organization_id]

    async def list_unread_response_contract_ids(
        self, buyer_user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        if buyer_user_id != BUYER_ID:
            return set()
        return self.unread_contract_ids.intersection(contract_ids)

    async def list_seller_listing_request_counts(
        self, seller_organization_id: UUID
    ) -> list[SellerListingRequestCountRecord]:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return self.listing_request_counts if seller_organization_id == ORGANIZATION_ID else []

    async def list_contract_clauses(self, contract_version_id: UUID) -> list[ContractClauseRecord]:
        return self.clauses if contract_version_id == VERSION_ID else []

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        return (user_id, organization_id) in self.memberships

    async def cancel_contract(
        self,
        *,
        contract_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[datetime, bool]:
        key = f"cancel:{idempotency_key}"
        if key in self.idempotency:
            stored_hash, _ = self.idempotency[key]
            if stored_hash != request_hash:
                raise IdempotencyConflictError
            record = await self.get_contract(contract_id)
            assert record is not None and record.cancelled_at is not None
            return record.cancelled_at, True
        record = await self.get_contract(contract_id)
        if record is None or record.status not in {"draft", "seller_review", "revision_requested"}:
            raise ContractStateConflictError
        cancelled_at = NOW
        self.records = [
            replace(row, status="cancelled", cancelled_at=cancelled_at)
            if row.id == contract_id
            else row
            for row in self.records
        ]
        self.audit_events.append(f"contract_cancelled:{actor_role}:{actor_user_id}")
        self.idempotency[key] = (
            request_hash,
            ContractCreatedRecord(contract_id=contract_id, status="cancelled"),
        )
        return cancelled_at, False


@pytest.fixture
def buyer() -> AuthenticatedUser:
    return AuthenticatedUser(id=BUYER_ID, email="buyer@example.test")


@pytest.fixture
def contract_repository() -> FakeContractRepository:
    return FakeContractRepository()


@pytest.fixture
def contract_client(
    app: FastAPI,
    contract_repository: FakeContractRepository,
    buyer: AuthenticatedUser,
) -> TestClient:
    calculator = PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW)
    service = ContractService(
        contract_repository,
        calculator,
        today=lambda: date(2026, 7, 31),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: buyer
    with TestClient(app) as client:
        yield client


def post_request(
    client: TestClient,
    payload: dict[str, object] | None = None,
    *,
    key: str = "contract-request-1",
):
    return client.post(
        f"/api/v1/listings/{LISTING_ID}/contract-requests",
        json=payload or request_payload(),
        headers={"Idempotency-Key": key},
    )


@pytest.mark.parametrize(
    ("kind", "expected_status"),
    [("as_is", "seller_review"), ("revision", "revision_requested")],
)
def test_contract_request_creates_expected_initial_state(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
    kind: str,
    expected_status: str,
) -> None:
    response = post_request(
        contract_client,
        request_payload(initial_request_kind=kind),
        key=f"kind-{kind}",
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "contract_id": str(CONTRACT_ID),
        "version_no": 1,
        "status": expected_status,
    }
    assert contract_repository.created_data[-1].status == expected_status
    assert contract_repository.audit_events[-1] == "contract_requested"
    assert contract_repository.notifications[-1] == "contract_requested"
    assert contract_repository.copied_versions[-1] == VERSION_ID
    assert contract_repository.copied_clause_counts[-1] == 1


def test_contract_request_can_use_a_subset_of_listing_supply_period(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    """A buyer may request part of the published period, not only the full period."""
    contract_repository.source = replace(
        contract_repository.source,
        service_start_date=date(2026, 8, 1),
        service_end_date=date(2026, 8, 31),
    )

    response = post_request(
        contract_client,
        request_payload(
            nights=3,
            start_date="2026-08-10",
            end_date="2026-08-13",
            initial_request_kind="as_is",
        ),
        key="subset-of-listing-period",
    )

    assert response.status_code == 200
    assert contract_repository.created_data[-1].service_start_date == date(2026, 8, 10)
    assert contract_repository.created_data[-1].service_end_date == date(2026, 8, 13)


def test_published_seat_listing_accepts_contract_request_with_same_unit(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.source = replace(
        contract_repository.source,
        quantity_unit="seat",
        price_unit="seat",
    )

    response = post_request(
        contract_client,
        request_payload(people=4, quantity=4, quantity_unit="seat"),
        key="published-seat-listing",
    )

    assert response.status_code == 200
    created = contract_repository.created_data[-1]
    assert created.amount_minor == 400_000
    assert created.calculation_snapshot["formula"] == "100000 KRW × 4 seat"


def test_individual_group_representative_is_snapshotted(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    response = post_request(contract_client)

    assert response.status_code == 200
    snapshot = contract_repository.party_snapshots[-1]
    assert snapshot["buyer_user_id"] == BUYER_ID
    assert snapshot["buyer_organization_id"] is None
    assert snapshot["buyer_name"] == "Buyer Snapshot"
    assert snapshot["buyer_email"] == "buyer@example.test"
    assert snapshot["group_name"] == "부산 여름여행 모임"
    assert snapshot["group_size"] == 30
    assert snapshot["signing_capacity"] == "group_representative"
    assert snapshot["participant_accounts"] == 0


def test_group_representative_requires_group_name(contract_client: TestClient) -> None:
    response = post_request(contract_client, request_payload(group_name=None))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("listing_status", ["paused", "draft", "archived"])
def test_non_published_listing_rejects_contract_request(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
    listing_status: str,
) -> None:
    contract_repository.source = replace(contract_repository.source, listing_status=listing_status)

    response = post_request(contract_client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.parametrize(
    "changes",
    [
        {"listing_status": "expired"},
        {"listing_expires_at": datetime(2026, 7, 30, tzinfo=UTC)},
        {"service_end_date": date(2026, 7, 30)},
    ],
)
def test_expired_listing_rejects_contract_request(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
    changes: dict[str, object],
) -> None:
    contract_repository.source = replace(contract_repository.source, **changes)

    response = post_request(contract_client)

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "LISTING_EXPIRED"


def test_listing_without_current_version_is_rejected(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.source = replace(contract_repository.source, current_version_id=None)

    response = post_request(contract_client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LISTING_VERSION_REQUIRED"


def test_seller_member_cannot_create_contract_as_its_own_buyer(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.memberships.add((BUYER_ID, ORGANIZATION_ID))

    response = post_request(contract_client, key="seller-cannot-self-contract")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_PARTY_CONFLICT"
    assert contract_repository.created_data == []


def test_server_recalculates_price_and_rejects_client_total(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    response = post_request(contract_client)

    assert response.status_code == 200
    data = contract_repository.created_data[-1]
    assert data.amount_minor == 3_000_000
    assert data.calculation_snapshot["quantity"] == 15
    assert data.calculation_snapshot["nights"] == 2
    assert data.calculation_snapshot["formula"] == "100000 KRW × 15 room × 2 nights"

    tampered = post_request(
        contract_client,
        request_payload(total_estimated_amount_minor=1),
        key="tampered",
    )
    assert tampered.status_code == 400
    assert tampered.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_request_is_idempotent(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    first = post_request(contract_client)
    second = post_request(contract_client)

    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    assert contract_repository.build_calls == 1
    assert len(contract_repository.created_data) == 1


def test_reusing_idempotency_key_for_different_payload_is_rejected(
    contract_client: TestClient,
) -> None:
    assert post_request(contract_client).status_code == 200

    response = post_request(
        contract_client,
        request_payload(request_message="다른 요청"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_intermediate_failure_rolls_back_all_contract_effects(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.fail_after_build = True

    response = post_request(contract_client)

    assert response.status_code == 503
    assert contract_repository.created_data == []
    assert contract_repository.party_snapshots == []
    assert contract_repository.audit_events == []
    assert contract_repository.notifications == []
    assert contract_repository.copied_versions == []
    assert contract_repository.copied_clause_counts == []
    assert contract_repository.idempotency == {}


def test_contract_detail_exposes_snapshot_without_private_contact_data(
    contract_client: TestClient,
) -> None:
    response = contract_client.get(f"/api/v1/contracts/{CONTRACT_ID}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parties"][0]["name"] == "Buyer Snapshot"
    assert data["parties"][1]["name"] == "Seller Snapshot"
    assert data["current_version"]["clauses"][0]["id"] == str(CLAUSE_ID)
    assert "email" not in response.text
    assert "phone" not in response.text
    assert "registration" not in response.text
    assert "Private Seller Legal Name" not in response.text


def test_buyer_contract_list_is_scoped_to_authenticated_user(
    contract_client: TestClient,
) -> None:
    response = contract_client.get("/api/v1/me/contracts")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [str(CONTRACT_ID)]


def test_buyer_contract_list_returns_screen_labels_and_unread_badge(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    statuses = [
        ("seller_review", date(2026, 8, 12), "seller_review", "셀러 검토 중"),
        ("revision_requested", date(2026, 8, 12), "revision_requested", "협상 중"),
        ("signing", date(2026, 8, 12), "signing", "서명 대기"),
        ("signed", date(2026, 8, 12), "signed", "체결 완료"),
        ("signed", date(2026, 7, 30), "finished", "종료"),
        ("cancelled", date(2026, 8, 12), "cancelled", "종료"),
    ]
    contract_repository.records = [
        contract_record(
            id=UUID(int=900 + index),
            status=contract_status,
            service_end_date=end_date,
        )
        for index, (contract_status, end_date, _, _) in enumerate(statuses)
    ]
    unread_id = contract_repository.records[1].id
    contract_repository.unread_contract_ids = {unread_id}

    response = contract_client.get("/api/v1/me/contracts")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [(row["bucket"], row["status_label"]) for row in data] == [
        (bucket, label) for _, _, bucket, label in statuses
    ]
    assert [row["has_unread_response"] for row in data] == [
        False,
        True,
        False,
        False,
        False,
        False,
    ]
    assert data[1]["status"] == "revision_requested"
    assert "응답 도착" not in {row["status"] for row in data}


def test_buyer_contract_list_filters_by_screen_bucket(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    negotiating_id = UUID("81000000-0000-0000-0000-000000000002")
    contract_repository.records = [
        contract_record(),
        contract_record(id=negotiating_id, status="revision_requested"),
    ]

    response = contract_client.get("/api/v1/me/contracts", params={"bucket": "revision_requested"})

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [str(negotiating_id)]


def test_buyer_contract_list_database_failure_is_safe(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.unavailable = True

    response = contract_client.get("/api/v1/me/contracts")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "SQL" not in response.text


def test_contract_detail_returns_unread_response_for_buyer(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.unread_contract_ids = {CONTRACT_ID}

    response = contract_client.get(f"/api/v1/contracts/{CONTRACT_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["has_unread_response"] is True


def test_unauthorized_seller_received_list_is_rejected(
    app: FastAPI,
    contract_repository: FakeContractRepository,
) -> None:
    service = ContractService(
        contract_repository,
        PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OUTSIDER_ID, email="outsider@example.test"
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/seller/contracts/received",
            headers={"X-Organization-Id": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_authorized_seller_can_list_and_read_received_contracts(
    app: FastAPI,
    contract_repository: FakeContractRepository,
) -> None:
    service = ContractService(
        contract_repository,
        PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=SELLER_ID, email="seller@example.test"
    )
    headers = {"X-Organization-Id": str(ORGANIZATION_ID)}
    with TestClient(app) as client:
        received = client.get("/api/v1/seller/contracts/received", headers=headers)
        detail = client.get(f"/api/v1/contracts/{CONTRACT_ID}", headers=headers)

    assert received.status_code == 200
    assert detail.status_code == 200


def test_seller_received_list_contains_requested_screen_fields(
    app: FastAPI,
    contract_repository: FakeContractRepository,
) -> None:
    service = ContractService(
        contract_repository,
        PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=SELLER_ID, email="seller@example.test"
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/seller/contracts/received",
            headers={"X-Organization-Id": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row == {
        "contract_id": str(CONTRACT_ID),
        "listing_id": str(LISTING_ID),
        "listing_title": "부산 객실 공급 계약",
        "buyer_name": "Buyer Snapshot",
        "buyer_group_name": "부산 여름여행 모임",
        "requested_people": 30,
        "service_start_date": "2026-08-10",
        "service_end_date": "2026-08-12",
        "amount_minor": 3_000_000,
        "currency": "KRW",
        "initial_request_kind": "as_is",
        "request_kind_label": "조건 그대로",
        "status": "seller_review",
        "status_label": "셀러 검토 중",
        "buyer_approved": False,
        "seller_approved": False,
        "final_approval_requested": False,
        "requested_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    assert "email" not in response.text
    assert "phone" not in response.text
    assert "registration" not in response.text


def test_seller_dashboard_returns_status_and_listing_request_counts(
    app: FastAPI,
    contract_repository: FakeContractRepository,
) -> None:
    contract_repository.records = [
        contract_record(id=UUID(int=1001), status="seller_review"),
        contract_record(id=UUID(int=1002), status="revision_requested"),
        contract_record(id=UUID(int=1003), status="signing"),
        contract_record(id=UUID(int=1004), status="signed"),
        contract_record(id=UUID(int=1005), status="cancelled"),
    ]
    second_listing_id = UUID("80000000-0000-0000-0000-000000000002")
    contract_repository.listing_request_counts = [
        SellerListingRequestCountRecord(
            listing_id=LISTING_ID,
            listing_title="부산 객실 공급 계약",
            listing_status="published",
            request_count=5,
        ),
        SellerListingRequestCountRecord(
            listing_id=second_listing_id,
            listing_title="요청 없는 공고",
            listing_status="draft",
            request_count=0,
        ),
    ]
    service = ContractService(
        contract_repository,
        PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=SELLER_ID, email="seller@example.test"
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/seller/dashboard",
            headers={"X-Organization-Id": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["stats"] == {
        "published_listings": 1,
        "received_requests": 5,
        "seller_review": 1,
        "revision_requested": 1,
        "signing": 1,
        "signed": 1,
        "cancelled": 1,
    }
    assert len(data["recent_requests"]) == 5
    assert [row["request_count"] for row in data["listing_request_counts"]] == [5, 0]


def test_unauthorized_seller_dashboard_is_rejected(
    app: FastAPI,
    contract_repository: FakeContractRepository,
) -> None:
    service = ContractService(
        contract_repository,
        PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OUTSIDER_ID, email="outsider@example.test"
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/seller/dashboard",
            headers={"X-Organization-Id": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_seller_dashboard_database_failure_is_safe(
    app: FastAPI,
    contract_repository: FakeContractRepository,
) -> None:
    service = ContractService(
        contract_repository,
        PriceCalculator(FakeExchangeRateProvider(), now=lambda: NOW),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=SELLER_ID, email="seller@example.test"
    )
    contract_repository.unavailable = True
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/seller/dashboard",
            headers={"X-Organization-Id": str(ORGANIZATION_ID)},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_contract_can_be_cancelled_idempotently(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
) -> None:
    headers = {"Idempotency-Key": "cancel-1"}
    first = contract_client.post(f"/api/v1/contracts/{CONTRACT_ID}/cancel", headers=headers)
    second = contract_client.post(f"/api/v1/contracts/{CONTRACT_ID}/cancel", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["status"] == "cancelled"
    assert len([event for event in contract_repository.audit_events if "cancelled" in event]) == 1


@pytest.mark.parametrize("contract_status", ["signing", "signed"])
def test_invalid_cancel_state_is_rejected(
    contract_client: TestClient,
    contract_repository: FakeContractRepository,
    contract_status: str,
) -> None:
    contract_repository.records = [contract_record(status=contract_status)]

    response = contract_client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/cancel",
        headers={"Idempotency-Key": "cancel-invalid"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_openapi_contains_contract_request_and_query_endpoints(
    contract_client: TestClient,
) -> None:
    paths = contract_client.get("/openapi.json").json()["paths"]

    assert "/api/v1/listings/{listing_id}/contract-requests" in paths
    assert "/api/v1/contracts/{contract_id}" in paths
    assert "/api/v1/me/contracts" in paths
    assert "/api/v1/seller/contracts/received" in paths
    assert "/api/v1/seller/dashboard" in paths
    assert "/api/v1/contracts/{contract_id}/cancel" in paths
