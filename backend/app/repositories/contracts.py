from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ContractRequestSourceRecord:
    listing_id: UUID
    listing_status: str
    listing_expires_at: datetime | None
    seller_organization_id: UUID
    listing_title: str
    current_version_id: UUID | None
    service_start_date: date | None
    service_end_date: date | None
    quantity_unit: str | None
    base_price_amount_minor: int | None
    currency: str | None
    price_unit: str | None
    buyer_name: str | None
    buyer_country_code: str | None
    buyer_phone: str | None
    seller_name: str
    seller_legal_name: str | None
    seller_business_registration_no: str | None


@dataclass(frozen=True, slots=True)
class NewContractData:
    status: str
    initial_request_kind: str
    request_message: str | None
    buyer_group_name: str | None
    signing_capacity: str
    requested_people: int
    service_start_date: date
    service_end_date: date
    amount_minor: int
    currency: str
    calculation_snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ContractCreatedRecord:
    contract_id: UUID
    status: str
    version_no: int = 1


@dataclass(frozen=True, slots=True)
class ContractRecord:
    id: UUID
    listing_id: UUID | None
    listing_title: str
    buyer_user_id: UUID
    seller_organization_id: UUID
    status: str
    initial_request_kind: str
    request_message: str | None
    requested_people: int
    buyer_group_name: str | None
    signing_capacity: str
    amount_minor: int | None
    currency: str | None
    service_start_date: date
    service_end_date: date
    calculation_snapshot: dict[str, Any]
    current_version_id: UUID | None
    version_no: int | None
    version_title: str | None
    version_body: str | None
    buyer_name: str
    buyer_country_code: str | None
    buyer_group_name_snapshot: str | None
    buyer_signing_capacity: str | None
    seller_name: str
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class ContractClauseRecord:
    id: UUID
    clause_order: int
    clause_key: str | None
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class ContractVersionClauseRecord:
    id: UUID
    clause_order: int
    clause_key: str | None
    title: str
    body: str
    source_listing_clause_id: UUID | None


@dataclass(frozen=True, slots=True)
class ContractVersionRecord:
    id: UUID
    contract_id: UUID
    version_no: int
    title: str
    structured_data: dict[str, Any]
    created_by_role: str
    creation_reason: str
    created_from_revision_request_id: UUID | None
    created_at: datetime
    risk_score: int | None
    risk_finding_count: int
    clauses: list[ContractVersionClauseRecord]


@dataclass(frozen=True, slots=True)
class ContractVersionApprovalContextRecord:
    contract_id: UUID
    contract_version_id: UUID
    version_no: int
    buyer_user_id: UUID
    seller_organization_id: UUID
    contract_status: str
    current_version_id: UUID


@dataclass(frozen=True, slots=True)
class ContractVersionApprovalRecord:
    id: UUID
    contract_version_id: UUID
    party_role: str
    approved_by_user_id: UUID
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class ContractVersionApprovalMutationRecord:
    context: ContractVersionApprovalContextRecord
    approvals: list[ContractVersionApprovalRecord]
    approved_role: str
    already_approved: bool
    contract_status: str


@dataclass(frozen=True, slots=True)
class SignatureRequestRecord:
    id: UUID
    contract_id: UUID
    contract_version_id: UUID
    status: str
    provider: str
    provider_document_id: str | None
    provider_status: str | None
    current_signing_order: int | None
    completed_at: datetime | None
    signed_document_id: UUID | None = None
    audit_trail_document_id: UUID | None = None
    reused: bool = False


@dataclass(frozen=True, slots=True)
class SignatureContactRecord:
    buyer_name: str
    buyer_email: str | None
    seller_name: str
    seller_email: str | None


@dataclass(frozen=True, slots=True)
class SignatureSourceDocumentRecord:
    storage_bucket: str
    storage_object_path: str


@dataclass(frozen=True, slots=True)
class SellerListingRequestCountRecord:
    listing_id: UUID
    listing_title: str
    listing_status: str
    request_count: int


class ContractRepositoryUnavailableError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class ContractStateConflictError(Exception):
    pass


class ContractVersionNotFoundError(Exception):
    pass


class ContractVersionApprovalAccessError(Exception):
    pass


class ContractVersionConflictError(Exception):
    pass


ContractBuilder = Callable[[ContractRequestSourceRecord | None], Awaitable[NewContractData]]


class ContractRepository(Protocol):
    async def create_contract_request(
        self,
        *,
        listing_id: UUID,
        buyer_user_id: UUID,
        buyer_email: str | None,
        idempotency_key: str,
        request_hash: str,
        build: ContractBuilder,
    ) -> ContractCreatedRecord: ...

    async def get_contract(self, contract_id: UUID) -> ContractRecord | None: ...

    async def list_buyer_contracts(self, buyer_user_id: UUID) -> list[ContractRecord]: ...

    async def list_seller_contracts(self, seller_organization_id: UUID) -> list[ContractRecord]: ...

    async def list_unread_response_contract_ids(
        self, buyer_user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]: ...

    async def list_seller_listing_request_counts(
        self, seller_organization_id: UUID
    ) -> list[SellerListingRequestCountRecord]: ...

    async def list_contract_clauses(
        self, contract_version_id: UUID
    ) -> list[ContractClauseRecord]: ...

    async def list_contract_versions(self, contract_id: UUID) -> list[ContractVersionRecord]: ...

    async def get_contract_version_approval_context(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> ContractVersionApprovalContextRecord | None: ...

    async def list_contract_version_approvals(
        self, contract_version_id: UUID
    ) -> list[ContractVersionApprovalRecord]: ...

    async def approve_contract_version(
        self,
        *,
        contract_id: UUID,
        contract_version_id: UUID,
        actor_user_id: UUID,
        party_role: str,
    ) -> ContractVersionApprovalMutationRecord: ...

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...

    async def begin_signature_request(
        self,
        *,
        contract_id: UUID,
        contract_version_id: UUID,
        requested_by: UUID,
        idempotency_key: str,
        provider_template_id: str,
        buyer_name: str,
        buyer_email: str,
        seller_name: str,
        seller_email: str,
    ) -> SignatureRequestRecord: ...

    async def get_signature_contacts(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> SignatureContactRecord | None: ...

    async def get_signature_source_document(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> SignatureSourceDocumentRecord | None: ...

    async def mark_signature_request_dispatched(
        self, signature_request_id: UUID, provider_document_id: str, provider_status: str
    ) -> SignatureRequestRecord: ...

    async def mark_signature_request_failed(self, signature_request_id: UUID) -> None: ...

    async def get_signature_request(
        self, signature_request_id: UUID
    ) -> SignatureRequestRecord | None: ...

    async def get_signature_request_by_provider_document_id(
        self, provider_document_id: str
    ) -> SignatureRequestRecord | None: ...

    async def update_signature_request_status(
        self,
        signature_request_id: UUID,
        *,
        provider_status: str,
        current_signing_order: int | None,
    ) -> SignatureRequestRecord: ...

    async def complete_signature_request(
        self,
        signature_request_id: UUID,
        *,
        signed_size_bytes: int,
        signed_sha256: str,
        audit_size_bytes: int,
        audit_sha256: str,
    ) -> SignatureRequestRecord: ...

    async def cancel_contract(
        self,
        *,
        contract_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[datetime, bool]: ...


class SqlAlchemyContractRepository:
    _OPERATION_CREATE = "create_contract_request"
    _OPERATION_CANCEL = "cancel_contract"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_contract_request(
        self,
        *,
        listing_id: UUID,
        buyer_user_id: UUID,
        buyer_email: str | None,
        idempotency_key: str,
        request_hash: str,
        build: ContractBuilder,
    ) -> ContractCreatedRecord:
        try:
            async with self._session.begin():
                existing = await self._claim_idempotency(
                    buyer_user_id, self._OPERATION_CREATE, idempotency_key, request_hash
                )
                if existing is not None:
                    return existing
                source = await self._get_request_source(listing_id, buyer_user_id)
                data = await build(source)
                created = await self._insert_contract(source, data, buyer_user_id, buyer_email)
                await self._complete_idempotency(
                    buyer_user_id,
                    self._OPERATION_CREATE,
                    idempotency_key,
                    created.contract_id,
                    {
                        "contract_id": str(created.contract_id),
                        "status": created.status,
                        "version_no": created.version_no,
                    },
                )
                return created
        except (IdempotencyConflictError, ContractStateConflictError):
            raise
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def get_signature_contacts(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> SignatureContactRecord | None:
        """Load immutable buyer contact data and the seller who approved this version."""
        try:
            result = await self._session.execute(
                text(
                    """
                    select buyer.name_snapshot as buyer_name,
                           buyer.email_snapshot as buyer_email,
                           seller.name_snapshot as seller_name,
                           seller_user.email as seller_email
                    from public.contracts c
                    join public.contract_parties buyer
                      on buyer.contract_id = c.id and buyer.party_role = 'buyer'
                    join public.contract_parties seller
                      on seller.contract_id = c.id and seller.party_role = 'seller'
                    left join public.contract_version_approvals seller_approval
                      on seller_approval.contract_version_id = :contract_version_id
                     and seller_approval.party_role = 'seller'
                    left join auth.users seller_user
                      on seller_user.id = seller_approval.approved_by_user_id
                    where c.id = :contract_id and c.current_version_id = :contract_version_id
                    """
                ),
                {"contract_id": contract_id, "contract_version_id": contract_version_id},
            )
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return SignatureContactRecord(**row) if row is not None else None

    async def get_signature_source_document(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> SignatureSourceDocumentRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select d.storage_bucket, d.storage_object_path
                    from public.contracts c
                    join public.documents d
                      on d.listing_id = c.listing_id
                     and d.purpose = 'source_contract'
                     and d.status in ('uploaded', 'ready')
                    where c.id = :contract_id and c.current_version_id = :contract_version_id
                    order by d.created_at desc
                    limit 1
                    """
                ),
                {"contract_id": contract_id, "contract_version_id": contract_version_id},
            )
        except SQLAlchemyError as exc:
            logger.exception("signature source document lookup failed")
            raise ContractRepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return SignatureSourceDocumentRecord(**row) if row is not None else None

    async def _claim_idempotency(
        self, actor_user_id: UUID, operation: str, key: str, request_hash: str
    ) -> ContractCreatedRecord | None:
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
        result = await self._session.execute(
            text(
                """
                insert into public.idempotency_records (
                    actor_user_id, operation, idempotency_key, request_hash, expires_at
                ) values (
                    :actor_user_id, :operation, :key, :request_hash, now() + interval '24 hours'
                )
                on conflict (actor_user_id, operation, idempotency_key)
                    where actor_user_id is not null
                do nothing
                returning id
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "operation": operation,
                "key": key,
                "request_hash": request_hash,
            },
        )
        if result.scalar_one_or_none() is not None:
            return None
        existing = await self._session.execute(
            text(
                """
                select request_hash, response_body, resource_id
                from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {"actor_user_id": actor_user_id, "operation": operation, "key": key},
        )
        row = existing.mappings().one()
        if row["request_hash"] != request_hash or row["response_body"] is None:
            raise IdempotencyConflictError
        body = row["response_body"]
        return ContractCreatedRecord(
            contract_id=row["resource_id"],
            status=body["status"],
            version_no=body["version_no"],
        )

    async def _complete_idempotency(
        self,
        actor_user_id: UUID,
        operation: str,
        key: str,
        resource_id: UUID,
        response_body: dict[str, Any],
    ) -> None:
        await self._session.execute(
            text(
                """
                update public.idempotency_records
                set response_status = 200, response_body = cast(:response_body as jsonb),
                    resource_type = 'contract', resource_id = :resource_id
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "operation": operation,
                "key": key,
                "resource_id": resource_id,
                "response_body": json.dumps(response_body),
            },
        )

    async def _get_request_source(
        self, listing_id: UUID, buyer_user_id: UUID
    ) -> ContractRequestSourceRecord | None:
        result = await self._session.execute(
            text(
                """
                select l.id as listing_id, l.status::text as listing_status,
                       l.expires_at as listing_expires_at, l.seller_organization_id,
                       coalesce(l.display_title, l.title) as listing_title,
                       l.current_version_id, lt.service_start_date, lt.service_end_date,
                       lt.quantity_unit, lt.base_price_amount_minor, lt.currency, lt.price_unit,
                       p.display_name as buyer_name, p.country_code as buyer_country_code,
                       p.phone as buyer_phone, o.name as seller_name,
                       o.legal_name as seller_legal_name,
                       o.business_registration_no as seller_business_registration_no
                from public.listings l
                join public.organizations o on o.id = l.seller_organization_id
                left join public.listing_terms lt on lt.listing_id = l.id
                left join public.profiles p on p.id = :buyer_user_id
                where l.id = :listing_id
                for update of l
                """
            ),
            {"listing_id": listing_id, "buyer_user_id": buyer_user_id},
        )
        row = result.mappings().one_or_none()
        return ContractRequestSourceRecord(**row) if row else None

    async def _insert_contract(
        self,
        source: ContractRequestSourceRecord | None,
        data: NewContractData,
        buyer_user_id: UUID,
        buyer_email: str | None,
    ) -> ContractCreatedRecord:
        if source is None or source.current_version_id is None or source.buyer_name is None:
            raise AssertionError("contract source must be validated before persistence")
        contract_id = uuid4()
        contract_version_id = uuid4()
        await self._session.execute(
            text(
                """
                insert into public.contracts (
                    id, listing_id, buyer_user_id, buyer_organization_id,
                    seller_organization_id, status, source_listing_version_id,
                    buyer_group_name, requested_people, signing_capacity,
                    estimated_price_amount_minor, estimated_price_currency,
                    request_message, initial_request_kind
                ) values (
                    :id, :listing_id, :buyer_user_id, null, :seller_organization_id,
                    'draft', :source_listing_version_id, :buyer_group_name,
                    :requested_people, cast(:signing_capacity as public.signing_capacity),
                    :amount_minor, :currency, :request_message, :initial_request_kind
                )
                """
            ),
            {
                "id": contract_id,
                "listing_id": source.listing_id,
                "buyer_user_id": buyer_user_id,
                "seller_organization_id": source.seller_organization_id,
                "source_listing_version_id": source.current_version_id,
                "buyer_group_name": data.buyer_group_name,
                "requested_people": data.requested_people,
                "signing_capacity": data.signing_capacity,
                "amount_minor": data.amount_minor,
                "currency": data.currency,
                "request_message": data.request_message,
                "initial_request_kind": data.initial_request_kind,
            },
        )
        await self._session.execute(
            text(
                """
                insert into public.contract_parties (
                    contract_id, party_role, user_id, name_snapshot,
                    country_code_snapshot, email_snapshot, phone_snapshot,
                    group_name_snapshot, group_size_snapshot, signing_capacity
                ) values (
                    :contract_id, 'buyer', :buyer_user_id, :name_snapshot,
                    :country_code, :email, :phone, :group_name, :group_size,
                    cast(:signing_capacity as public.signing_capacity)
                )
                """
            ),
            {
                "contract_id": contract_id,
                "buyer_user_id": buyer_user_id,
                "name_snapshot": source.buyer_name,
                "country_code": source.buyer_country_code,
                "email": buyer_email,
                "phone": source.buyer_phone,
                "group_name": data.buyer_group_name,
                "group_size": data.requested_people,
                "signing_capacity": data.signing_capacity,
            },
        )
        await self._session.execute(
            text(
                """
                insert into public.contract_parties (
                    contract_id, party_role, organization_id, name_snapshot,
                    legal_name_snapshot, business_registration_no_snapshot
                ) values (
                    :contract_id, 'seller', :organization_id, :name_snapshot,
                    :legal_name, :business_registration_no
                )
                """
            ),
            {
                "contract_id": contract_id,
                "organization_id": source.seller_organization_id,
                "name_snapshot": source.seller_name,
                "legal_name": source.seller_legal_name,
                "business_registration_no": source.seller_business_registration_no,
            },
        )
        await self._session.execute(
            text(
                """
                insert into public.contract_terms (
                    contract_id, service_start_date, service_end_date, people,
                    amount_minor, currency, calculation_snapshot
                ) values (
                    :contract_id, :start_date, :end_date, :people,
                    :amount_minor, :currency, cast(:snapshot as jsonb)
                )
                """
            ),
            {
                "contract_id": contract_id,
                "start_date": data.service_start_date,
                "end_date": data.service_end_date,
                "people": data.requested_people,
                "amount_minor": data.amount_minor,
                "currency": data.currency,
                "snapshot": json.dumps(data.calculation_snapshot),
            },
        )
        copied = await self._session.execute(
            text(
                """
                insert into public.contract_versions (
                    id, contract_id, version_no, title, body, content_sha256,
                    source_listing_version_id, structured_data, created_by
                )
                select :contract_version_id, :contract_id, 1, title, body, content_sha256,
                       id, structured_data || jsonb_build_object(
                           'contract_terms', cast(:terms_snapshot as jsonb)
                       ), :buyer_user_id
                from public.listing_versions
                where id = :listing_version_id and listing_id = :listing_id
                returning id
                """
            ),
            {
                "contract_version_id": contract_version_id,
                "contract_id": contract_id,
                "buyer_user_id": buyer_user_id,
                "listing_version_id": source.current_version_id,
                "listing_id": source.listing_id,
                "terms_snapshot": json.dumps(
                    {
                        "amount_minor": data.amount_minor,
                        "currency": data.currency,
                        "service_start_date": data.service_start_date.isoformat(),
                        "service_end_date": data.service_end_date.isoformat(),
                        **data.calculation_snapshot,
                    }
                ),
            },
        )
        if copied.scalar_one_or_none() is None:
            raise ContractStateConflictError
        await self._session.execute(
            text(
                """
                insert into public.contract_clauses (
                    contract_version_id, source_listing_clause_id, clause_order,
                    clause_key, title, body, source_page, source_bbox
                )
                select :contract_version_id, id, clause_order, clause_key, title,
                       body, source_page, source_bbox
                from public.listing_clauses
                where listing_version_id = :listing_version_id
                order by clause_order
                """
            ),
            {
                "contract_version_id": contract_version_id,
                "listing_version_id": source.current_version_id,
            },
        )
        await self._session.execute(
            text(
                """
                update public.contracts
                set current_version_id = :current_version_id,
                    status = cast(:status as public.contract_status)
                where id = :contract_id and status = 'draft'
                """
            ),
            {
                "current_version_id": contract_version_id,
                "status": data.status,
                "contract_id": contract_id,
            },
        )
        await self._session.execute(
            text(
                """
                insert into public.audit_events (
                    contract_id, listing_id, actor_user_id, actor_role,
                    event_type, target_type, target_id, event_data
                ) values (
                    :contract_id, :listing_id, :actor_user_id, 'buyer',
                    'contract_requested', 'contract', :contract_id,
                    cast(:event_data as jsonb)
                )
                """
            ),
            {
                "contract_id": contract_id,
                "listing_id": source.listing_id,
                "actor_user_id": buyer_user_id,
                "event_data": json.dumps(
                    {
                        "initial_request_kind": data.initial_request_kind,
                        "status": data.status,
                        "version_no": 1,
                    }
                ),
            },
        )
        await self._session.execute(
            text(
                """
                insert into public.notifications (
                    user_id, notification_type, title, body, resource_type, resource_id
                )
                select om.user_id, 'contract_requested', '새 계약 요청',
                       '새 계약 요청이 도착했습니다.', 'contract', :contract_id
                from public.organization_members om
                where om.organization_id = :organization_id
                """
            ),
            {"contract_id": contract_id, "organization_id": source.seller_organization_id},
        )
        return ContractCreatedRecord(contract_id=contract_id, status=data.status)

    async def get_contract(self, contract_id: UUID) -> ContractRecord | None:
        records = await self._contract_records("c.id = :contract_id", {"contract_id": contract_id})
        return records[0] if records else None

    async def list_buyer_contracts(self, buyer_user_id: UUID) -> list[ContractRecord]:
        return await self._contract_records(
            "c.buyer_user_id = :buyer_user_id", {"buyer_user_id": buyer_user_id}
        )

    async def list_seller_contracts(self, seller_organization_id: UUID) -> list[ContractRecord]:
        return await self._contract_records(
            "c.seller_organization_id = :seller_organization_id",
            {"seller_organization_id": seller_organization_id},
        )

    async def list_unread_response_contract_ids(
        self, buyer_user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]:
        if not contract_ids:
            return set()
        try:
            result = await self._session.execute(
                text(
                    """
                    select distinct resource_id
                    from public.notifications
                    where user_id = :buyer_user_id
                      and resource_type = 'contract'
                      and resource_id = any(cast(:contract_ids as uuid[]))
                      and read_at is null
                      and notification_type in (
                          'seller_response', 'revision_requested', 'revision_decided',
                          'final_approval_requested', 'signature_requested',
                          'signature_completed', 'contract_cancelled'
                      )
                    """
                ),
                {"buyer_user_id": buyer_user_id, "contract_ids": contract_ids},
            )
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
        return set(result.scalars().all())

    async def list_seller_listing_request_counts(
        self, seller_organization_id: UUID
    ) -> list[SellerListingRequestCountRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select l.id as listing_id, coalesce(l.display_title, l.title) as listing_title,
                           l.status::text as listing_status, count(c.id)::integer as request_count
                    from public.listings l
                    left join public.contracts c on c.listing_id = l.id
                    where l.seller_organization_id = :seller_organization_id
                    group by l.id, l.display_title, l.title, l.status
                    order by request_count desc, listing_title, l.id
                    """
                ),
                {"seller_organization_id": seller_organization_id},
            )
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
        return [SellerListingRequestCountRecord(**row) for row in result.mappings().all()]

    async def _contract_records(
        self, condition: str, params: dict[str, object]
    ) -> list[ContractRecord]:
        try:
            result = await self._session.execute(
                text(
                    f"""
                    select c.id, c.listing_id, coalesce(l.display_title, l.title, cv.title)
                               as listing_title,
                           c.buyer_user_id, c.seller_organization_id, c.status::text as status,
                           c.initial_request_kind, c.request_message, c.requested_people,
                           c.buyer_group_name, c.signing_capacity::text as signing_capacity,
                           ct.amount_minor, ct.currency, ct.service_start_date,
                           ct.service_end_date, ct.calculation_snapshot,
                           c.current_version_id, cv.version_no, cv.title as version_title,
                           cv.body as version_body, buyer.name_snapshot as buyer_name,
                           buyer.country_code_snapshot as buyer_country_code,
                           buyer.group_name_snapshot as buyer_group_name_snapshot,
                           buyer.signing_capacity::text as buyer_signing_capacity,
                           seller.name_snapshot as seller_name,
                           c.created_at, c.updated_at, c.cancelled_at
                    from public.contracts c
                    left join public.listings l on l.id = c.listing_id
                    join public.contract_terms ct on ct.contract_id = c.id
                    left join public.contract_versions cv on cv.id = c.current_version_id
                    join public.contract_parties buyer
                      on buyer.contract_id = c.id and buyer.party_role = 'buyer'
                    join public.contract_parties seller
                      on seller.contract_id = c.id and seller.party_role = 'seller'
                    where {condition}
                    order by c.updated_at desc, c.id desc
                    """  # noqa: S608 - condition is selected only by repository methods
                ),
                params,
            )
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
        return [ContractRecord(**row) for row in result.mappings().all()]

    async def list_contract_clauses(self, contract_version_id: UUID) -> list[ContractClauseRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, clause_order, clause_key, title, body
                    from public.contract_clauses
                    where contract_version_id = :contract_version_id
                    order by clause_order
                    """
                ),
                {"contract_version_id": contract_version_id},
            )
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
        return [ContractClauseRecord(**row) for row in result.mappings().all()]

    async def list_contract_versions(self, contract_id: UUID) -> list[ContractVersionRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select cv.id, cv.contract_id, cv.version_no, cv.title,
                           cv.structured_data, cv.created_from_revision_request_id,
                           cv.created_at,
                           case
                               when cv.created_by = c.buyer_user_id then 'buyer'
                               when exists (
                                   select 1 from public.organization_members om
                                   where om.organization_id = c.seller_organization_id
                                     and om.user_id = cv.created_by
                               ) then 'seller'
                               else 'system'
                           end as created_by_role,
                           case
                               when cv.version_no = 1 then 'contract_created'
                               when cv.created_from_revision_request_id is not null
                                   then 'revision_agreement'
                               else 'manual_version'
                           end as creation_reason,
                           case when latest_run.id is null then null else coalesce(sum(
                               case finding.severity::text
                                   when 'high' then 3
                                   when 'medium' then 2
                                   when 'low' then 1
                                   else 0
                               end
                           ), 0)::integer end as risk_score,
                           count(finding.id)::integer as risk_finding_count
                    from public.contract_versions cv
                    join public.contracts c on c.id = cv.contract_id
                    left join lateral (
                        select run.id
                        from public.ai_analysis_runs run
                        where run.contract_version_id = cv.id
                          and run.viewer_role = 'buyer'
                          and run.status = 'succeeded'
                        order by run.completed_at desc nulls last, run.created_at desc
                        limit 1
                    ) latest_run on true
                    left join public.ai_findings finding
                      on finding.analysis_run_id = latest_run.id
                     and finding.status <> 'dismissed'
                    where cv.contract_id = :contract_id
                    group by cv.id, c.buyer_user_id, c.seller_organization_id, latest_run.id
                    order by cv.version_no
                    """
                ),
                {"contract_id": contract_id},
            )
            versions = []
            for row in result.mappings().all():
                clauses = await self._list_version_clauses(row["id"])
                versions.append(ContractVersionRecord(**row, clauses=clauses))
            return versions
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def _list_version_clauses(
        self, contract_version_id: UUID
    ) -> list[ContractVersionClauseRecord]:
        result = await self._session.execute(
            text(
                """
                select id, clause_order, clause_key, title, body, source_listing_clause_id
                from public.contract_clauses
                where contract_version_id = :contract_version_id
                order by clause_order
                """
            ),
            {"contract_version_id": contract_version_id},
        )
        return [ContractVersionClauseRecord(**row) for row in result.mappings().all()]

    async def get_contract_version_approval_context(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> ContractVersionApprovalContextRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select c.id as contract_id, cv.id as contract_version_id, cv.version_no,
                           c.buyer_user_id, c.seller_organization_id,
                           c.status::text as contract_status, c.current_version_id
                    from public.contracts c
                    join public.contract_versions cv on cv.contract_id = c.id
                    where c.id = :contract_id and cv.id = :contract_version_id
                    """
                ),
                {"contract_id": contract_id, "contract_version_id": contract_version_id},
            )
            row = result.mappings().one_or_none()
            return ContractVersionApprovalContextRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def list_contract_version_approvals(
        self, contract_version_id: UUID
    ) -> list[ContractVersionApprovalRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, contract_version_id, party_role::text as party_role,
                           approved_by_user_id, approved_at
                    from public.contract_version_approvals
                    where contract_version_id = :contract_version_id
                    order by party_role
                    """
                ),
                {"contract_version_id": contract_version_id},
            )
            return [ContractVersionApprovalRecord(**row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def approve_contract_version(
        self,
        *,
        contract_id: UUID,
        contract_version_id: UUID,
        actor_user_id: UUID,
        party_role: str,
    ) -> ContractVersionApprovalMutationRecord:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                context = await self._lock_approval_context(contract_id, contract_version_id)
                if context is None:
                    raise ContractVersionNotFoundError
                if context.current_version_id != contract_version_id:
                    raise ContractVersionConflictError
                if context.contract_status not in {"seller_review", "signing"}:
                    raise ContractStateConflictError
                if party_role == "buyer":
                    if context.buyer_user_id != actor_user_id:
                        raise ContractVersionApprovalAccessError
                elif not await self._is_member_in_transaction(
                    actor_user_id, context.seller_organization_id
                ):
                    raise ContractVersionApprovalAccessError
                inserted = await self._session.execute(
                    text(
                        """
                        insert into public.contract_version_approvals (
                            contract_version_id, party_role, approved_by_user_id
                        ) values (
                            :contract_version_id, cast(:party_role as public.party_role),
                            :actor_user_id
                        )
                        on conflict (contract_version_id, party_role) do nothing
                        returning id
                        """
                    ),
                    {
                        "contract_version_id": contract_version_id,
                        "party_role": party_role,
                        "actor_user_id": actor_user_id,
                    },
                )
                already_approved = inserted.scalar_one_or_none() is None
                approvals = await self._list_approvals_in_transaction(contract_version_id)
                all_approved = {approval.party_role for approval in approvals} == {
                    "buyer",
                    "seller",
                }
                contract_status = context.contract_status
                if all_approved and contract_status == "seller_review":
                    await self._session.execute(
                        text("update public.contracts set status = 'signing' where id = :id"),
                        {"id": contract_id},
                    )
                    contract_status = "signing"
                if not already_approved:
                    if not all_approved:
                        # A notification is auxiliary.  Older deployments can
                        # temporarily lack its deduplication migration; that
                        # must never roll back the legally relevant approval.
                        try:
                            async with self._session.begin_nested():
                                await self._notify_contract_approval_counterparty(
                                    contract_id=contract_id,
                                    contract_version_id=contract_version_id,
                                    buyer_user_id=context.buyer_user_id,
                                    seller_organization_id=context.seller_organization_id,
                                    approved_role=party_role,
                                )
                        except SQLAlchemyError:
                            pass
                    await self._session.execute(
                        text(
                            """
                            insert into public.audit_events (
                                contract_id, actor_user_id, actor_role, event_type,
                                target_type, target_id, event_data
                            ) values (
                                :contract_id, :actor_user_id, cast(:party_role as text),
                                'contract_version_approved', 'contract_version',
                                :contract_version_id,
                                jsonb_build_object('party_role', cast(:party_role as text))
                            )
                            """
                        ),
                        {
                            "contract_id": contract_id,
                            "actor_user_id": actor_user_id,
                            "party_role": party_role,
                            "contract_version_id": contract_version_id,
                        },
                    )
                return ContractVersionApprovalMutationRecord(
                    context=context,
                    approvals=approvals,
                    approved_role=party_role,
                    already_approved=already_approved,
                    contract_status=contract_status,
                )
        except (
            ContractStateConflictError,
            ContractVersionApprovalAccessError,
            ContractVersionConflictError,
            ContractVersionNotFoundError,
        ):
            raise
        except SQLAlchemyError as exc:
            logger.exception("contract version approval persistence failed")
            raise ContractRepositoryUnavailableError from exc

    async def begin_signature_request(
        self,
        *,
        contract_id: UUID,
        contract_version_id: UUID,
        requested_by: UUID,
        idempotency_key: str,
        provider_template_id: str,
        buyer_name: str,
        buyer_email: str,
        seller_name: str,
        seller_email: str,
    ) -> SignatureRequestRecord:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing = await self._session.execute(
                    text(
                        """
                        select id, contract_id, contract_version_id, status::text as status,
                               provider, provider_document_id, provider_status,
                               current_signing_order, completed_at
                        from public.signature_requests
                        where contract_id = :contract_id and idempotency_key = :idempotency_key
                        """
                    ),
                    {"contract_id": contract_id, "idempotency_key": idempotency_key},
                )
                row = existing.mappings().one_or_none()
                if row:
                    record = SignatureRequestRecord(**row)
                    if record.contract_version_id != contract_version_id:
                        raise IdempotencyConflictError
                    return SignatureRequestRecord(**row, reused=True)

                context = await self._lock_approval_context(contract_id, contract_version_id)
                if context is None:
                    raise ContractVersionNotFoundError
                if context.current_version_id != contract_version_id:
                    raise ContractVersionConflictError
                if context.contract_status != "signing":
                    raise ContractStateConflictError
                approvals = await self._list_approvals_in_transaction(contract_version_id)
                if {approval.party_role for approval in approvals} != {"buyer", "seller"}:
                    raise ContractStateConflictError

                created = await self._session.execute(
                    text(
                        """
                        insert into public.signature_requests (
                            contract_id, contract_version_id, status, provider,
                            provider_template_id, idempotency_key, requested_by
                        ) values (
                            :contract_id, :contract_version_id, 'preparing', 'modusign',
                            :provider_template_id, :idempotency_key, :requested_by
                        )
                        returning id, contract_id, contract_version_id, status::text as status,
                                  provider, provider_document_id, provider_status,
                                  current_signing_order, completed_at, signed_document_id,
                                  audit_trail_document_id
                        """
                    ),
                    {
                        "contract_id": contract_id,
                        "contract_version_id": contract_version_id,
                        "provider_template_id": provider_template_id,
                        "idempotency_key": idempotency_key,
                        "requested_by": requested_by,
                    },
                )
                request = SignatureRequestRecord(**created.mappings().one())
                await self._session.execute(
                    text(
                        """
                        insert into public.signature_participants (
                            signature_request_id, party_role, provider_role_name,
                            signing_order, name_snapshot, email_snapshot
                        ) values
                            (:request_id, 'buyer', '바이어', 1, :buyer_name, :buyer_email),
                            (:request_id, 'seller', '셀러', 2, :seller_name, :seller_email)
                        """
                    ),
                    {
                        "request_id": request.id,
                        "buyer_name": buyer_name,
                        "buyer_email": buyer_email,
                        "seller_name": seller_name,
                        "seller_email": seller_email,
                    },
                )
                return request
        except (
            ContractStateConflictError,
            ContractVersionConflictError,
            ContractVersionNotFoundError,
            IdempotencyConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def mark_signature_request_dispatched(
        self, signature_request_id: UUID, provider_document_id: str, provider_status: str
    ) -> SignatureRequestRecord:
        try:
            async with self._session.begin():
                result = await self._session.execute(
                    text(
                        """
                        update public.signature_requests
                        set status = 'in_progress', provider_document_id = :provider_document_id,
                            provider_status = :provider_status, current_signing_order = 1
                        where id = :id and status = 'preparing'
                        returning id, contract_id, contract_version_id, status::text as status,
                                  provider, provider_document_id, provider_status,
                                  current_signing_order, completed_at
                        """
                    ),
                    {
                        "id": signature_request_id,
                        "provider_document_id": provider_document_id,
                        "provider_status": provider_status,
                    },
                )
                row = result.mappings().one_or_none()
                if row is None:
                    raise ContractStateConflictError
                return SignatureRequestRecord(**row)
        except ContractStateConflictError:
            raise
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def mark_signature_request_failed(self, signature_request_id: UUID) -> None:
        try:
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        update public.signature_requests
                        set status = 'failed', failed_at = timezone('utc', now())
                        where id = :id and status = 'preparing'
                        """
                    ),
                    {"id": signature_request_id},
                )
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def get_signature_request(
        self, signature_request_id: UUID
    ) -> SignatureRequestRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, contract_id, contract_version_id, status::text as status,
                           provider, provider_document_id, provider_status,
                           current_signing_order, completed_at, signed_document_id,
                           audit_trail_document_id
                    from public.signature_requests where id = :id
                    """
                ),
                {"id": signature_request_id},
            )
            row = result.mappings().one_or_none()
            return SignatureRequestRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def get_signature_request_by_provider_document_id(
        self, provider_document_id: str
    ) -> SignatureRequestRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, contract_id, contract_version_id, status::text as status,
                           provider, provider_document_id, provider_status,
                           current_signing_order, completed_at, signed_document_id,
                           audit_trail_document_id
                    from public.signature_requests
                    where provider_document_id = :provider_document_id
                    """
                ),
                {"provider_document_id": provider_document_id},
            )
            row = result.mappings().one_or_none()
            return SignatureRequestRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def update_signature_request_status(
        self,
        signature_request_id: UUID,
        *,
        provider_status: str,
        current_signing_order: int | None,
    ) -> SignatureRequestRecord:
        try:
            async with self._session.begin():
                result = await self._session.execute(
                    text(
                        """
                        update public.signature_requests
                        set provider_status = :provider_status,
                            current_signing_order = :current_signing_order
                        where id = :id
                        returning id, contract_id, contract_version_id, status::text as status,
                                  provider, provider_document_id, provider_status,
                                  current_signing_order, completed_at, signed_document_id,
                                  audit_trail_document_id
                        """
                    ),
                    {
                        "id": signature_request_id,
                        "provider_status": provider_status,
                        "current_signing_order": current_signing_order,
                    },
                )
                row = result.mappings().one_or_none()
                if row is None:
                    raise ContractVersionNotFoundError
                return SignatureRequestRecord(**row)
        except ContractVersionNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def complete_signature_request(
        self,
        signature_request_id: UUID,
        *,
        signed_size_bytes: int,
        signed_sha256: str,
        audit_size_bytes: int,
        audit_sha256: str,
    ) -> SignatureRequestRecord:
        try:
            async with self._session.begin():
                result = await self._session.execute(
                    text(
                        """
                        select id, contract_id, contract_version_id, requested_by,
                               status::text as status, provider, provider_document_id,
                               provider_status, current_signing_order, completed_at
                        from public.signature_requests where id = :id for update
                        """
                    ),
                    {"id": signature_request_id},
                )
                row = result.mappings().one_or_none()
                if row is None:
                    raise ContractVersionNotFoundError
                row_data = dict(row)
                requested_by = row_data.pop("requested_by")
                record = SignatureRequestRecord(**row_data)
                if record.status == "completed":
                    return record
                if record.status != "in_progress":
                    raise ContractStateConflictError
                base_path = f"contracts/{record.contract_id}/signatures/{record.id}"
                signed_document_id = uuid4()
                audit_document_id = uuid4()
                await self._session.execute(
                    text(
                        """
                        insert into public.documents (
                            id, contract_id, contract_version_id, purpose, status,
                            storage_bucket, storage_object_path, original_filename,
                            mime_type, size_bytes, content_sha256, uploaded_by
                        ) values
                            (:signed_id, :contract_id, :version_id, 'signed_contract', 'ready',
                             'contract-documents', :signed_path, 'signed-contract.pdf',
                             'application/pdf', :signed_size, :signed_sha, :requested_by),
                            (:audit_id, :contract_id, :version_id, 'audit_trail', 'ready',
                             'contract-documents', :audit_path, 'audit-trail.pdf',
                             'application/pdf', :audit_size, :audit_sha, :requested_by)
                        """
                    ),
                    {
                        "signed_id": signed_document_id,
                        "audit_id": audit_document_id,
                        "contract_id": record.contract_id,
                        "version_id": record.contract_version_id,
                        "signed_path": f"{base_path}/signed.pdf",
                        "audit_path": f"{base_path}/audit-trail.pdf",
                        "signed_size": signed_size_bytes,
                        "signed_sha": signed_sha256,
                        "audit_size": audit_size_bytes,
                        "audit_sha": audit_sha256,
                        "requested_by": requested_by,
                    },
                )
                updated = await self._session.execute(
                    text(
                        """
                        update public.signature_requests
                        set status = 'completed', provider_status = 'COMPLETED',
                            signed_document_id = :signed_id, audit_trail_document_id = :audit_id,
                            completed_at = timezone('utc', now())
                        where id = :id
                        returning id, contract_id, contract_version_id, status::text as status,
                                  provider, provider_document_id, provider_status,
                                  current_signing_order, completed_at
                        """
                    ),
                    {
                        "id": record.id,
                        "signed_id": signed_document_id,
                        "audit_id": audit_document_id,
                    },
                )
                await self._session.execute(
                    text(
                        """
                        update public.contracts set status = 'signed'
                        where id = :contract_id and current_version_id = :version_id
                          and status = 'signing'
                        """
                    ),
                    {"contract_id": record.contract_id, "version_id": record.contract_version_id},
                )
                return SignatureRequestRecord(**updated.mappings().one())
        except (ContractVersionNotFoundError, ContractStateConflictError):
            raise
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc

    async def _notify_contract_approval_counterparty(
        self,
        *,
        contract_id: UUID,
        contract_version_id: UUID,
        buyer_user_id: UUID,
        seller_organization_id: UUID,
        approved_role: str,
    ) -> None:
        if approved_role == "buyer":
            await self._session.execute(
                text(
                    """
                    insert into public.notifications (
                        user_id, notification_type, title, body,
                        resource_type, resource_id, dedupe_key
                    )
                    select om.user_id, 'final_approval_requested', '최종안 승인 요청',
                           '바이어가 최종 계약안을 승인했습니다. 같은 버전을 확인해 주세요.',
                           'contract', :contract_id,
                           'final-approval:' || :version_id || ':seller'
                    from public.organization_members om
                    where om.organization_id = :organization_id
                    on conflict (user_id, dedupe_key)
                        where dedupe_key is not null
                    do nothing
                    """
                ),
                {
                    "contract_id": contract_id,
                    "version_id": str(contract_version_id),
                    "organization_id": seller_organization_id,
                },
            )
            return
        await self._session.execute(
            text(
                """
                insert into public.notifications (
                    user_id, notification_type, title, body,
                    resource_type, resource_id, dedupe_key
                ) values (
                    :buyer_user_id, 'final_approval_requested', '최종안 승인 요청',
                    '셀러가 최종 계약안을 승인했습니다. 같은 버전을 확인해 주세요.',
                    'contract', :contract_id,
                    'final-approval:' || :version_id || ':buyer'
                )
                on conflict (user_id, dedupe_key)
                    where dedupe_key is not null
                do nothing
                """
            ),
            {
                "buyer_user_id": buyer_user_id,
                "contract_id": contract_id,
                "version_id": str(contract_version_id),
            },
        )

    async def _lock_approval_context(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> ContractVersionApprovalContextRecord | None:
        result = await self._session.execute(
            text(
                """
                select c.id as contract_id, cv.id as contract_version_id, cv.version_no,
                       c.buyer_user_id, c.seller_organization_id,
                       c.status::text as contract_status, c.current_version_id
                from public.contracts c
                join public.contract_versions cv on cv.contract_id = c.id
                where c.id = :contract_id and cv.id = :contract_version_id
                for update of c
                """
            ),
            {"contract_id": contract_id, "contract_version_id": contract_version_id},
        )
        row = result.mappings().one_or_none()
        return ContractVersionApprovalContextRecord(**row) if row else None

    async def _is_member_in_transaction(self, user_id: UUID, organization_id: UUID) -> bool:
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

    async def _list_approvals_in_transaction(
        self, contract_version_id: UUID
    ) -> list[ContractVersionApprovalRecord]:
        result = await self._session.execute(
            text(
                """
                select id, contract_version_id, party_role::text as party_role,
                       approved_by_user_id, approved_at
                from public.contract_version_approvals
                where contract_version_id = :contract_version_id
                order by party_role
                """
            ),
            {"contract_version_id": contract_version_id},
        )
        return [ContractVersionApprovalRecord(**row) for row in result.mappings().all()]

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
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
        return bool(result.scalar_one())

    async def cancel_contract(
        self,
        *,
        contract_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[datetime, bool]:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing = await self._claim_idempotency(
                    actor_user_id, self._OPERATION_CANCEL, idempotency_key, request_hash
                )
                if existing is not None:
                    record = await self._session.execute(
                        text("select cancelled_at from public.contracts where id = :id"),
                        {"id": contract_id},
                    )
                    return record.scalar_one(), True
                result = await self._session.execute(
                    text(
                        """
                        update public.contracts
                        set status = 'cancelled', cancelled_at = now()
                        where id = :contract_id
                          and status in ('draft', 'seller_review', 'revision_requested')
                        returning cancelled_at
                        """
                    ),
                    {"contract_id": contract_id},
                )
                cancelled_at = result.scalar_one_or_none()
                if cancelled_at is None:
                    raise ContractStateConflictError
                await self._session.execute(
                    text(
                        """
                        update public.revision_requests
                        set status = 'cancelled'
                        where contract_id = :contract_id
                          and status in ('draft', 'sent', 'countered')
                        """
                    ),
                    {"contract_id": contract_id},
                )
                await self._session.execute(
                    text(
                        """
                        insert into public.audit_events (
                            contract_id, actor_user_id, actor_role, event_type,
                            target_type, target_id
                        ) values (
                            :contract_id, :actor_user_id, :actor_role,
                            'contract_cancelled', 'contract', :contract_id
                        )
                        """
                    ),
                    {
                        "contract_id": contract_id,
                        "actor_user_id": actor_user_id,
                        "actor_role": actor_role,
                    },
                )
                await self._complete_idempotency(
                    actor_user_id,
                    self._OPERATION_CANCEL,
                    idempotency_key,
                    contract_id,
                    {"contract_id": str(contract_id), "status": "cancelled", "version_no": 1},
                )
                return cancelled_at, False
        except (IdempotencyConflictError, ContractStateConflictError):
            raise
        except SQLAlchemyError as exc:
            raise ContractRepositoryUnavailableError from exc
