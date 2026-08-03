from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
    ContractRepositoryUnavailableError,
    ContractApprovalOrderError,
    ContractStateConflictError,
    ContractVersionApprovalAccessError,
    ContractVersionApprovalContextRecord,
    ContractVersionApprovalMutationRecord,
    ContractVersionApprovalRecord,
    ContractVersionConflictError,
    ContractVersionNotFoundError,
)

CONTRACT_ID = UUID("a1000000-0000-0000-0000-000000000001")
CURRENT_VERSION_ID = UUID("a2000000-0000-0000-0000-000000000002")
OLD_VERSION_ID = UUID("a2000000-0000-0000-0000-000000000001")
BUYER_ID = UUID("a3000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("a3000000-0000-0000-0000-000000000002")
OTHER_SELLER_ID = UUID("a3000000-0000-0000-0000-000000000003")
OUTSIDER_ID = UUID("a3000000-0000-0000-0000-000000000004")
ORGANIZATION_ID = UUID("a4000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID("a4000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 7, 31, 15, tzinfo=UTC)


class FakeContractApprovalRepository:
    def __init__(self) -> None:
        self.current_context = ContractVersionApprovalContextRecord(
            contract_id=CONTRACT_ID,
            contract_version_id=CURRENT_VERSION_ID,
            version_no=2,
            buyer_user_id=BUYER_ID,
            seller_organization_id=ORGANIZATION_ID,
            contract_status="seller_review",
            current_version_id=CURRENT_VERSION_ID,
        )
        self.old_context = replace(
            self.current_context,
            contract_version_id=OLD_VERSION_ID,
            version_no=1,
        )
        self.memberships = {(SELLER_ID, ORGANIZATION_ID)}
        self.approvals: dict[tuple[UUID, str], ContractVersionApprovalRecord] = {}
        self.audit_events: list[tuple[str, str]] = []
        self.notifications: list[tuple[str, UUID]] = []
        self.unavailable = False

    async def get_contract_version_approval_context(
        self, contract_id: UUID, contract_version_id: UUID
    ):
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        if contract_id != CONTRACT_ID:
            return None
        if contract_version_id == CURRENT_VERSION_ID:
            return self.current_context
        if contract_version_id == OLD_VERSION_ID:
            return self.old_context
        return None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return (user_id, organization_id) in self.memberships

    async def list_contract_version_approvals(self, contract_version_id: UUID):
        if self.unavailable:
            raise ContractRepositoryUnavailableError
        return [
            approval
            for (version_id, _), approval in self.approvals.items()
            if version_id == contract_version_id
        ]

    async def approve_contract_version(
        self,
        *,
        contract_id: UUID,
        contract_version_id: UUID,
        actor_user_id: UUID,
        party_role: str,
    ) -> ContractVersionApprovalMutationRecord:
        context = await self.get_contract_version_approval_context(contract_id, contract_version_id)
        if context is None:
            raise ContractVersionNotFoundError
        if context.current_version_id != contract_version_id:
            raise ContractVersionConflictError
        if context.contract_status not in {"seller_review", "signing"}:
            raise ContractStateConflictError
        if party_role == "buyer" and actor_user_id != context.buyer_user_id:
            raise ContractVersionApprovalAccessError
        if party_role == "seller" and not await self.is_seller_member(
            actor_user_id, context.seller_organization_id
        ):
            raise ContractVersionApprovalAccessError
        existing_approvals = await self.list_contract_version_approvals(contract_version_id)
        if party_role == "buyer" and not any(
            approval.party_role == "seller" for approval in existing_approvals
        ):
            raise ContractApprovalOrderError
        key = (contract_version_id, party_role)
        already_approved = key in self.approvals
        if not already_approved:
            self.approvals[key] = ContractVersionApprovalRecord(
                id=uuid4(),
                contract_version_id=contract_version_id,
                party_role=party_role,
                approved_by_user_id=actor_user_id,
                approved_at=NOW,
            )
            self.audit_events.append(("contract_version_approved", party_role))
        approvals = await self.list_contract_version_approvals(contract_version_id)
        all_approved = {approval.party_role for approval in approvals} == {"buyer", "seller"}
        if not already_approved and not all_approved:
            notified_role = "seller" if party_role == "buyer" else "buyer"
            self.notifications.append((notified_role, contract_version_id))
        contract_status = context.contract_status
        if all_approved and contract_status == "seller_review":
            contract_status = "signing"
            self.current_context = replace(self.current_context, contract_status="signing")
            context = self.current_context
        return ContractVersionApprovalMutationRecord(
            context=context,
            approvals=approvals,
            approved_role=party_role,
            already_approved=already_approved,
            contract_status=contract_status,
        )


@pytest.fixture
def approval_repository() -> FakeContractApprovalRepository:
    return FakeContractApprovalRepository()


@pytest.fixture
def approval_client(
    app: FastAPI, approval_repository: FakeContractApprovalRepository
) -> TestClient:
    service = ContractService(
        approval_repository,  # type: ignore[arg-type]
        PriceCalculator(FakeExchangeRateProvider()),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    return TestClient(app)


def seller_headers(app: FastAPI, user_id: UUID = SELLER_ID) -> dict[str, str]:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=user_id, email="seller@example.test"
    )
    return {"X-Organization-Id": str(ORGANIZATION_ID)}


def buyer_headers(app: FastAPI) -> dict[str, str]:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    return {}


def test_approval_status_starts_empty(approval_client: TestClient) -> None:
    response = approval_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approvals"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_current_version"] is True
    assert data["buyer"]["approved"] is False
    assert data["seller"]["approved"] is False
    assert data["all_approved"] is False


def test_buyer_approval_requires_seller_first_and_is_idempotent(
    app: FastAPI,
    approval_client: TestClient,
    approval_repository: FakeContractApprovalRepository,
) -> None:
    url = f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approve"

    blocked = approval_client.post(url, headers=buyer_headers(app))
    seller = approval_client.post(url, headers=seller_headers(app))
    first = approval_client.post(url, headers=buyer_headers(app))
    second = approval_client.post(url, headers=buyer_headers(app))

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SELLER_APPROVAL_REQUIRED"
    assert seller.status_code == 200
    assert first.status_code == 200
    assert first.json()["data"]["approved_role"] == "buyer"
    assert first.json()["data"]["already_approved"] is False
    assert second.json()["data"]["already_approved"] is True
    assert len(approval_repository.approvals) == 2
    assert approval_repository.audit_events == [
        ("contract_version_approved", "seller"),
        ("contract_version_approved", "buyer"),
    ]
    assert approval_repository.notifications == [("buyer", CURRENT_VERSION_ID)]


def test_buyer_and_seller_must_approve_same_version(
    app: FastAPI,
    approval_client: TestClient,
    approval_repository: FakeContractApprovalRepository,
) -> None:
    url = f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approve"
    seller = approval_client.post(url, headers=seller_headers(app))
    buyer = approval_client.post(url, headers=buyer_headers(app))

    assert buyer.json()["data"]["all_approved"] is True
    assert seller.status_code == 200
    assert buyer.status_code == 200
    data = buyer.json()["data"]
    assert data["buyer"]["approved"] is True
    assert data["seller"]["approved"] is True
    assert data["all_approved"] is True
    assert data["contract_status"] == "signing"
    assert approval_repository.current_context.contract_status == "signing"
    assert approval_repository.notifications == [("buyer", CURRENT_VERSION_ID)]


def test_seller_requires_matching_organization_membership(
    app: FastAPI, approval_client: TestClient
) -> None:
    headers = seller_headers(app, OTHER_SELLER_ID)

    response = approval_client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approve",
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_approval_rejects_version_from_another_contract(
    approval_client: TestClient,
) -> None:
    response = approval_client.post(f"/api/v1/contracts/{CONTRACT_ID}/versions/{uuid4()}/approve")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_VERSION_NOT_FOUND"


def test_old_version_approval_is_not_reused_for_current_version(
    approval_client: TestClient,
    approval_repository: FakeContractApprovalRepository,
) -> None:
    approval_repository.approvals[(OLD_VERSION_ID, "buyer")] = ContractVersionApprovalRecord(
        id=uuid4(),
        contract_version_id=OLD_VERSION_ID,
        party_role="buyer",
        approved_by_user_id=BUYER_ID,
        approved_at=NOW,
    )

    old_status = approval_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{OLD_VERSION_ID}/approvals"
    )
    current_status = approval_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approvals"
    )
    old_approve = approval_client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{OLD_VERSION_ID}/approve"
    )

    assert old_status.json()["data"]["buyer"]["approved"] is True
    assert old_status.json()["data"]["is_current_version"] is False
    assert current_status.json()["data"]["buyer"]["approved"] is False
    assert old_approve.status_code == 409
    assert old_approve.json()["error"]["code"] == "VERSION_CONFLICT"


def test_approval_rejects_invalid_contract_state(
    approval_client: TestClient,
    approval_repository: FakeContractApprovalRepository,
) -> None:
    approval_repository.current_context = replace(
        approval_repository.current_context, contract_status="signed"
    )

    response = approval_client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approve"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_approval_database_failure_is_safe(
    approval_client: TestClient,
    approval_repository: FakeContractApprovalRepository,
) -> None:
    approval_repository.unavailable = True

    response = approval_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{CURRENT_VERSION_ID}/approvals"
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "SQL" not in response.text
