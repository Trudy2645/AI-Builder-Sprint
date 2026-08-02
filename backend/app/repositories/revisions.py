from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class RevisionContractRecord:
    contract_id: UUID
    buyer_user_id: UUID
    seller_organization_id: UUID
    contract_status: str
    current_version_id: UUID
    version_no: int
    version_title: str
    listing_title: str
    buyer_name: str


@dataclass(frozen=True, slots=True)
class RevisionClauseRecord:
    id: UUID
    clause_order: int
    clause_key: str | None
    title: str
    body: str
    source_listing_clause_id: UUID | None = None
    source_page: int | None = None
    source_bbox: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RevisionItemRecord:
    id: UUID
    item_order: int
    request_type: str
    clause_id: UUID | None
    reason: str
    requested_text: str | None
    document_ids: list[UUID]
    decision: str
    decision_reason: str | None
    counter_text: str | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None


@dataclass(frozen=True, slots=True)
class RevisionRequestRecord:
    id: UUID
    contract_id: UUID
    contract_version_id: UUID
    current_version_id: UUID
    base_version_no: int
    buyer_user_id: UUID
    seller_organization_id: UUID
    contract_status: str
    requested_by_user_id: UUID
    status: str
    message: str | None
    decision_message: str | None
    response_message: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    decided_at: datetime | None
    responded_at: datetime | None
    version_title: str
    listing_title: str
    buyer_name: str
    items: list[RevisionItemRecord]
    clauses: list[RevisionClauseRecord]


@dataclass(frozen=True, slots=True)
class RevisionMutationRecord:
    revision_request_id: UUID
    contract_id: UUID
    revision_status: str
    contract_status: str
    version_no: int | None = None
    replayed: bool = False


class RevisionRepositoryError(Exception):
    pass


class RevisionNotFoundError(Exception):
    pass


class RevisionStateConflictError(Exception):
    pass


class RevisionVersionConflictError(Exception):
    pass


class RevisionReferenceError(Exception):
    pass


class RevisionPendingItemsError(Exception):
    pass


class RevisionIdempotencyConflictError(Exception):
    pass


class RevisionRepository(Protocol):
    async def get_contract(self, contract_id: UUID) -> RevisionContractRecord | None: ...

    async def get_revision(self, revision_id: UUID) -> RevisionRequestRecord | None: ...

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...

    async def list_seller_revisions(
        self, organization_id: UUID, statuses: set[str]
    ) -> list[RevisionRequestRecord]: ...

    async def list_buyer_revisions(
        self, user_id: UUID, statuses: set[str]
    ) -> list[RevisionRequestRecord]: ...

    async def list_unread_revision_contract_ids(
        self, user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]: ...

    async def create_revision(
        self,
        *,
        contract_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        message: str | None,
        items: list[dict[str, Any]],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord: ...

    async def add_item(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        item: dict[str, Any],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord: ...

    async def update_draft_item(
        self, revision_id: UUID, item_id: UUID, actor_user_id: UUID, item: dict[str, Any]
    ) -> None: ...

    async def delete_draft_item(
        self, revision_id: UUID, item_id: UUID, actor_user_id: UUID
    ) -> None: ...

    async def send_revision(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord: ...

    async def decide_item(
        self,
        revision_id: UUID,
        item_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        decision: str,
        reason: str | None,
        counter_text: str | None,
    ) -> None: ...

    async def finalize_decision(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        seller_message: str | None,
        version_clauses: list[RevisionClauseRecord],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord: ...

    async def reject_all(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        seller_message: str | None,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord: ...

    async def respond(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        accepted: bool,
        message: str | None,
        version_clauses: list[RevisionClauseRecord],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord: ...


class SqlAlchemyRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_contract(self, contract_id: UUID) -> RevisionContractRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select c.id as contract_id, c.buyer_user_id, c.seller_organization_id,
                           c.status::text as contract_status, c.current_version_id,
                           cv.version_no, cv.title as version_title,
                           coalesce(l.display_title, l.title, cv.title) as listing_title,
                           buyer.name_snapshot as buyer_name
                    from public.contracts c
                    join public.contract_versions cv on cv.id = c.current_version_id
                    left join public.listings l on l.id = c.listing_id
                    join public.contract_parties buyer
                      on buyer.contract_id = c.id and buyer.party_role = 'buyer'
                    where c.id = :contract_id
                    """
                ),
                {"contract_id": contract_id},
            )
            row = result.mappings().one_or_none()
            return RevisionContractRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def get_revision(self, revision_id: UUID) -> RevisionRequestRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select rr.id, rr.contract_id, rr.contract_version_id,
                           cv.version_no as base_version_no, c.buyer_user_id,
                           c.seller_organization_id, c.status::text as contract_status,
                           c.current_version_id,
                           rr.requested_by_user_id, rr.status::text as status, rr.message,
                           rr.decision_message, rr.response_message, rr.created_at,
                           rr.updated_at, rr.sent_at, rr.decided_at, rr.responded_at,
                           cv.title as version_title,
                           coalesce(l.display_title, l.title, cv.title) as listing_title,
                           buyer.name_snapshot as buyer_name
                    from public.revision_requests rr
                    join public.contracts c on c.id = rr.contract_id
                    join public.contract_versions cv on cv.id = rr.contract_version_id
                    left join public.listings l on l.id = c.listing_id
                    join public.contract_parties buyer
                      on buyer.contract_id = c.id and buyer.party_role = 'buyer'
                    where rr.id = :revision_id
                    """
                ),
                {"revision_id": revision_id},
            )
            row = result.mappings().one_or_none()
            if row is None:
                return None
            return RevisionRequestRecord(
                **row,
                items=await self._list_items(revision_id),
                clauses=await self._list_clauses(row["contract_version_id"]),
            )
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        try:
            result = await self._session.execute(
                text(
                    """
                    select exists (
                        select 1 from public.organization_members
                        where user_id = :user_id and organization_id = :organization_id
                    )
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            return bool(result.scalar_one())
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def list_seller_revisions(
        self, organization_id: UUID, statuses: set[str]
    ) -> list[RevisionRequestRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select rr.id
                    from public.revision_requests rr
                    join public.contracts c on c.id = rr.contract_id
                    where c.seller_organization_id = :organization_id
                      and rr.status::text = any(cast(:statuses as text[]))
                    order by coalesce(rr.sent_at, rr.updated_at) desc, rr.id desc
                    """
                ),
                {"organization_id": organization_id, "statuses": sorted(statuses)},
            )
            records = []
            for revision_id in result.scalars().all():
                record = await self.get_revision(revision_id)
                if record is not None:
                    records.append(record)
            return records
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def list_buyer_revisions(
        self, user_id: UUID, statuses: set[str]
    ) -> list[RevisionRequestRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select rr.id
                    from public.revision_requests rr
                    join public.contracts c on c.id = rr.contract_id
                    where c.buyer_user_id = :user_id
                      and rr.status::text = any(cast(:statuses as text[]))
                    order by coalesce(rr.sent_at, rr.updated_at) desc, rr.id desc
                    """
                ),
                {"user_id": user_id, "statuses": sorted(statuses)},
            )
            records = []
            for revision_id in result.scalars().all():
                record = await self.get_revision(revision_id)
                if record is not None:
                    records.append(record)
            return records
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def mark_buyer_revision_read(self, user_id: UUID, revision_id: UUID) -> None:
        try:
            await self._session.execute(
                text(
                    """
                    update public.notifications n
                    set read_at = coalesce(read_at, now())
                    from public.revision_requests rr
                    where rr.id = :revision_id
                      and n.user_id = :user_id
                      and n.resource_type = 'contract'
                      and n.resource_id = rr.contract_id
                      and n.notification_type in ('revision_decided', 'seller_response')
                    """
                ),
                {"user_id": user_id, "revision_id": revision_id},
            )
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def list_unread_revision_contract_ids(
        self, user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]:
        if not contract_ids:
            return set()
        try:
            result = await self._session.execute(
                text(
                    """
                    select distinct resource_id
                    from public.notifications
                    where user_id = :user_id and resource_type = 'contract'
                      and resource_id = any(cast(:contract_ids as uuid[]))
                      and notification_type in ('revision_requested', 'seller_response')
                      and read_at is null
                    """
                ),
                {"user_id": user_id, "contract_ids": contract_ids},
            )
            return set(result.scalars().all())
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def create_revision(
        self,
        *,
        contract_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        message: str | None,
        items: list[dict[str, Any]],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        operation = f"create_revision:{contract_id}"
        try:
            await self._reset_transaction()
            async with self._session.begin():
                replay = await self._claim_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._mutation_from_body(replay, replayed=True)
                context = await self._lock_contract(contract_id)
                if context is None:
                    raise RevisionNotFoundError
                if context.buyer_user_id != actor_user_id:
                    raise RevisionReferenceError
                if context.version_no != base_version_no:
                    raise RevisionVersionConflictError
                if context.contract_status not in {"seller_review", "revision_requested"}:
                    raise RevisionStateConflictError
                revision_id = uuid4()
                await self._session.execute(
                    text(
                        """
                        insert into public.revision_requests (
                            id, contract_id, contract_version_id, requested_by_role,
                            requested_by_user_id, message
                        ) values (
                            :id, :contract_id, :version_id, 'buyer', :actor_user_id, :message
                        )
                        """
                    ),
                    {
                        "id": revision_id,
                        "contract_id": contract_id,
                        "version_id": context.current_version_id,
                        "actor_user_id": actor_user_id,
                        "message": message,
                    },
                )
                for order, item in enumerate(items, start=1):
                    await self._insert_item(revision_id, contract_id, order, item)
                mutation = RevisionMutationRecord(
                    revision_request_id=revision_id,
                    contract_id=contract_id,
                    revision_status="draft",
                    contract_status=context.contract_status,
                )
                await self._complete_idempotency(
                    actor_user_id, operation, idempotency_key, mutation
                )
                return mutation
        except (
            RevisionIdempotencyConflictError,
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
            RevisionVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def add_item(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        item: dict[str, Any],
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        operation = f"add_revision_item:{revision_id}"
        try:
            await self._reset_transaction()
            async with self._session.begin():
                replay = await self._claim_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._mutation_from_body(replay, replayed=True)
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["requested_by_user_id"] != actor_user_id:
                    raise RevisionReferenceError
                if row["status"] != "draft":
                    raise RevisionStateConflictError
                order_result = await self._session.execute(
                    text(
                        """
                        select coalesce(max(item_order), 0) + 1
                        from public.revision_request_items
                        where revision_request_id = :revision_id
                        """
                    ),
                    {"revision_id": revision_id},
                )
                await self._insert_item(
                    revision_id, row["contract_id"], order_result.scalar_one(), item
                )
                mutation = RevisionMutationRecord(
                    revision_request_id=revision_id,
                    contract_id=row["contract_id"],
                    revision_status="draft",
                    contract_status=row["contract_status"],
                )
                await self._complete_idempotency(
                    actor_user_id, operation, idempotency_key, mutation
                )
                return mutation
        except (
            RevisionIdempotencyConflictError,
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def update_draft_item(
        self, revision_id: UUID, item_id: UUID, actor_user_id: UUID, item: dict[str, Any]
    ) -> None:
        try:
            await self._reset_transaction()
            async with self._session.begin():
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["requested_by_user_id"] != actor_user_id:
                    raise RevisionReferenceError
                if row["status"] != "draft":
                    raise RevisionStateConflictError
                clause_id = await self._validate_item_references(
                    revision_id, row["contract_id"], item["clause_id"], item["document_ids"]
                )
                updated = await self._session.execute(
                    text(
                        """
                        update public.revision_request_items
                        set request_type = :request_type, clause_id = :clause_id,
                            reason = :reason, requested_text = :requested_text,
                            decision = 'pending', decision_reason = null,
                            counter_text = null, decided_by_user_id = null, decided_at = null
                        where id = :item_id and revision_request_id = :revision_id
                        returning id
                        """
                    ),
                    {
                        "item_id": item_id,
                        "revision_id": revision_id,
                        "clause_id": clause_id,
                        **{key: item[key] for key in ("request_type", "reason", "requested_text")},
                    },
                )
                if updated.scalar_one_or_none() is None:
                    raise RevisionNotFoundError
                await self._replace_documents(item_id, row["contract_id"], item["document_ids"])
        except (
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def delete_draft_item(
        self, revision_id: UUID, item_id: UUID, actor_user_id: UUID
    ) -> None:
        try:
            await self._reset_transaction()
            async with self._session.begin():
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["requested_by_user_id"] != actor_user_id:
                    raise RevisionReferenceError
                if row["status"] != "draft":
                    raise RevisionStateConflictError
                deleted = await self._session.execute(
                    text(
                        """
                        delete from public.revision_request_items
                        where id = :item_id and revision_request_id = :revision_id
                        returning id
                        """
                    ),
                    {"item_id": item_id, "revision_id": revision_id},
                )
                if deleted.scalar_one_or_none() is None:
                    raise RevisionNotFoundError
        except (
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def send_revision(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        operation = f"send_revision:{revision_id}"
        try:
            await self._reset_transaction()
            async with self._session.begin():
                replay = await self._claim_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._mutation_from_body(replay, replayed=True)
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["requested_by_user_id"] != actor_user_id:
                    raise RevisionReferenceError
                if row["status"] != "draft":
                    raise RevisionStateConflictError
                if row["current_version_id"] != row["contract_version_id"]:
                    raise RevisionVersionConflictError
                count = await self._session.execute(
                    text(
                        "select count(*) from public.revision_request_items "
                        "where revision_request_id = :revision_id"
                    ),
                    {"revision_id": revision_id},
                )
                if count.scalar_one() == 0:
                    raise RevisionStateConflictError
                await self._session.execute(
                    text(
                        """
                        update public.revision_requests
                        set status = 'sent', sent_at = now()
                        where id = :revision_id
                        """
                    ),
                    {"revision_id": revision_id},
                )
                await self._session.execute(
                    text(
                        """
                        update public.contracts set status = 'revision_requested'
                        where id = :contract_id
                        """
                    ),
                    {"contract_id": row["contract_id"]},
                )
                await self._notify_seller(
                    row["seller_organization_id"], row["contract_id"], "revision_requested"
                )
                await self._audit(
                    row["contract_id"], actor_user_id, "buyer", "revision_requested", revision_id
                )
                mutation = RevisionMutationRecord(
                    revision_request_id=revision_id,
                    contract_id=row["contract_id"],
                    revision_status="sent",
                    contract_status="revision_requested",
                )
                await self._complete_idempotency(
                    actor_user_id, operation, idempotency_key, mutation
                )
                return mutation
        except (
            RevisionIdempotencyConflictError,
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
            RevisionVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

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
        try:
            await self._reset_transaction()
            async with self._session.begin():
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["seller_organization_id"] != organization_id:
                    raise RevisionReferenceError
                if row["status"] != "sent":
                    raise RevisionStateConflictError
                updated = await self._session.execute(
                    text(
                        """
                        update public.revision_request_items
                        set decision = cast(:decision as public.revision_item_decision),
                            decision_reason = :reason, counter_text = :counter_text,
                            decided_by_user_id = :actor_user_id, decided_at = now()
                        where id = :item_id and revision_request_id = :revision_id
                        returning id
                        """
                    ),
                    {
                        "decision": decision,
                        "reason": reason,
                        "counter_text": counter_text,
                        "actor_user_id": actor_user_id,
                        "item_id": item_id,
                        "revision_id": revision_id,
                    },
                )
                if updated.scalar_one_or_none() is None:
                    raise RevisionNotFoundError
        except (
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

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
        operation = f"decide_revision:{revision_id}"
        try:
            await self._reset_transaction()
            async with self._session.begin():
                replay = await self._claim_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._mutation_from_body(replay, replayed=True)
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["seller_organization_id"] != organization_id:
                    raise RevisionReferenceError
                if row["status"] != "sent":
                    raise RevisionStateConflictError
                if row["current_version_id"] != row["contract_version_id"]:
                    raise RevisionVersionConflictError
                decisions = await self._decision_values(revision_id)
                if not decisions or "pending" in decisions:
                    raise RevisionPendingItemsError
                if "countered" in decisions:
                    revision_status = "countered"
                elif decisions == {"accepted"}:
                    revision_status = "accepted"
                elif decisions == {"rejected"}:
                    revision_status = "rejected"
                else:
                    revision_status = "partially_accepted"
                contract_status = "revision_requested"
                version_no = None
                if revision_status == "accepted":
                    version_no = await self._create_version(row, actor_user_id, version_clauses)
                    contract_status = "signing"
                elif revision_status == "rejected":
                    contract_status = "seller_review"
                    await self._session.execute(
                        text("update public.contracts set status = 'seller_review' where id = :id"),
                        {"id": row["contract_id"]},
                    )
                await self._session.execute(
                    text(
                        """
                        update public.revision_requests
                        set status = cast(:status as public.revision_status),
                            decision_message = :message, decided_at = now()
                        where id = :revision_id
                        """
                    ),
                    {
                        "status": revision_status,
                        "message": seller_message,
                        "revision_id": revision_id,
                    },
                )
                await self._notify_buyer(row["buyer_user_id"], row["contract_id"])
                await self._audit(
                    row["contract_id"], actor_user_id, "seller", "revision_decided", revision_id
                )
                mutation = RevisionMutationRecord(
                    revision_request_id=revision_id,
                    contract_id=row["contract_id"],
                    revision_status=revision_status,
                    contract_status=contract_status,
                    version_no=version_no,
                )
                await self._complete_idempotency(
                    actor_user_id, operation, idempotency_key, mutation
                )
                return mutation
        except (
            RevisionIdempotencyConflictError,
            RevisionNotFoundError,
            RevisionPendingItemsError,
            RevisionReferenceError,
            RevisionStateConflictError,
            RevisionVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def reject_all(
        self,
        revision_id: UUID,
        actor_user_id: UUID,
        organization_id: UUID,
        seller_message: str | None,
        idempotency_key: str,
        request_hash: str,
    ) -> RevisionMutationRecord:
        operation = f"reject_all_revision:{revision_id}"
        try:
            await self._reset_transaction()
            async with self._session.begin():
                replay = await self._claim_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._mutation_from_body(replay, replayed=True)
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["seller_organization_id"] != organization_id:
                    raise RevisionReferenceError
                if row["status"] != "sent":
                    raise RevisionStateConflictError
                if row["current_version_id"] != row["contract_version_id"]:
                    raise RevisionVersionConflictError
                await self._session.execute(
                    text(
                        """
                        update public.revision_request_items
                        set decision = 'rejected', decision_reason = coalesce(
                                decision_reason, :message
                            ), counter_text = null, decided_by_user_id = :actor_user_id,
                            decided_at = coalesce(decided_at, now())
                        where revision_request_id = :revision_id
                        """
                    ),
                    {
                        "revision_id": revision_id,
                        "actor_user_id": actor_user_id,
                        "message": seller_message,
                    },
                )
                await self._session.execute(
                    text(
                        """
                        update public.revision_requests
                        set status = 'rejected', decision_message = :message, decided_at = now()
                        where id = :revision_id
                        """
                    ),
                    {"revision_id": revision_id, "message": seller_message},
                )
                await self._session.execute(
                    text("update public.contracts set status = 'seller_review' where id = :id"),
                    {"id": row["contract_id"]},
                )
                await self._notify_buyer(row["buyer_user_id"], row["contract_id"])
                await self._audit(
                    row["contract_id"], actor_user_id, "seller", "revision_rejected", revision_id
                )
                mutation = RevisionMutationRecord(
                    revision_request_id=revision_id,
                    contract_id=row["contract_id"],
                    revision_status="rejected",
                    contract_status="seller_review",
                )
                await self._complete_idempotency(
                    actor_user_id, operation, idempotency_key, mutation
                )
                return mutation
        except (
            RevisionIdempotencyConflictError,
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
            RevisionVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

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
        operation = f"respond_revision:{revision_id}"
        try:
            await self._reset_transaction()
            async with self._session.begin():
                replay = await self._claim_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._mutation_from_body(replay, replayed=True)
                row = await self._lock_revision(revision_id)
                if row is None:
                    raise RevisionNotFoundError
                if row["buyer_user_id"] != actor_user_id:
                    raise RevisionReferenceError
                if row["status"] not in {"partially_accepted", "countered"}:
                    raise RevisionStateConflictError
                if row["current_version_id"] != row["contract_version_id"]:
                    raise RevisionVersionConflictError
                revision_status = "accepted" if accepted else "rejected"
                contract_status = "revision_requested"
                version_no = None
                if accepted:
                    version_no = await self._create_version(row, actor_user_id, version_clauses)
                    contract_status = "signing"
                await self._session.execute(
                    text(
                        """
                        update public.revision_requests
                        set status = cast(:status as public.revision_status),
                            response_message = :message, responded_at = now()
                        where id = :revision_id
                        """
                    ),
                    {"status": revision_status, "message": message, "revision_id": revision_id},
                )
                await self._notify_seller(
                    row["seller_organization_id"], row["contract_id"], "seller_response"
                )
                await self._audit(
                    row["contract_id"], actor_user_id, "buyer", "revision_responded", revision_id
                )
                mutation = RevisionMutationRecord(
                    revision_request_id=revision_id,
                    contract_id=row["contract_id"],
                    revision_status=revision_status,
                    contract_status=contract_status,
                    version_no=version_no,
                )
                await self._complete_idempotency(
                    actor_user_id, operation, idempotency_key, mutation
                )
                return mutation
        except (
            RevisionIdempotencyConflictError,
            RevisionNotFoundError,
            RevisionReferenceError,
            RevisionStateConflictError,
            RevisionVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise RevisionRepositoryError from exc

    async def _list_items(self, revision_id: UUID) -> list[RevisionItemRecord]:
        result = await self._session.execute(
            text(
                """
                select ri.id, ri.item_order, ri.request_type, ri.clause_id, ri.reason,
                       ri.requested_text, ri.decision::text as decision,
                       ri.decision_reason, ri.counter_text, ri.decided_by_user_id,
                       ri.decided_at,
                       coalesce(array_agg(rid.document_id order by rid.document_id)
                           filter (where rid.document_id is not null), '{}') as document_ids
                from public.revision_request_items ri
                left join public.revision_request_item_documents rid
                  on rid.revision_request_item_id = ri.id
                where ri.revision_request_id = :revision_id
                group by ri.id
                order by ri.item_order
                """
            ),
            {"revision_id": revision_id},
        )
        return [RevisionItemRecord(**row) for row in result.mappings().all()]

    async def _list_clauses(self, version_id: UUID) -> list[RevisionClauseRecord]:
        result = await self._session.execute(
            text(
                """
                select id, clause_order, clause_key, title, body, source_listing_clause_id,
                       source_page, source_bbox
                from public.contract_clauses
                where contract_version_id = :version_id
                order by clause_order
                """
            ),
            {"version_id": version_id},
        )
        return [RevisionClauseRecord(**row) for row in result.mappings().all()]

    async def _lock_contract(self, contract_id: UUID):
        result = await self._session.execute(
            text(
                """
                select c.id as contract_id, c.buyer_user_id, c.seller_organization_id,
                       c.status::text as contract_status, c.current_version_id,
                       cv.version_no, cv.title as version_title
                from public.contracts c
                join public.contract_versions cv on cv.id = c.current_version_id
                where c.id = :contract_id
                for update of c
                """
            ),
            {"contract_id": contract_id},
        )
        row = result.mappings().one_or_none()
        return (
            RevisionContractRecord(**row, listing_title=row["version_title"], buyer_name="")
            if row
            else None
        )

    async def _lock_revision(self, revision_id: UUID):
        result = await self._session.execute(
            text(
                """
                select rr.id, rr.contract_id, rr.contract_version_id,
                       rr.requested_by_user_id, rr.status::text as status,
                       c.buyer_user_id, c.seller_organization_id,
                       c.status::text as contract_status, c.current_version_id,
                       cv.version_no, cv.title as version_title
                from public.revision_requests rr
                join public.contracts c on c.id = rr.contract_id
                join public.contract_versions cv on cv.id = rr.contract_version_id
                where rr.id = :revision_id
                for update of rr, c
                """
            ),
            {"revision_id": revision_id},
        )
        return result.mappings().one_or_none()

    async def _insert_item(
        self, revision_id: UUID, contract_id: UUID, item_order: int, item: dict[str, Any]
    ) -> UUID:
        clause_id = await self._validate_item_references(
            revision_id, contract_id, item["clause_id"], item["document_ids"]
        )
        item_id = uuid4()
        await self._session.execute(
            text(
                """
                insert into public.revision_request_items (
                    id, revision_request_id, clause_id, item_order,
                    request_type, reason, requested_text
                ) values (
                    :id, :revision_id, :clause_id, :item_order,
                    :request_type, :reason, :requested_text
                )
                """
            ),
            {
                "id": item_id,
                "revision_id": revision_id,
                "item_order": item_order,
                "clause_id": clause_id,
                **{key: item[key] for key in ("request_type", "reason", "requested_text")},
            },
        )
        await self._replace_documents(item_id, contract_id, item["document_ids"])
        return item_id

    async def _replace_documents(
        self, item_id: UUID, contract_id: UUID, document_ids: list[UUID]
    ) -> None:
        if document_ids:
            result = await self._session.execute(
                text(
                    """
                    select count(*) from public.documents
                    where contract_id = :contract_id
                      and id = any(cast(:document_ids as uuid[]))
                    """
                ),
                {"contract_id": contract_id, "document_ids": document_ids},
            )
            if result.scalar_one() != len(document_ids):
                raise RevisionReferenceError
        await self._session.execute(
            text(
                "delete from public.revision_request_item_documents "
                "where revision_request_item_id = :item_id"
            ),
            {"item_id": item_id},
        )
        for document_id in document_ids:
            await self._session.execute(
                text(
                    """
                    insert into public.revision_request_item_documents (
                        revision_request_item_id, document_id
                    ) values (:item_id, :document_id)
                    """
                ),
                {"item_id": item_id, "document_id": document_id},
            )

    async def _validate_item_references(
        self,
        revision_id: UUID,
        contract_id: UUID,
        clause_id: UUID | None,
        document_ids: list[UUID],
    ) -> UUID | None:
        normalized_clause_id = clause_id
        if clause_id is not None:
            result = await self._session.execute(
                text(
                    """
                    select cc.id
                        from public.contract_clauses cc
                        join public.revision_requests rr
                          on rr.contract_version_id = cc.contract_version_id
                        where rr.id = :revision_id
                          and (cc.id = :clause_id or cc.source_listing_clause_id = :clause_id)
                    """
                ),
                {"revision_id": revision_id, "clause_id": clause_id},
            )
            normalized_clause_id = result.scalar_one_or_none()
            if normalized_clause_id is None:
                raise RevisionReferenceError
        if len(set(document_ids)) != len(document_ids):
            raise RevisionReferenceError
        if document_ids:
            result = await self._session.execute(
                text(
                    """
                    select count(*) from public.documents
                    where contract_id = :contract_id
                      and id = any(cast(:document_ids as uuid[]))
                    """
                ),
                {"contract_id": contract_id, "document_ids": document_ids},
            )
            if result.scalar_one() != len(document_ids):
                raise RevisionReferenceError
        return normalized_clause_id

    async def _decision_values(self, revision_id: UUID) -> set[str]:
        result = await self._session.execute(
            text(
                "select decision::text from public.revision_request_items "
                "where revision_request_id = :revision_id for update"
            ),
            {"revision_id": revision_id},
        )
        return set(result.scalars().all())

    async def _create_version(
        self, row, actor_user_id: UUID, clauses: list[RevisionClauseRecord]
    ) -> int:
        version_id = uuid4()
        version_no = row["version_no"] + 1
        body = "\n\n".join(f"{clause.title}\n{clause.body}" for clause in clauses)
        result = await self._session.execute(
            text(
                """
                insert into public.contract_versions (
                    id, contract_id, version_no, title, body, content_sha256,
                    source_listing_version_id, created_from_revision_request_id,
                    structured_data, created_by
                )
                select :id, :contract_id, :version_no, :title, :body,
                       encode(digest(:body, 'sha256'), 'hex'), source_listing_version_id,
                       :revision_id, structured_data, :actor_user_id
                from public.contract_versions
                where id = :base_version_id and contract_id = :contract_id
                returning id
                """
            ),
            {
                "id": version_id,
                "contract_id": row["contract_id"],
                "version_no": version_no,
                "title": row["version_title"],
                "body": body,
                "revision_id": row["id"],
                "actor_user_id": actor_user_id,
                "base_version_id": row["contract_version_id"],
            },
        )
        if result.scalar_one_or_none() is None:
            raise RevisionVersionConflictError
        for order, clause in enumerate(clauses, start=1):
            await self._session.execute(
                text(
                    """
                    insert into public.contract_clauses (
                        contract_version_id, source_listing_clause_id, clause_order,
                        clause_key, title, body, source_page, source_bbox
                    ) values (
                        :version_id, :source_listing_clause_id, :clause_order,
                        :clause_key, :title, :body, :source_page, cast(:source_bbox as jsonb)
                    )
                    """
                ),
                {
                    "version_id": version_id,
                    "source_listing_clause_id": clause.source_listing_clause_id,
                    "clause_order": order,
                    "clause_key": clause.clause_key,
                    "title": clause.title,
                    "body": clause.body,
                    "source_page": clause.source_page,
                    "source_bbox": json.dumps(clause.source_bbox),
                },
            )
        updated = await self._session.execute(
            text(
                """
                update public.contracts
                set current_version_id = :version_id, status = 'signing'
                where id = :contract_id and current_version_id = :base_version_id
                returning id
                """
            ),
            {
                "version_id": version_id,
                "contract_id": row["contract_id"],
                "base_version_id": row["contract_version_id"],
            },
        )
        if updated.scalar_one_or_none() is None:
            raise RevisionVersionConflictError
        return version_no

    async def _claim_idempotency(
        self, actor_user_id: UUID, operation: str, key: str, request_hash: str
    ) -> dict[str, Any] | None:
        await self._session.execute(
            text(
                """
                delete from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key and expires_at <= now()
                """
            ),
            {"actor_user_id": actor_user_id, "operation": operation, "key": key},
        )
        claimed = await self._session.execute(
            text(
                """
                insert into public.idempotency_records (
                    actor_user_id, operation, idempotency_key, request_hash, expires_at
                ) values (
                    :actor_user_id, :operation, :key, :request_hash, now() + interval '24 hours'
                )
                on conflict (actor_user_id, operation, idempotency_key)
                    where actor_user_id is not null
                do nothing returning id
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "operation": operation,
                "key": key,
                "request_hash": request_hash,
            },
        )
        if claimed.scalar_one_or_none() is not None:
            return None
        existing = await self._session.execute(
            text(
                """
                select request_hash, response_body
                from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {"actor_user_id": actor_user_id, "operation": operation, "key": key},
        )
        row = existing.mappings().one()
        if row["request_hash"] != request_hash or row["response_body"] is None:
            raise RevisionIdempotencyConflictError
        return row["response_body"]

    async def _complete_idempotency(
        self, actor_user_id: UUID, operation: str, key: str, mutation: RevisionMutationRecord
    ) -> None:
        body = {
            "revision_request_id": str(mutation.revision_request_id),
            "contract_id": str(mutation.contract_id),
            "revision_status": mutation.revision_status,
            "contract_status": mutation.contract_status,
            "version_no": mutation.version_no,
        }
        await self._session.execute(
            text(
                """
                update public.idempotency_records
                set response_status = 200, response_body = cast(:body as jsonb),
                    resource_type = 'revision_request', resource_id = :resource_id
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {
                "body": json.dumps(body),
                "resource_id": mutation.revision_request_id,
                "actor_user_id": actor_user_id,
                "operation": operation,
                "key": key,
            },
        )

    @staticmethod
    def _mutation_from_body(body: dict[str, Any], *, replayed: bool) -> RevisionMutationRecord:
        return RevisionMutationRecord(
            revision_request_id=UUID(body["revision_request_id"]),
            contract_id=UUID(body["contract_id"]),
            revision_status=body["revision_status"],
            contract_status=body["contract_status"],
            version_no=body.get("version_no"),
            replayed=replayed,
        )

    async def _notify_seller(
        self, organization_id: UUID, contract_id: UUID, notification_type: str
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.notifications (
                    user_id, notification_type, title, body, resource_type, resource_id
                )
                select user_id, :notification_type, '계약 수정 요청 알림',
                       '계약 수정 요청에 새로운 응답이 있습니다.', 'contract', :contract_id
                from public.organization_members where organization_id = :organization_id
                """
            ),
            {
                "notification_type": notification_type,
                "contract_id": contract_id,
                "organization_id": organization_id,
            },
        )

    async def _notify_buyer(self, buyer_user_id: UUID, contract_id: UUID) -> None:
        await self._session.execute(
            text(
                """
                insert into public.notifications (
                    user_id, notification_type, title, body, resource_type, resource_id
                ) values (
                    :user_id, 'revision_decided', '수정 요청 답변 도착',
                    '셀러가 수정 요청에 답변했습니다.', 'contract', :contract_id
                )
                """
            ),
            {"user_id": buyer_user_id, "contract_id": contract_id},
        )

    async def _audit(
        self, contract_id: UUID, actor_user_id: UUID, actor_role: str, event: str, target_id: UUID
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.audit_events (
                    contract_id, actor_user_id, actor_role, event_type, target_type, target_id
                ) values (
                    :contract_id, :actor_user_id, :actor_role, :event,
                    'revision_request', :target_id
                )
                """
            ),
            {
                "contract_id": contract_id,
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "event": event,
                "target_id": target_id,
            },
        )

    async def _reset_transaction(self) -> None:
        if self._session.in_transaction():
            await self._session.rollback()
