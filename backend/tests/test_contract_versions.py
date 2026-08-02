from copy import deepcopy
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
    ContractRecord,
    ContractRepositoryUnavailableError,
    ContractVersionClauseRecord,
    ContractVersionRecord,
)

CONTRACT_ID = UUID("91000000-0000-0000-0000-000000000001")
LISTING_ID = UUID("91000000-0000-0000-0000-000000000002")
VERSION_1_ID = UUID("92000000-0000-0000-0000-000000000001")
VERSION_2_ID = UUID("92000000-0000-0000-0000-000000000002")
SOURCE_1_ID = UUID("93000000-0000-0000-0000-000000000001")
SOURCE_2_ID = UUID("93000000-0000-0000-0000-000000000002")
SOURCE_3_ID = UUID("93000000-0000-0000-0000-000000000003")
CLAUSE_1_ID = UUID("94000000-0000-0000-0000-000000000001")
CLAUSE_2_ID = UUID("94000000-0000-0000-0000-000000000002")
CLAUSE_3_ID = UUID("94000000-0000-0000-0000-000000000003")
CLAUSE_4_ID = UUID("94000000-0000-0000-0000-000000000004")
CLAUSE_5_ID = UUID("94000000-0000-0000-0000-000000000005")
BUYER_ID = UUID("95000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("95000000-0000-0000-0000-000000000002")
OUTSIDER_ID = UUID("95000000-0000-0000-0000-000000000003")
ORGANIZATION_ID = UUID("96000000-0000-0000-0000-000000000001")
REVISION_ID = UUID("97000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


def contract_record() -> ContractRecord:
    return ContractRecord(
        id=CONTRACT_ID,
        listing_id=LISTING_ID,
        listing_title="부산 숙박 계약",
        buyer_user_id=BUYER_ID,
        seller_organization_id=ORGANIZATION_ID,
        status="signing",
        initial_request_kind="revision",
        request_message="취소 조건 수정",
        requested_people=10,
        buyer_group_name=None,
        signing_capacity="self",
        amount_minor=1_200_000,
        currency="KRW",
        service_start_date=date(2026, 9, 2),
        service_end_date=date(2026, 9, 5),
        calculation_snapshot={
            "quantity": 10,
            "quantity_unit": "person",
            "nights": 3,
            "formula": "120000 KRW × 10 person",
        },
        current_version_id=VERSION_2_ID,
        version_no=2,
        version_title="부산 숙박 계약",
        version_body="변경된 계약",
        buyer_name="Buyer Snapshot",
        buyer_country_code="JP",
        buyer_group_name_snapshot=None,
        buyer_signing_capacity="self",
        seller_name="Seller Snapshot",
        created_at=NOW,
        updated_at=NOW,
        cancelled_at=None,
    )


def clause(
    clause_id: UUID,
    order: int,
    key: str | None,
    title: str,
    body: str,
    source_id: UUID | None,
) -> ContractVersionClauseRecord:
    return ContractVersionClauseRecord(
        id=clause_id,
        clause_order=order,
        clause_key=key,
        title=title,
        body=body,
        source_listing_clause_id=source_id,
    )


class FakeContractVersionRepository:
    def __init__(self) -> None:
        self.contract = contract_record()
        self.memberships = {(SELLER_ID, ORGANIZATION_ID)}
        self.unavailable = False
        self.versions = [
            ContractVersionRecord(
                id=VERSION_1_ID,
                contract_id=CONTRACT_ID,
                version_no=1,
                title="부산 숙박 계약",
                structured_data={
                    "contract_terms": {
                        "amount_minor": 1_000_000,
                        "currency": "KRW",
                        "service_start_date": "2026-09-01",
                        "service_end_date": "2026-09-04",
                    }
                },
                created_by_role="buyer",
                creation_reason="contract_created",
                created_from_revision_request_id=None,
                created_at=NOW,
                risk_score=6,
                risk_finding_count=3,
                clauses=[
                    clause(
                        CLAUSE_1_ID,
                        1,
                        "price",
                        "가격",
                        "총액은 1,000,000원입니다.",
                        SOURCE_1_ID,
                    ),
                    clause(
                        CLAUSE_2_ID,
                        2,
                        "cancel",
                        "취소",
                        "취소할 수 없습니다.",
                        SOURCE_2_ID,
                    ),
                    clause(
                        CLAUSE_3_ID,
                        3,
                        "penalty",
                        "위약금",
                        "위약금은 50%입니다.",
                        SOURCE_3_ID,
                    ),
                ],
            ),
            ContractVersionRecord(
                id=VERSION_2_ID,
                contract_id=CONTRACT_ID,
                version_no=2,
                title="부산 숙박 계약",
                structured_data={
                    "contract_terms": {
                        "amount_minor": 1_200_000,
                        "currency": "KRW",
                        "service_start_date": "2026-09-02",
                        "service_end_date": "2026-09-05",
                    }
                },
                created_by_role="seller",
                creation_reason="revision_agreement",
                created_from_revision_request_id=REVISION_ID,
                created_at=NOW,
                risk_score=3,
                risk_finding_count=2,
                clauses=[
                    clause(
                        CLAUSE_4_ID,
                        1,
                        "price",
                        "가격",
                        "총액은 1,200,000원입니다.",
                        SOURCE_1_ID,
                    ),
                    clause(
                        CLAUSE_2_ID,
                        2,
                        "cancel",
                        "취소",
                        "취소할 수 없습니다.",
                        SOURCE_2_ID,
                    ),
                    clause(
                        CLAUSE_5_ID,
                        3,
                        None,
                        "안전",
                        "비상 연락망을 제공합니다.",
                        None,
                    ),
                ],
            ),
        ]

    async def get_contract(self, contract_id: UUID):
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return self.contract if contract_id == CONTRACT_ID else None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return (user_id, organization_id) in self.memberships

    async def list_contract_versions(self, contract_id: UUID):
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return self.versions if contract_id == CONTRACT_ID else []


@pytest.fixture
def version_repository() -> FakeContractVersionRepository:
    return FakeContractVersionRepository()


@pytest.fixture
def version_client(app: FastAPI, version_repository: FakeContractVersionRepository) -> TestClient:
    service = ContractService(
        version_repository,  # type: ignore[arg-type]
        PriceCalculator(FakeExchangeRateProvider()),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    return TestClient(app)


def test_buyer_lists_contract_versions(version_client: TestClient) -> None:
    response = version_client.get(f"/api/v1/contracts/{CONTRACT_ID}/versions")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [row["version_label"] for row in data] == ["V1", "V2"]
    assert [row["created_by_role"] for row in data] == ["buyer", "seller"]
    assert [row["creation_reason"] for row in data] == [
        "contract_created",
        "revision_agreement",
    ]
    assert data[1]["created_from_revision_request_id"] == str(REVISION_ID)
    assert data[1]["risk"] == {"score": 3, "finding_count": 2}


def test_seller_member_can_list_versions(app: FastAPI, version_client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=SELLER_ID, email="seller@example.test"
    )

    response = version_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions",
        headers={"X-Organization-Id": str(ORGANIZATION_ID)},
    )

    assert response.status_code == 200


def test_non_party_cannot_list_versions(app: FastAPI, version_client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OUTSIDER_ID, email="outsider@example.test"
    )

    response = version_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions",
        headers={"X-Organization-Id": str(ORGANIZATION_ID)},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_compare_versions_returns_clause_price_period_and_risk_changes(
    version_client: TestClient,
    version_repository: FakeContractVersionRepository,
) -> None:
    original_versions = deepcopy(version_repository.versions)
    response = version_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/compare",
        params={"from": 1, "to": 2},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["clause_summary"] == {"added": 1, "deleted": 1, "modified": 1}
    assert [change["change_type"] for change in data["clause_changes"]] == [
        "modified",
        "deleted",
        "added",
    ]
    assert data["price_change"] == {
        "direction": "increased",
        "before": {"amount_minor": 1_000_000, "currency": "KRW"},
        "after": {"amount_minor": 1_200_000, "currency": "KRW"},
        "delta_amount_minor": 200_000,
    }
    assert data["period_change"]["changed"] is True
    assert data["risk_change"]["direction"] == "decreased"
    assert data["risk_change"]["before_score"] == 6
    assert data["risk_change"]["after_score"] == 3
    assert version_repository.versions == original_versions


def test_compare_returns_unknown_when_stored_snapshots_are_missing(
    version_client: TestClient,
    version_repository: FakeContractVersionRepository,
) -> None:
    version_repository.versions[0] = replace(
        version_repository.versions[0],
        structured_data={},
        risk_score=None,
    )

    response = version_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/compare",
        params={"from": 1, "to": 2},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["price_change"]["direction"] == "unknown"
    assert data["period_change"]["changed"] is None
    assert data["risk_change"]["direction"] == "unknown"


def test_compare_rejects_same_version(version_client: TestClient) -> None:
    response = version_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/compare",
        params={"from": 1, "to": 1},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VERSION_COMPARE_INVALID"


def test_compare_rejects_missing_version(version_client: TestClient) -> None:
    response = version_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/compare",
        params={"from": 1, "to": 4},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_VERSION_NOT_FOUND"


def test_version_database_failure_is_safe(
    version_client: TestClient,
    version_repository: FakeContractVersionRepository,
) -> None:
    version_repository.unavailable = True

    response = version_client.get(f"/api/v1/contracts/{CONTRACT_ID}/versions")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "SQL" not in response.text
