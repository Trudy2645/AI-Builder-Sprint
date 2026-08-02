from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_revision_service
from app.core.auth import get_current_user
from app.domain.revisions.service import RevisionService
from app.integrations.auth import AuthenticatedUser
from app.repositories.revisions import (
    RevisionClauseRecord,
    RevisionContractRecord,
    RevisionIdempotencyConflictError,
    RevisionItemRecord,
    RevisionMutationRecord,
    RevisionPendingItemsError,
    RevisionReferenceError,
    RevisionRequestRecord,
    RevisionStateConflictError,
    RevisionVersionConflictError,
)

BUYER_ID = UUID("10000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("10000000-0000-0000-0000-000000000002")
OUTSIDER_ID = UUID("10000000-0000-0000-0000-000000000003")
ORGANIZATION_ID = UUID("20000000-0000-0000-0000-000000000001")
CONTRACT_ID = UUID("30000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("40000000-0000-0000-0000-000000000001")
CLAUSE_ID = UUID("50000000-0000-0000-0000-000000000001")
DOCUMENT_ID = UUID("60000000-0000-0000-0000-000000000001")
REVISION_ID = UUID("70000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 31, tzinfo=UTC)


class FakeRevisionRepository:
    def __init__(self) -> None:
        self.context = RevisionContractRecord(
            contract_id=CONTRACT_ID,
            buyer_user_id=BUYER_ID,
            seller_organization_id=ORGANIZATION_ID,
            contract_status="seller_review",
            current_version_id=VERSION_ID,
            version_no=1,
            version_title="부산 숙박 계약",
            listing_title="부산 숙박 계약",
            buyer_name="Buyer Snapshot",
        )
        self.clauses = [
            RevisionClauseRecord(
                id=CLAUSE_ID,
                clause_order=1,
                clause_key="cancellation",
                title="취소",
                body="취소할 수 없습니다.",
            )
        ]
        self.revisions: dict[UUID, RevisionRequestRecord] = {}
        self.memberships = {(SELLER_ID, ORGANIZATION_ID)}
        self.documents = {DOCUMENT_ID}
        self.idempotency: dict[tuple[UUID, str], tuple[str, RevisionMutationRecord]] = {}
        self.notifications: list[tuple[str, UUID]] = []
        self.unread_contract_ids: set[UUID] = set()
        self.version_snapshots: list[list[RevisionClauseRecord]] = []

    async def get_contract(self, contract_id: UUID):
        return self.context if contract_id == CONTRACT_ID else None

    async def get_revision(self, revision_id: UUID):
        return self.revisions.get(revision_id)

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        return (user_id, organization_id) in self.memberships

    async def list_seller_revisions(self, organization_id: UUID, statuses: set[str]):
        if organization_id != ORGANIZATION_ID:
            return []
        return [row for row in self.revisions.values() if row.status in statuses]

    async def list_unread_revision_contract_ids(
        self, user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]:
        return self.unread_contract_ids.intersection(contract_ids)

    async def create_revision(
        self,
        *,
        contract_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        message: str | None,
        items: list[dict],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        replay = self._replay(actor_user_id, idempotency_key, request_hash)
        if replay:
            return replay
        if base_version_no != self.context.version_no:
            raise RevisionVersionConflictError
        item_records = [self._item(item, order) for order, item in enumerate(items, start=1)]
        self.revisions[REVISION_ID] = RevisionRequestRecord(
            id=REVISION_ID,
            contract_id=contract_id,
            contract_version_id=VERSION_ID,
            current_version_id=self.context.current_version_id,
            base_version_no=base_version_no,
            buyer_user_id=BUYER_ID,
            seller_organization_id=ORGANIZATION_ID,
            contract_status=self.context.contract_status,
            requested_by_user_id=actor_user_id,
            status="draft",
            message=message,
            decision_message=None,
            response_message=None,
            created_at=NOW,
            updated_at=NOW,
            sent_at=None,
            decided_at=None,
            responded_at=None,
            version_title=self.context.version_title,
            listing_title=self.context.listing_title,
            buyer_name=self.context.buyer_name,
            items=item_records,
            clauses=list(self.clauses),
        )
        mutation = self._mutation("draft", self.context.contract_status)
        self.idempotency[(actor_user_id, idempotency_key)] = (request_hash, mutation)
        return mutation

    async def add_item(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        item: dict,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        replay = self._replay(actor_user_id, idempotency_key, request_hash)
        if replay:
            return replay
        record = self.revisions[revision_id]
        record.items.append(self._item(item, len(record.items) + 1))
        mutation = self._mutation("draft", record.contract_status)
        self.idempotency[(actor_user_id, idempotency_key)] = (request_hash, mutation)
        return mutation

    async def update_draft_item(
        self, revision_id: UUID, item_id: UUID, actor_user_id: UUID, item: dict
    ) -> None:
        record = self.revisions[revision_id]
        if record.status != "draft":
            raise RevisionStateConflictError
        for index, existing in enumerate(record.items):
            if existing.id == item_id:
                record.items[index] = self._item(item, existing.item_order, item_id)
                return
        raise RevisionReferenceError

    async def delete_draft_item(
        self, revision_id: UUID, item_id: UUID, actor_user_id: UUID
    ) -> None:
        record = self.revisions[revision_id]
        before = len(record.items)
        record.items[:] = [item for item in record.items if item.id != item_id]
        if len(record.items) == before:
            raise RevisionReferenceError

    async def send_revision(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        replay = self._replay(actor_user_id, idempotency_key, request_hash)
        if replay:
            return replay
        record = self.revisions[revision_id]
        if record.current_version_id != record.contract_version_id:
            raise RevisionVersionConflictError
        self.revisions[revision_id] = replace(
            record, status="sent", contract_status="revision_requested", sent_at=NOW
        )
        self.context = replace(self.context, contract_status="revision_requested")
        self.notifications.append(("revision_requested", SELLER_ID))
        mutation = self._mutation("sent", "revision_requested")
        self.idempotency[(actor_user_id, idempotency_key)] = (request_hash, mutation)
        return mutation

    async def decide_item(
        self,
        revision_id: UUID,
        item_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        decision: str,
        reason: str | None,
        counter_text: str | None,
    ) -> None:
        record = self.revisions[revision_id]
        if record.status != "sent":
            raise RevisionStateConflictError
        for index, item in enumerate(record.items):
            if item.id == item_id:
                record.items[index] = replace(
                    item,
                    decision=decision,
                    decision_reason=reason,
                    counter_text=counter_text,
                    decided_by_user_id=actor_user_id,
                    decided_at=NOW,
                )
                return
        raise RevisionReferenceError

    async def finalize_decision(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        seller_message: str | None,
        version_clauses: list[RevisionClauseRecord],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        replay = self._replay(actor_user_id, idempotency_key, request_hash)
        if replay:
            return replay
        record = self.revisions[revision_id]
        decisions = {item.decision for item in record.items}
        if "pending" in decisions:
            raise RevisionPendingItemsError
        if "countered" in decisions:
            revision_status, contract_status, version_no = "countered", "revision_requested", None
        elif decisions == {"accepted"}:
            revision_status, contract_status, version_no = "accepted", "signing", 2
            self.version_snapshots.append(version_clauses)
            self.context = replace(
                self.context,
                contract_status="signing",
                current_version_id=uuid4(),
                version_no=2,
            )
        elif decisions == {"rejected"}:
            revision_status, contract_status, version_no = "rejected", "seller_review", None
            self.context = replace(self.context, contract_status="seller_review")
        else:
            revision_status, contract_status, version_no = (
                "partially_accepted",
                "revision_requested",
                None,
            )
        self.revisions[revision_id] = replace(
            record,
            status=revision_status,
            contract_status=contract_status,
            decision_message=seller_message,
            decided_at=NOW,
        )
        self.notifications.append(("revision_decided", BUYER_ID))
        mutation = self._mutation(revision_status, contract_status, version_no)
        self.idempotency[(actor_user_id, idempotency_key)] = (request_hash, mutation)
        return mutation

    async def reject_all(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        seller_message: str | None,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        record = self.revisions[revision_id]
        record.items[:] = [
            replace(
                item,
                decision="rejected",
                decision_reason=item.decision_reason or seller_message,
                decided_by_user_id=actor_user_id,
                decided_at=NOW,
            )
            for item in record.items
        ]
        self.revisions[revision_id] = replace(
            record,
            status="rejected",
            contract_status="seller_review",
            decision_message=seller_message,
            decided_at=NOW,
        )
        self.notifications.append(("revision_decided", BUYER_ID))
        return self._mutation("rejected", "seller_review")

    async def respond(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        accepted: bool,
        message: str | None,
        version_clauses: list[RevisionClauseRecord],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        record = self.revisions[revision_id]
        revision_status = "accepted" if accepted else "rejected"
        contract_status = "signing" if accepted else "revision_requested"
        version_no = 2 if accepted else None
        if accepted:
            self.version_snapshots.append(version_clauses)
        self.revisions[revision_id] = replace(
            record,
            status=revision_status,
            contract_status=contract_status,
            response_message=message,
            responded_at=NOW,
        )
        self.notifications.append(("seller_response", SELLER_ID))
        return self._mutation(revision_status, contract_status, version_no)

    def _item(self, data: dict, order: int, item_id: UUID | None = None) -> RevisionItemRecord:
        clause_id = (
            UUID(data["clause_id"]) if isinstance(data["clause_id"], str) else data["clause_id"]
        )
        document_ids = [
            UUID(value) if isinstance(value, str) else value for value in data["document_ids"]
        ]
        if clause_id is not None and clause_id != CLAUSE_ID:
            raise RevisionReferenceError
        if not set(document_ids).issubset(self.documents):
            raise RevisionReferenceError
        return RevisionItemRecord(
            id=item_id or uuid4(),
            item_order=order,
            request_type=data["request_type"],
            clause_id=clause_id,
            reason=data["reason"],
            requested_text=data["requested_text"],
            document_ids=document_ids,
            decision="pending",
            decision_reason=None,
            counter_text=None,
            decided_by_user_id=None,
            decided_at=None,
        )

    def _replay(self, actor_id: UUID, key: str, request_hash: str):
        existing = self.idempotency.get((actor_id, key))
        if existing is None:
            return None
        stored_hash, mutation = existing
        if stored_hash != request_hash:
            raise RevisionIdempotencyConflictError
        return replace(mutation, replayed=True)

    @staticmethod
    def _mutation(
        revision_status: str, contract_status: str, version_no: int | None = None
    ) -> RevisionMutationRecord:
        return RevisionMutationRecord(
            revision_request_id=REVISION_ID,
            contract_id=CONTRACT_ID,
            revision_status=revision_status,
            contract_status=contract_status,
            version_no=version_no,
        )


@pytest.fixture
def revision_repository() -> FakeRevisionRepository:
    return FakeRevisionRepository()


@pytest.fixture
def revision_client(app: FastAPI, revision_repository: FakeRevisionRepository) -> TestClient:
    app.dependency_overrides[get_revision_service] = lambda: RevisionService(revision_repository)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    return TestClient(app)


def item_payload(**changes):
    payload = {
        "request_type": "modify",
        "clause_id": str(CLAUSE_ID),
        "reason": "무료 취소 기한이 필요합니다.",
        "requested_text": "이용 7일 전까지 무료 취소할 수 있습니다.",
        "document_ids": [str(DOCUMENT_ID)],
    }
    payload.update(changes)
    return payload


def create_draft(client: TestClient, *, items: list[dict] | None = None):
    return client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/revision-requests",
        headers={"Idempotency-Key": "create-1"},
        json={"base_version_no": 1, "message": "수정 요청", "items": items or [item_payload()]},
    )


def as_seller(app: FastAPI) -> dict[str, str]:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=SELLER_ID, email="seller@example.test"
    )
    return {"X-Organization-Id": str(ORGANIZATION_ID)}


def test_create_revision_is_draft_and_idempotent(
    revision_client: TestClient, revision_repository: FakeRevisionRepository
) -> None:
    first = create_draft(revision_client)
    second = create_draft(revision_client)

    assert first.status_code == 200
    assert first.json()["data"]["status"] == "draft"
    assert second.json()["data"]["replayed"] is True
    assert len(revision_repository.revisions) == 1


def test_create_rejects_version_conflict(revision_client: TestClient) -> None:
    response = revision_client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/revision-requests",
        headers={"Idempotency-Key": "wrong-version"},
        json={"base_version_no": 2, "items": [item_payload()]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_create_rejects_idempotency_key_reuse_with_different_payload(
    revision_client: TestClient,
) -> None:
    assert create_draft(revision_client).status_code == 200

    response = revision_client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/revision-requests",
        headers={"Idempotency-Key": "create-1"},
        json={"base_version_no": 1, "message": "다른 요청", "items": [item_payload()]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_create_rejects_document_from_another_contract(revision_client: TestClient) -> None:
    response = create_draft(
        revision_client,
        items=[item_payload(document_ids=[str(uuid4())])],
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


@pytest.mark.parametrize(
    "payload",
    [
        item_payload(request_type="modify", clause_id=None),
        item_payload(request_type="delete", requested_text="not-null"),
        item_payload(request_type="add", clause_id=str(CLAUSE_ID)),
    ],
)
def test_item_type_shape_is_validated(revision_client: TestClient, payload: dict) -> None:
    response = create_draft(revision_client, items=[payload])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_draft_items_can_be_added_updated_and_deleted(revision_client: TestClient) -> None:
    assert create_draft(revision_client).status_code == 200
    added = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/items",
        headers={"Idempotency-Key": "add-item-1"},
        json=item_payload(
            request_type="add",
            clause_id=None,
            requested_text="새로운 인원 변경 조항",
            document_ids=[],
        ),
    )
    assert added.status_code == 200

    detail = revision_client.get(f"/api/v1/revision-requests/{REVISION_ID}").json()["data"]
    item_id = detail["items"][1]["id"]
    updated = revision_client.patch(
        f"/api/v1/revision-requests/{REVISION_ID}/items/{item_id}",
        json=item_payload(
            request_type="add",
            clause_id=None,
            reason="수정된 이유",
            requested_text="수정된 새 조항",
            document_ids=[],
        ),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["items"][1]["reason"] == "수정된 이유"

    deleted = revision_client.delete(f"/api/v1/revision-requests/{REVISION_ID}/items/{item_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"deleted": True}


def test_send_requires_buyer_and_creates_seller_notification(
    app: FastAPI,
    revision_client: TestClient,
    revision_repository: FakeRevisionRepository,
) -> None:
    create_draft(revision_client)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OUTSIDER_ID, email="outsider@example.test"
    )
    denied = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-denied"},
    )
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    sent = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-1"},
    )
    assert sent.status_code == 200
    assert sent.json()["data"]["status"] == "sent"
    assert revision_repository.notifications[-1] == ("revision_requested", SELLER_ID)


def test_non_party_cannot_read_revision(app: FastAPI, revision_client: TestClient) -> None:
    create_draft(revision_client)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=OUTSIDER_ID, email="outsider@example.test"
    )

    response = revision_client.get(f"/api/v1/revision-requests/{REVISION_ID}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_seller_cannot_read_buyer_draft(app: FastAPI, revision_client: TestClient) -> None:
    create_draft(revision_client)

    response = revision_client.get(
        f"/api/v1/revision-requests/{REVISION_ID}", headers=as_seller(app)
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRACT_ACCESS_DENIED"


def test_seller_list_is_organization_scoped_and_returns_unread(
    app: FastAPI,
    revision_client: TestClient,
    revision_repository: FakeRevisionRepository,
) -> None:
    create_draft(revision_client)
    revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-1"},
    )
    revision_repository.unread_contract_ids = {CONTRACT_ID}

    response = revision_client.get(
        "/api/v1/seller/revision-requests",
        headers=as_seller(app),
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["buyer_name"] == "Buyer Snapshot"
    assert response.json()["data"][0]["has_unread"] is True


def test_seller_cannot_finalize_until_every_item_is_decided(
    app: FastAPI, revision_client: TestClient
) -> None:
    create_draft(revision_client)
    revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-1"},
    )
    headers = {**as_seller(app), "Idempotency-Key": "decide-pending"}
    response = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/decide",
        headers=headers,
        json={"seller_message": "검토했습니다."},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVISION_ITEMS_PENDING"


def test_all_accepted_creates_immutable_new_version_and_notifies_buyer(
    app: FastAPI,
    revision_client: TestClient,
    revision_repository: FakeRevisionRepository,
) -> None:
    create_draft(revision_client)
    revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-1"},
    )
    item_id = revision_repository.revisions[REVISION_ID].items[0].id
    seller_headers = as_seller(app)
    decided_item = revision_client.patch(
        f"/api/v1/revision-requests/{REVISION_ID}/items/{item_id}",
        headers=seller_headers,
        json={"decision": "accepted", "seller_reason": "수락합니다."},
    )
    assert decided_item.status_code == 200

    finalized = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/decide",
        headers={**seller_headers, "Idempotency-Key": "decide-1"},
        json={"seller_message": "전체 수락"},
    )
    assert finalized.status_code == 200
    assert finalized.json()["data"] | {"replayed": False} == finalized.json()["data"]
    assert finalized.json()["data"]["contract_status"] == "signing"
    assert finalized.json()["data"]["version_no"] == 2
    assert revision_repository.clauses[0].body == "취소할 수 없습니다."
    assert revision_repository.version_snapshots[0][0].body.startswith("이용 7일")
    assert revision_repository.notifications[-1] == ("revision_decided", BUYER_ID)


def test_counter_preview_requires_buyer_response_and_acceptance_creates_version(
    app: FastAPI,
    revision_client: TestClient,
    revision_repository: FakeRevisionRepository,
) -> None:
    create_draft(revision_client)
    revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-1"},
    )
    item_id = revision_repository.revisions[REVISION_ID].items[0].id
    seller_headers = as_seller(app)
    revision_client.patch(
        f"/api/v1/revision-requests/{REVISION_ID}/items/{item_id}",
        headers=seller_headers,
        json={
            "decision": "countered",
            "seller_reason": "7일은 어렵습니다.",
            "counter_text": "이용 14일 전까지 무료 취소할 수 있습니다.",
        },
    )
    finalized = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/decide",
        headers={**seller_headers, "Idempotency-Key": "decide-counter"},
        json={"seller_message": "대안을 확인해주세요."},
    )
    assert finalized.json()["data"]["status"] == "countered"
    assert not revision_repository.version_snapshots

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    detail = revision_client.get(f"/api/v1/revision-requests/{REVISION_ID}")
    assert detail.json()["data"]["decision_preview"]["requires_buyer_response"] is True
    assert detail.json()["data"]["decision_preview"]["resulting_clauses"][0]["body"].startswith(
        "이용 14일"
    )

    response = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/respond",
        headers={"Idempotency-Key": "respond-1"},
        json={"decision": "accepted", "message": "대안에 동의합니다."},
    )
    assert response.status_code == 200
    assert response.json()["data"]["contract_status"] == "signing"
    assert revision_repository.version_snapshots[0][0].body.startswith("이용 14일")


def test_reject_all_rejects_items_without_creating_version(
    app: FastAPI,
    revision_client: TestClient,
    revision_repository: FakeRevisionRepository,
) -> None:
    create_draft(revision_client)
    revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/send",
        headers={"Idempotency-Key": "send-1"},
    )
    response = revision_client.post(
        f"/api/v1/revision-requests/{REVISION_ID}/reject-all",
        headers={**as_seller(app), "Idempotency-Key": "reject-all-1"},
        json={"seller_message": "기존 조건을 유지합니다."},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"
    assert response.json()["data"]["contract_status"] == "seller_review"
    assert revision_repository.revisions[REVISION_ID].items[0].decision == "rejected"
    assert not revision_repository.version_snapshots
