import hashlib
import json
from dataclasses import replace
from typing import Any
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.repositories.revisions import (
    RevisionClauseRecord,
    RevisionContractRecord,
    RevisionIdempotencyConflictError,
    RevisionItemRecord,
    RevisionNotFoundError,
    RevisionPendingItemsError,
    RevisionReferenceError,
    RevisionRepository,
    RevisionRepositoryError,
    RevisionRequestRecord,
    RevisionStateConflictError,
    RevisionVersionConflictError,
)
from app.schemas.contracts import ContractClauseResponse
from app.schemas.revisions import (
    RevisionDecisionPreview,
    RevisionDecisionRequest,
    RevisionItemDecisionUpdate,
    RevisionItemInput,
    RevisionItemResponse,
    RevisionMutationResponse,
    RevisionRequestCreate,
    RevisionRequestResponse,
    RevisionResponseRequest,
    SellerRevisionRequestListItem,
)


class RevisionService:
    def __init__(self, repository: RevisionRepository) -> None:
        self._repository = repository

    async def create(
        self,
        contract_id: UUID,
        actor: AuthenticatedUser,
        payload: RevisionRequestCreate,
        idempotency_key: str,
    ) -> RevisionMutationResponse:
        context = await self._contract(contract_id)
        self._authorize_buyer(context, actor)
        if context.version_no != payload.base_version_no:
            self._version_conflict()
        if context.contract_status not in {"seller_review", "revision_requested"}:
            self._invalid_state("A revision request cannot be created in this contract state.")
        return await self._mutation(
            self._repository.create_revision(
                contract_id=contract_id,
                actor_user_id=actor.id,
                base_version_no=payload.base_version_no,
                message=payload.message,
                items=[self._item_data(item) for item in payload.items],
                idempotency_key=idempotency_key,
                request_hash=self._hash(
                    {"contract_id": str(contract_id), **payload.model_dump(mode="json")}
                ),
            )
        )

    async def get(
        self,
        revision_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> RevisionRequestResponse:
        record = await self._revision(revision_id)
        await self._authorize_party(record, actor, organization_header)
        return self._detail(record)

    async def list_seller(
        self,
        actor: AuthenticatedUser,
        organization_header: str | None,
        statuses: set[str],
    ) -> list[SellerRevisionRequestListItem]:
        organization_id = await self._authorize_seller(actor, organization_header)
        try:
            records = await self._repository.list_seller_revisions(organization_id, statuses)
            unread_contract_ids = await self._repository.list_unread_revision_contract_ids(
                actor.id, list({record.contract_id for record in records})
            )
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)
        return [
            SellerRevisionRequestListItem(
                id=record.id,
                contract_id=record.contract_id,
                listing_title=record.listing_title,
                buyer_name=record.buyer_name,
                status=record.status,
                message=record.message,
                item_count=len(record.items),
                item_summary=[item.reason for item in record.items[:3]],
                has_unread=record.contract_id in unread_contract_ids,
                sent_at=record.sent_at,
                updated_at=record.updated_at,
            )
            for record in records
        ]

    async def list_buyer(
        self, actor: AuthenticatedUser, statuses: set[str]
    ) -> list[SellerRevisionRequestListItem]:
        try:
            records = await self._repository.list_buyer_revisions(actor.id, statuses)
            unread_contract_ids = await self._repository.list_unread_revision_contract_ids(
                actor.id, [record.contract_id for record in records]
            )
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)
        return [
            SellerRevisionRequestListItem(
                id=record.id,
                contract_id=record.contract_id,
                listing_title=record.listing_title,
                buyer_name=record.buyer_name,
                status=record.status,
                message=record.message,
                item_count=len(record.items),
                item_summary=[item.reason for item in record.items[:3]],
                has_unread=record.contract_id in unread_contract_ids,
                sent_at=record.sent_at,
                updated_at=record.updated_at,
            )
            for record in records
        ]

    async def mark_buyer_read(self, revision_id: UUID, actor: AuthenticatedUser) -> None:
        record = await self._revision(revision_id)
        self._authorize_revision_buyer(record, actor)
        try:
            await self._repository.mark_buyer_revision_read(actor.id, revision_id)
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)

    async def add_item(
        self,
        revision_id: UUID,
        actor: AuthenticatedUser,
        payload: RevisionItemInput,
        idempotency_key: str,
    ) -> RevisionMutationResponse:
        record = await self._revision(revision_id)
        self._authorize_revision_buyer(record, actor)
        if record.status != "draft":
            self._invalid_state("Only draft revision requests can add items.")
        return await self._mutation(
            self._repository.add_item(
                revision_id,
                actor.id,
                self._item_data(payload),
                idempotency_key,
                self._hash(payload.model_dump(mode="json")),
            )
        )

    async def patch_item(
        self,
        revision_id: UUID,
        item_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
        payload: RevisionItemInput | RevisionItemDecisionUpdate,
    ) -> RevisionRequestResponse:
        record = await self._revision(revision_id)
        if isinstance(payload, RevisionItemInput):
            self._authorize_revision_buyer(record, actor)
            if record.status != "draft":
                self._invalid_state("Only draft revision items can be edited by the buyer.")
            await self._run(
                self._repository.update_draft_item(
                    revision_id, item_id, actor.id, self._item_data(payload)
                )
            )
        else:
            organization_id = await self._authorize_seller(actor, organization_header)
            if record.seller_organization_id != organization_id:
                self._access_denied()
            if record.status != "sent":
                self._invalid_state("Only sent revision requests can be decided by the seller.")
            await self._run(
                self._repository.decide_item(
                    revision_id,
                    item_id,
                    actor.id,
                    organization_id,
                    payload.decision,
                    payload.seller_reason,
                    payload.counter_text,
                )
            )
        return self._detail(await self._revision(revision_id))

    async def delete_item(self, revision_id: UUID, item_id: UUID, actor: AuthenticatedUser) -> None:
        record = await self._revision(revision_id)
        self._authorize_revision_buyer(record, actor)
        if record.status != "draft":
            self._invalid_state("Only draft revision items can be deleted.")
        await self._run(self._repository.delete_draft_item(revision_id, item_id, actor.id))

    async def send(
        self,
        revision_id: UUID,
        actor: AuthenticatedUser,
        idempotency_key: str,
    ) -> RevisionMutationResponse:
        record = await self._revision(revision_id)
        self._authorize_revision_buyer(record, actor)
        if record.status != "draft":
            self._invalid_state("Only draft revision requests can be sent.")
        if not record.items:
            self._invalid_state("A revision request must contain at least one item.")
        self._ensure_base_is_current(record)
        return await self._mutation(
            self._repository.send_revision(
                revision_id,
                actor.id,
                idempotency_key,
                self._hash({"revision_request_id": str(revision_id)}),
            )
        )

    async def decide(
        self,
        revision_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
        payload: RevisionDecisionRequest,
        idempotency_key: str,
    ) -> RevisionMutationResponse:
        record = await self._revision(revision_id)
        organization_id = await self._authorize_seller(actor, organization_header)
        if record.seller_organization_id != organization_id:
            self._access_denied()
        if record.status != "sent":
            self._invalid_state("Only sent revision requests can be finalized.")
        if not record.items or any(item.decision == "pending" for item in record.items):
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="REVISION_ITEMS_PENDING",
                message="Every revision item must be decided before finalization.",
            )
        self._ensure_base_is_current(record)
        clauses = self._apply_items(record, include_pending=False)
        return await self._mutation(
            self._repository.finalize_decision(
                revision_id,
                actor.id,
                organization_id,
                payload.seller_message,
                clauses,
                idempotency_key,
                self._hash(
                    {
                        "revision_request_id": str(revision_id),
                        **payload.model_dump(mode="json"),
                    }
                ),
            )
        )

    async def reject_all(
        self,
        revision_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
        payload: RevisionDecisionRequest,
        idempotency_key: str,
    ) -> RevisionMutationResponse:
        record = await self._revision(revision_id)
        organization_id = await self._authorize_seller(actor, organization_header)
        if record.seller_organization_id != organization_id:
            self._access_denied()
        if record.status != "sent":
            self._invalid_state("Only sent revision requests can be rejected.")
        self._ensure_base_is_current(record)
        return await self._mutation(
            self._repository.reject_all(
                revision_id,
                actor.id,
                organization_id,
                payload.seller_message,
                idempotency_key,
                self._hash(
                    {
                        "revision_request_id": str(revision_id),
                        **payload.model_dump(mode="json"),
                    }
                ),
            )
        )

    async def respond(
        self,
        revision_id: UUID,
        actor: AuthenticatedUser,
        payload: RevisionResponseRequest,
        idempotency_key: str,
    ) -> RevisionMutationResponse:
        record = await self._revision(revision_id)
        self._authorize_revision_buyer(record, actor)
        if record.status not in {"partially_accepted", "countered"}:
            self._invalid_state("Only partial or countered decisions can receive a buyer response.")
        self._ensure_base_is_current(record)
        clauses = self._apply_items(record, include_pending=False)
        return await self._mutation(
            self._repository.respond(
                revision_id,
                actor.id,
                payload.decision == "accepted",
                payload.message,
                clauses,
                idempotency_key,
                self._hash(
                    {
                        "revision_request_id": str(revision_id),
                        **payload.model_dump(mode="json"),
                    }
                ),
            )
        )

    def _detail(self, record: RevisionRequestRecord) -> RevisionRequestResponse:
        clauses = self._apply_items(record, include_pending=True)
        pending = sum(item.decision == "pending" for item in record.items)
        requires_response = record.status in {"partially_accepted", "countered"}
        decisions = {item.decision for item in record.items}
        return RevisionRequestResponse(
            id=record.id,
            contract_id=record.contract_id,
            base_version_no=record.base_version_no,
            status=record.status,
            requested_by_user_id=record.requested_by_user_id,
            message=record.message,
            seller_message=record.decision_message,
            response_message=record.response_message,
            items=[self._item_response(item) for item in record.items],
            decision_preview=RevisionDecisionPreview(
                resulting_clauses=[
                    ContractClauseResponse(
                        id=clause.id,
                        clause_order=index,
                        clause_key=clause.clause_key,
                        title=clause.title,
                        body=clause.body,
                    )
                    for index, clause in enumerate(clauses, start=1)
                ],
                pending_item_count=pending,
                requires_buyer_response=requires_response,
                will_create_version=(
                    pending == 0
                    and decisions == {"accepted"}
                    or record.status in {"partially_accepted", "countered"}
                ),
            ),
            created_at=record.created_at,
            updated_at=record.updated_at,
            sent_at=record.sent_at,
            decided_at=record.decided_at,
            responded_at=record.responded_at,
        )

    @staticmethod
    def _apply_items(
        record: RevisionRequestRecord, *, include_pending: bool
    ) -> list[RevisionClauseRecord]:
        clauses = list(record.clauses)
        by_id = {clause.id: index for index, clause in enumerate(clauses)}
        additions: list[RevisionClauseRecord] = []
        deleted: set[UUID] = set()
        for item in record.items:
            if item.decision == "rejected" or (item.decision == "pending" and not include_pending):
                continue
            text = item.counter_text if item.decision == "countered" else item.requested_text
            if item.decision == "pending":
                continue
            if item.request_type == "delete" and item.decision == "accepted":
                if item.clause_id is not None:
                    deleted.add(item.clause_id)
                continue
            if item.request_type == "add":
                if text is not None:
                    additions.append(
                        RevisionClauseRecord(
                            id=item.id,
                            clause_order=len(clauses) + len(additions) + 1,
                            clause_key=None,
                            title="추가 조항",
                            body=text,
                        )
                    )
                continue
            if item.clause_id is not None and text is not None and item.clause_id in by_id:
                index = by_id[item.clause_id]
                clauses[index] = replace(clauses[index], body=text)
        return [clause for clause in clauses if clause.id not in deleted] + additions

    @staticmethod
    def _item_response(item: RevisionItemRecord) -> RevisionItemResponse:
        return RevisionItemResponse(
            id=item.id,
            item_order=item.item_order,
            request_type=item.request_type,
            clause_id=item.clause_id,
            reason=item.reason,
            requested_text=item.requested_text,
            document_ids=item.document_ids,
            decision=item.decision,
            seller_reason=item.decision_reason,
            counter_text=item.counter_text,
            decided_at=item.decided_at,
        )

    @staticmethod
    def _item_data(item: RevisionItemInput) -> dict[str, Any]:
        return item.model_dump(mode="json")

    async def _contract(self, contract_id: UUID) -> RevisionContractRecord:
        try:
            record = await self._repository.get_contract(contract_id)
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)
        if record is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CONTRACT_NOT_FOUND",
                message="Contract was not found.",
            )
        return record

    async def _revision(self, revision_id: UUID) -> RevisionRequestRecord:
        try:
            record = await self._repository.get_revision(revision_id)
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)
        if record is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="REVISION_REQUEST_NOT_FOUND",
                message="Revision request was not found.",
            )
        return record

    async def _authorize_party(
        self,
        record: RevisionRequestRecord,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> None:
        if record.buyer_user_id == actor.id:
            return
        if record.status == "draft":
            self._access_denied()
        if organization_header is None:
            self._access_denied()
        organization_id = await self._authorize_seller(actor, organization_header)
        if record.seller_organization_id != organization_id:
            self._access_denied()

    async def _authorize_seller(
        self, actor: AuthenticatedUser, organization_header: str | None
    ) -> UUID:
        organization_id = self._organization_id(organization_header)
        try:
            member = await self._repository.is_seller_member(actor.id, organization_id)
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)
        if not member:
            self._access_denied()
        return organization_id

    @staticmethod
    def _authorize_buyer(context: RevisionContractRecord, actor: AuthenticatedUser) -> None:
        if context.buyer_user_id != actor.id:
            RevisionService._access_denied()

    @staticmethod
    def _authorize_revision_buyer(record: RevisionRequestRecord, actor: AuthenticatedUser) -> None:
        if record.buyer_user_id != actor.id or record.requested_by_user_id != actor.id:
            RevisionService._access_denied()

    @staticmethod
    def _ensure_base_is_current(record: RevisionRequestRecord) -> None:
        if record.current_version_id != record.contract_version_id:
            RevisionService._version_conflict()
        if record.contract_status in {"signed", "cancelled"}:
            RevisionService._invalid_state("The contract no longer accepts revision changes.")

    async def _mutation(self, operation) -> RevisionMutationResponse:
        try:
            record = await operation
        except RevisionIdempotencyConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_CONFLICT",
                message="The Idempotency-Key was already used for a different request.",
            ) from exc
        except RevisionVersionConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="VERSION_CONFLICT",
                message="The contract version changed during revision processing.",
            ) from exc
        except RevisionPendingItemsError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="REVISION_ITEMS_PENDING",
                message="Every revision item must be decided before finalization.",
            ) from exc
        except RevisionNotFoundError as exc:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="REVISION_REQUEST_NOT_FOUND",
                message="Revision request was not found.",
            ) from exc
        except RevisionReferenceError as exc:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CONTRACT_ACCESS_DENIED",
                message="A referenced clause or document does not belong to this contract.",
            ) from exc
        except RevisionStateConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="INVALID_STATE_TRANSITION",
                message="The revision request cannot perform this operation in its current state.",
            ) from exc
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)
        return RevisionMutationResponse(
            revision_request_id=record.revision_request_id,
            status=record.revision_status,
            contract_id=record.contract_id,
            contract_status=record.contract_status,
            version_no=record.version_no,
            replayed=record.replayed,
        )

    async def _run(self, operation) -> None:
        try:
            await operation
        except RevisionNotFoundError as exc:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="REVISION_ITEM_NOT_FOUND",
                message="Revision request item was not found.",
            ) from exc
        except RevisionReferenceError as exc:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CONTRACT_ACCESS_DENIED",
                message="A referenced resource does not belong to this contract.",
            ) from exc
        except RevisionStateConflictError:
            self._invalid_state("The revision item cannot be changed in its current state.")
        except RevisionRepositoryError as exc:
            self._database_unavailable(exc)

    @staticmethod
    def _organization_id(header: str | None) -> UUID:
        if header is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required for seller organization APIs.",
            )
        try:
            return UUID(header)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="X-Organization-Id must be a UUID.",
            ) from exc

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _version_conflict() -> None:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="VERSION_CONFLICT",
            message="base_version_no does not match the current contract version.",
        )

    @staticmethod
    def _invalid_state(message: str) -> None:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message=message,
        )

    @staticmethod
    def _access_denied() -> None:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CONTRACT_ACCESS_DENIED",
            message="You do not have access to this contract.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
