from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


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

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...

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
                       id, structured_data, :buyer_user_id
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
                          'signature_requested', 'signature_completed', 'contract_cancelled'
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
