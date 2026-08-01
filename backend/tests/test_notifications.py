from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_notification_service
from app.core.auth import get_auth_provider, get_current_user
from app.domain.notifications.service import NotificationService
from app.integrations.auth import AuthenticatedUser, FakeAuthProvider
from app.repositories.notifications import (
    ContractAuditAccessRecord,
    ContractAuditEventRecord,
    NotificationRecord,
    NotificationRepositoryError,
)

BUYER_ID = UUID("d1000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("d1000000-0000-0000-0000-000000000002")
OUTSIDER_ID = UUID("d1000000-0000-0000-0000-000000000003")
ORGANIZATION_ID = UUID("d2000000-0000-0000-0000-000000000001")
CONTRACT_ID = UUID("d3000000-0000-0000-0000-000000000001")
LISTING_ID = UUID("d4000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[UUID, tuple[UUID, NotificationRecord]] = {}
        self.deadline_keys: set[tuple[UUID, UUID]] = set()
        self.materialize_calls = 0
        self.access = ContractAuditAccessRecord(
            contract_id=CONTRACT_ID,
            buyer_user_id=BUYER_ID,
            seller_organization_id=ORGANIZATION_ID,
        )
        self.members = {(SELLER_ID, ORGANIZATION_ID)}
        self.audit_events = [
            ContractAuditEventRecord(
                id=UUID(int=1),
                event_type="contract_requested",
                actor_role="buyer",
                target_type="contract",
                target_id=CONTRACT_ID,
                event_data={"status": "seller_review"},
                created_at=NOW,
            ),
            ContractAuditEventRecord(
                id=UUID(int=2),
                event_type="revision_sent",
                actor_role="buyer",
                target_type="revision_request",
                target_id=UUID(int=10),
                event_data={},
                created_at=NOW.replace(hour=13),
            ),
        ]
        self.unavailable = False

    def add_notification(
        self,
        user_id: UUID,
        notification_type: str,
        *,
        read: bool = False,
        resource_type: str = "contract",
        resource_id: UUID = CONTRACT_ID,
    ) -> UUID:
        notification_id = uuid4()
        self.notifications[notification_id] = (
            user_id,
            NotificationRecord(
                id=notification_id,
                notification_type=notification_type,
                title=f"{notification_type} 제목",
                body=f"{notification_type} 내용",
                resource_type=resource_type,
                resource_id=resource_id,
                read_at=NOW if read else None,
                created_at=NOW,
            ),
        )
        return notification_id

    def _check(self) -> None:
        if self.unavailable:
            raise NotificationRepositoryError

    async def materialize_listing_expiring_notifications(
        self, user_id: UUID, today: date, warning_days: int
    ) -> None:
        self._check()
        self.materialize_calls += 1
        if user_id != SELLER_ID or (user_id, LISTING_ID) in self.deadline_keys:
            return
        assert today == date(2026, 7, 31)
        assert warning_days == 7
        self.deadline_keys.add((user_id, LISTING_ID))
        self.add_notification(
            user_id,
            "listing_expiring",
            resource_type="listing",
            resource_id=LISTING_ID,
        )

    async def list_notifications(self, user_id: UUID, *, unread_only: bool, limit: int):
        self._check()
        rows = [
            record
            for owner_id, record in self.notifications.values()
            if owner_id == user_id and (not unread_only or record.read_at is None)
        ]
        return rows[:limit]

    async def count_unread_notifications(self, user_id: UUID) -> int:
        self._check()
        return sum(
            owner_id == user_id and record.read_at is None
            for owner_id, record in self.notifications.values()
        )

    async def mark_notification_read(self, notification_id: UUID, user_id: UUID):
        self._check()
        owned = self.notifications.get(notification_id)
        if owned is None or owned[0] != user_id:
            return None
        record = owned[1]
        if record.read_at is None:
            record = replace(record, read_at=NOW)
            self.notifications[notification_id] = (user_id, record)
        return record

    async def get_contract_audit_access(self, contract_id: UUID):
        self._check()
        return self.access if contract_id == CONTRACT_ID else None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        self._check()
        return (user_id, organization_id) in self.members

    async def list_contract_audit_events(self, contract_id: UUID):
        self._check()
        return self.audit_events if contract_id == CONTRACT_ID else []


@pytest.fixture
def notification_repository() -> FakeNotificationRepository:
    return FakeNotificationRepository()


@pytest.fixture
def notification_client(
    app: FastAPI, notification_repository: FakeNotificationRepository
) -> TestClient:
    service = NotificationService(notification_repository, today=lambda: date(2026, 7, 31))
    app.dependency_overrides[get_notification_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        BUYER_ID, "buyer@example.test"
    )
    return TestClient(app)


def seller_actor(app: FastAPI) -> dict[str, str]:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )
    return {"X-Organization-Id": str(ORGANIZATION_ID)}


def test_notification_list_returns_supported_events_and_unread_count(
    notification_client: TestClient,
    notification_repository: FakeNotificationRepository,
) -> None:
    for notification_type in (
        "revision_requested",
        "revision_decided",
        "final_approval_requested",
        "signature_requested",
        "signature_completed",
    ):
        notification_repository.add_notification(BUYER_ID, notification_type)
    notification_repository.add_notification(BUYER_ID, "contract_cancelled", read=True)

    response = notification_client.get("/api/v1/notifications")

    assert response.status_code == 200
    data = response.json()["data"]
    assert {item["notification_type"] for item in data["items"]} == {
        "revision_requested",
        "revision_decided",
        "final_approval_requested",
        "signature_requested",
        "signature_completed",
        "contract_cancelled",
    }
    assert data["unread_count"] == 5


def test_unread_filter_excludes_read_notifications(
    notification_client: TestClient,
    notification_repository: FakeNotificationRepository,
) -> None:
    notification_repository.add_notification(BUYER_ID, "revision_decided")
    notification_repository.add_notification(BUYER_ID, "signature_completed", read=True)

    response = notification_client.get("/api/v1/notifications", params={"unread_only": "true"})

    assert response.status_code == 200
    assert [item["notification_type"] for item in response.json()["data"]["items"]] == [
        "revision_decided"
    ]
    assert response.json()["data"]["unread_count"] == 1


def test_listing_expiry_notification_is_materialized_once(
    app: FastAPI,
    notification_client: TestClient,
    notification_repository: FakeNotificationRepository,
) -> None:
    seller_actor(app)

    first = notification_client.get("/api/v1/notifications")
    second = notification_client.get("/api/v1/notifications")

    assert first.status_code == 200
    assert first.json()["data"]["items"][0]["notification_type"] == "listing_expiring"
    assert len(second.json()["data"]["items"]) == 1
    assert notification_repository.materialize_calls == 2


def test_notification_read_is_idempotent(
    notification_client: TestClient,
    notification_repository: FakeNotificationRepository,
) -> None:
    notification_id = notification_repository.add_notification(BUYER_ID, "revision_decided")
    url = f"/api/v1/notifications/{notification_id}"

    first = notification_client.patch(url, json={"read": True})
    second = notification_client.patch(url, json={"read": True})

    assert first.status_code == 200
    assert first.json()["data"]["is_read"] is True
    assert first.json()["data"]["read_at"] == second.json()["data"]["read_at"]


def test_notification_cannot_be_unread_or_read_by_another_user(
    app: FastAPI,
    notification_client: TestClient,
    notification_repository: FakeNotificationRepository,
) -> None:
    notification_id = notification_repository.add_notification(BUYER_ID, "revision_decided")
    invalid_payload = notification_client.patch(
        f"/api/v1/notifications/{notification_id}", json={"read": False}
    )
    seller_actor(app)
    other_user = notification_client.patch(
        f"/api/v1/notifications/{notification_id}", json={"read": True}
    )

    assert invalid_payload.status_code == 400
    assert invalid_payload.json()["error"]["code"] == "VALIDATION_ERROR"
    assert other_user.status_code == 404
    assert other_user.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"


def test_buyer_reads_contract_audit_timeline(notification_client: TestClient) -> None:
    response = notification_client.get(f"/api/v1/contracts/{CONTRACT_ID}/audit-events")

    assert response.status_code == 200
    events = response.json()["data"]
    assert [event["event_type"] for event in events] == [
        "contract_requested",
        "revision_sent",
    ]
    assert events[0]["event_data"] == {"status": "seller_review"}
    assert "actor_user_id" not in events[0]


def test_seller_member_reads_contract_audit_timeline(
    app: FastAPI, notification_client: TestClient
) -> None:
    response = notification_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/audit-events",
        headers=seller_actor(app),
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_outsider_cannot_read_contract_audit_timeline(
    app: FastAPI, notification_client: TestClient
) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OUTSIDER_ID, "outsider@example.test"
    )

    response = notification_client.get(
        f"/api/v1/contracts/{CONTRACT_ID}/audit-events",
        headers={"X-Organization-Id": str(ORGANIZATION_ID)},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_unknown_contract_audit_timeline_returns_not_found(
    notification_client: TestClient,
) -> None:
    response = notification_client.get(f"/api/v1/contracts/{uuid4()}/audit-events")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTRACT_NOT_FOUND"


def test_notification_database_failure_is_safe(
    notification_client: TestClient,
    notification_repository: FakeNotificationRepository,
) -> None:
    notification_repository.unavailable = True

    response = notification_client.get("/api/v1/notifications")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "SQL" not in response.text


def test_notification_api_requires_authentication(
    app: FastAPI, notification_repository: FakeNotificationRepository
) -> None:
    app.dependency_overrides[get_notification_service] = lambda: NotificationService(
        notification_repository
    )
    app.dependency_overrides[get_auth_provider] = lambda: FakeAuthProvider({})
    with TestClient(app) as client:
        response = client.get("/api/v1/notifications")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
