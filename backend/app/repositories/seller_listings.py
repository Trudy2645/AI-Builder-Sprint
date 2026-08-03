from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SellerListingMembershipRecord:
    organization_id: UUID
    organization_type: str
    verification_status: str
    role: str


@dataclass(frozen=True, slots=True)
class SellerListingClauseRecord:
    id: UUID
    clause_order: int
    clause_key: str | None
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class NewSellerListingClause:
    clause_key: str | None
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class SellerListingRecord:
    id: UUID
    seller_organization_id: UUID
    organization_name: str
    verification_status: str
    title: str
    display_title: str | None
    display_company_name: str | None
    district: str
    category: str
    language: str
    status: str
    creation_method: str
    seller_description: str | None
    public_headline: str | None
    ai_summary: str | None
    hero_document_id: UUID | None
    current_version_id: UUID
    current_version_no: int
    current_version_title: str
    current_version_body: str
    current_version_created_at: datetime
    contract_request_count: int
    contract_count: int
    attention_required_count: int
    service_start_date: date | None
    service_end_date: date | None
    supply_quantity: int | None
    supply_quantity_description: str | None
    quantity_unit: str | None
    minimum_quantity: int | None
    maximum_quantity: int | None
    people_per_unit: int | None
    base_price_amount_minor: int | None
    currency: str | None
    price_unit: str | None
    minimum_people: int | None
    maximum_people: int | None
    cancellation_policy: str | None
    no_show_policy: str | None
    refund_policy: str | None
    settlement_policy: str | None
    safety_policy: str | None
    compensation_policy: str | None
    liability_policy: str | None
    termination_policy: str | None
    special_terms: str | None
    price_display_basis: str | None
    contract_availability_note: str | None
    published_at: datetime | None
    paused_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SellerListingCreatedRecord:
    listing_id: UUID
    status: str
    version_no: int


class SellerListingRepositoryError(Exception):
    pass


class SellerListingNotFoundError(Exception):
    pass


class SellerListingVersionConflictError(Exception):
    pass


class SellerListingStateConflictError(Exception):
    pass


class SellerListingHasContractsError(Exception):
    pass


class SellerListingDocumentAccessError(Exception):
    pass


class SellerListingIdempotencyConflictError(Exception):
    pass


class SellerListingRepository(Protocol):
    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> SellerListingMembershipRecord | None: ...

    async def list_seller_listings(self, organization_id: UUID) -> list[SellerListingRecord]: ...

    async def get_seller_listing(self, listing_id: UUID) -> SellerListingRecord | None: ...

    async def list_listing_clauses(
        self, listing_version_id: UUID
    ) -> list[SellerListingClauseRecord]: ...

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
    ) -> SellerListingCreatedRecord: ...

    async def update_listing_terms(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        changes: dict[str, Any],
        structured_data: dict[str, Any],
        body: str,
        clauses: list[NewSellerListingClause],
    ) -> SellerListingRecord: ...

    async def update_listing_presentation(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        listing_changes: dict[str, Any],
        term_changes: dict[str, Any],
    ) -> SellerListingRecord: ...

    async def complete_listing(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        expected_version_id: UUID,
    ) -> SellerListingRecord: ...

    async def transition_listing(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        target_status: str,
    ) -> SellerListingRecord: ...


class SqlAlchemySellerListingRepository:
    _CREATE_OPERATION = "seller_listing_create"
    _TERM_COLUMNS = {
        "service_start_date",
        "service_end_date",
        "supply_quantity",
        "supply_quantity_description",
        "quantity_unit",
        "minimum_quantity",
        "maximum_quantity",
        "people_per_unit",
        "base_price_amount_minor",
        "currency",
        "price_unit",
        "minimum_people",
        "maximum_people",
        "cancellation_policy",
        "no_show_policy",
        "refund_policy",
        "settlement_policy",
        "safety_policy",
        "compensation_policy",
        "liability_policy",
        "termination_policy",
        "special_terms",
        "price_display_basis",
        "contract_availability_note",
    }
    _PRESENTATION_COLUMNS = {
        "display_company_name",
        "display_title",
        "hero_document_id",
        "seller_description",
        "public_headline",
    }
    _SELECT = """
        select l.id, l.seller_organization_id, o.name as organization_name,
               o.verification_status::text as verification_status, l.title,
               l.display_title, l.display_company_name, l.district,
               l.category::text as category, l.language::text as language,
               l.status::text as status, l.creation_method::text as creation_method,
               l.seller_description, l.public_headline, l.ai_summary, l.hero_document_id,
               l.current_version_id, lv.version_no as current_version_no,
               lv.title as current_version_title, lv.body as current_version_body,
               lv.created_at as current_version_created_at,
               l.contract_request_count::integer,
               (select count(*)::integer from public.contracts c where c.listing_id = l.id)
                   as contract_count,
               coalesce((
                   select count(distinct finding.listing_clause_id)
                   from public.ai_findings finding
                   where finding.analysis_run_id = (
                       select run.id
                       from public.ai_analysis_runs run
                       where run.listing_version_id = l.current_version_id
                         and run.viewer_role = 'seller'
                         and run.status = 'succeeded'
                       order by run.completed_at desc nulls last, run.created_at desc
                       limit 1
                   )
                     and finding.status = 'open'
                     and finding.listing_clause_id is not null
               ), 0)::integer as attention_required_count,
               lt.service_start_date, lt.service_end_date, lt.supply_quantity,
               lt.supply_quantity_description, lt.quantity_unit,
               lt.minimum_quantity, lt.maximum_quantity,
               lt.people_per_unit, lt.base_price_amount_minor,
               lt.currency, lt.price_unit, lt.minimum_people, lt.maximum_people,
               lt.cancellation_policy, lt.no_show_policy, lt.refund_policy,
               lt.settlement_policy, lt.safety_policy, lt.compensation_policy,
               lt.liability_policy, lt.termination_policy, lt.special_terms,
               lt.price_display_basis, lt.contract_availability_note,
               l.published_at, l.paused_at, l.created_at, l.updated_at
        from public.listings l
        join public.organizations o on o.id = l.seller_organization_id
        join public.listing_terms lt on lt.listing_id = l.id
        join public.listing_versions lv on lv.id = l.current_version_id
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> SellerListingMembershipRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.organization_type::text,
                           o.verification_status::text, om.role::text
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id and om.organization_id = :organization_id
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            row = result.mappings().one_or_none()
            return SellerListingMembershipRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def list_seller_listings(self, organization_id: UUID) -> list[SellerListingRecord]:
        try:
            result = await self._session.execute(
                text(
                    self._SELECT
                    + """
                    where l.seller_organization_id = :organization_id
                    order by l.updated_at desc, l.id
                    """
                ),
                {"organization_id": organization_id},
            )
            return [SellerListingRecord(**row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def get_seller_listing(self, listing_id: UUID) -> SellerListingRecord | None:
        try:
            result = await self._session.execute(
                text(self._SELECT + " where l.id = :listing_id"),
                {"listing_id": listing_id},
            )
            row = result.mappings().one_or_none()
            return SellerListingRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def list_listing_clauses(
        self, listing_version_id: UUID
    ) -> list[SellerListingClauseRecord]:
        try:
            return await self._list_clauses(listing_version_id)
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

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
        listing_id = uuid4()
        version_id = uuid4()
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing = await self._claim_create_idempotency(
                    organization_id, idempotency_key, request_hash
                )
                if existing is not None:
                    return existing
                await self._session.execute(
                    text(
                        """
                        insert into public.listings (
                            id, seller_organization_id, creation_method, title,
                            district, category, language, created_by
                        ) values (
                            :id, :organization_id,
                            cast(:creation_method as public.listing_creation_method),
                            :title, :district, cast(:category as public.contract_category),
                            cast(:language as public.supported_locale), :actor_user_id
                        )
                        """
                    ),
                    {
                        "id": listing_id,
                        "organization_id": organization_id,
                        "creation_method": creation_method,
                        "title": title,
                        "district": district,
                        "category": category,
                        "language": language,
                        "actor_user_id": actor_user_id,
                    },
                )
                await self._session.execute(
                    text("insert into public.listing_terms (listing_id) values (:listing_id)"),
                    {"listing_id": listing_id},
                )
                await self._session.execute(
                    text(
                        """
                        insert into public.listing_versions (
                            id, listing_id, version_no, title, body, content_sha256,
                            structured_data, created_by
                        ) values (
                            :version_id, :listing_id, 1, :title, '',
                            encode(digest('', 'sha256'), 'hex'), '{}'::jsonb, :actor_user_id
                        )
                        """
                    ),
                    {
                        "version_id": version_id,
                        "listing_id": listing_id,
                        "title": title,
                        "actor_user_id": actor_user_id,
                    },
                )
                await self._session.execute(
                    text(
                        "update public.listings set current_version_id = :version_id where id = :id"
                    ),
                    {"version_id": version_id, "id": listing_id},
                )
                await self._insert_audit_event(
                    listing_id, actor_user_id, "listing_created", version_id, {"version_no": 1}
                )
                await self._complete_create_idempotency(
                    organization_id, idempotency_key, listing_id
                )
            return SellerListingCreatedRecord(listing_id, "draft", 1)
        except SellerListingIdempotencyConflictError:
            raise
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def update_listing_terms(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        changes: dict[str, Any],
        structured_data: dict[str, Any],
        body: str,
        clauses: list[NewSellerListingClause],
    ) -> SellerListingRecord:
        safe_changes = {key: value for key, value in changes.items() if key in self._TERM_COLUMNS}
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                row = await self._lock_listing(listing_id, organization_id)
                self._require_listing(row)
                if row["current_version_no"] != base_version_no:
                    raise SellerListingVersionConflictError
                if row["status"] not in {"draft", "ready", "published", "paused"}:
                    raise SellerListingStateConflictError
                if await self._has_contracts(listing_id):
                    raise SellerListingHasContractsError
                if safe_changes:
                    assignments = ", ".join(f"{key} = :{key}" for key in safe_changes)
                    await self._session.execute(
                        text(
                            f"update public.listing_terms set {assignments} "
                            "where listing_id = :listing_id"  # noqa: S608
                        ),
                        {"listing_id": listing_id, **safe_changes},
                    )
                version_no = base_version_no + 1
                version_id = uuid4()
                await self._session.execute(
                    text(
                        """
                        insert into public.listing_versions (
                            id, listing_id, version_no, title, body, content_sha256,
                            structured_data, created_by
                        ) values (
                            :version_id, :listing_id, :version_no, :title, :body,
                            encode(digest(:body, 'sha256'), 'hex'),
                            cast(:structured_data as jsonb), :actor_user_id
                        )
                        """
                    ),
                    {
                        "version_id": version_id,
                        "listing_id": listing_id,
                        "version_no": version_no,
                        "title": row["title"],
                        "body": body,
                        "structured_data": json.dumps(structured_data, default=str),
                        "actor_user_id": actor_user_id,
                    },
                )
                for clause_order, clause in enumerate(clauses, start=1):
                    await self._session.execute(
                        text(
                            """
                            insert into public.listing_clauses (
                                listing_version_id, clause_order, clause_key, title, body
                            ) values (
                                :version_id, :clause_order, :clause_key, :title, :body
                            )
                            """
                        ),
                        {
                            "version_id": version_id,
                            "clause_order": clause_order,
                            "clause_key": clause.clause_key,
                            "title": clause.title,
                            "body": clause.body,
                        },
                    )
                await self._session.execute(
                    text(
                        """
                        update public.listings
                        set current_version_id = :version_id,
                            status = case when status = 'ready' then 'draft' else status end
                        where id = :listing_id
                        """
                    ),
                    {"version_id": version_id, "listing_id": listing_id},
                )
                await self._insert_audit_event(
                    listing_id,
                    actor_user_id,
                    "listing_terms_updated",
                    version_id,
                    {"version_no": version_no},
                )
            record = await self.get_seller_listing(listing_id)
            if record is None:
                raise SellerListingNotFoundError
            return record
        except (
            SellerListingHasContractsError,
            SellerListingNotFoundError,
            SellerListingStateConflictError,
            SellerListingVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def update_listing_presentation(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        listing_changes: dict[str, Any],
        term_changes: dict[str, Any],
    ) -> SellerListingRecord:
        safe_listing = {
            key: value
            for key, value in listing_changes.items()
            if key in self._PRESENTATION_COLUMNS
        }
        safe_terms = {
            key: value
            for key, value in term_changes.items()
            if key in {"price_display_basis", "contract_availability_note"}
        }
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                row = await self._lock_listing(listing_id, organization_id)
                self._require_listing(row)
                if row["status"] not in {"draft", "ready", "published", "paused"}:
                    raise SellerListingStateConflictError
                hero_document_id = safe_listing.get("hero_document_id")
                if hero_document_id is not None:
                    valid_document = await self._session.execute(
                        text(
                            """
                            select exists (
                                select 1 from public.documents
                                where id = :document_id and listing_id = :listing_id
                                  and purpose in ('listing_hero', 'source_contract')
                                  and status = 'ready'
                            )
                            """
                        ),
                        {"document_id": hero_document_id, "listing_id": listing_id},
                    )
                    if not valid_document.scalar_one():
                        raise SellerListingDocumentAccessError
                if safe_listing:
                    assignments = ", ".join(f"{key} = :{key}" for key in safe_listing)
                    await self._session.execute(
                        text(
                            f"update public.listings set {assignments} where id = :listing_id"  # noqa: S608
                        ),
                        {"listing_id": listing_id, **safe_listing},
                    )
                if safe_terms:
                    assignments = ", ".join(f"{key} = :{key}" for key in safe_terms)
                    await self._session.execute(
                        text(
                            f"update public.listing_terms set {assignments} "
                            "where listing_id = :listing_id"  # noqa: S608
                        ),
                        {"listing_id": listing_id, **safe_terms},
                    )
                if safe_listing or safe_terms:
                    await self._insert_audit_event(
                        listing_id,
                        actor_user_id,
                        "listing_presentation_updated",
                        row["current_version_id"],
                        {},
                    )
            record = await self.get_seller_listing(listing_id)
            if record is None:
                raise SellerListingNotFoundError
            return record
        except (
            SellerListingDocumentAccessError,
            SellerListingNotFoundError,
            SellerListingStateConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def complete_listing(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        expected_version_id: UUID,
    ) -> SellerListingRecord:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                row = await self._lock_listing(listing_id, organization_id)
                self._require_listing(row)
                if row["current_version_id"] != expected_version_id:
                    raise SellerListingVersionConflictError
                if row["status"] == "ready":
                    pass
                elif row["status"] == "draft":
                    await self._session.execute(
                        text("update public.listings set status = 'processing' where id = :id"),
                        {"id": listing_id},
                    )
                    await self._session.execute(
                        text("update public.listings set status = 'ready' where id = :id"),
                        {"id": listing_id},
                    )
                    await self._insert_audit_event(
                        listing_id,
                        actor_user_id,
                        "listing_completed",
                        expected_version_id,
                        {"transitions": ["draft", "processing", "ready"]},
                    )
                else:
                    raise SellerListingStateConflictError
            record = await self.get_seller_listing(listing_id)
            if record is None:
                raise SellerListingNotFoundError
            return record
        except (
            SellerListingNotFoundError,
            SellerListingStateConflictError,
            SellerListingVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def transition_listing(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        target_status: str,
    ) -> SellerListingRecord:
        allowed_sources = {
            "published": {"ready", "paused", "published"},
            "paused": {"published", "paused"},
            "archived": {"draft", "ready", "paused", "archived"},
        }
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                row = await self._lock_listing(listing_id, organization_id)
                self._require_listing(row)
                if (
                    target_status not in allowed_sources
                    or row["status"] not in allowed_sources[target_status]
                ):
                    raise SellerListingStateConflictError
                changed = row["status"] != target_status
                if changed:
                    if target_status == "published":
                        await self._session.execute(
                            text(
                                """
                                update public.listings
                                set status = 'published',
                                    published_at = coalesce(published_at, now()),
                                    paused_at = null
                                where id = :id
                                """
                            ),
                            {"id": listing_id},
                        )
                    elif target_status == "paused":
                        await self._session.execute(
                            text(
                                """
                                update public.listings
                                set status = 'paused', paused_at = now()
                                where id = :id
                                """
                            ),
                            {"id": listing_id},
                        )
                    else:
                        await self._session.execute(
                            text("update public.listings set status = 'archived' where id = :id"),
                            {"id": listing_id},
                        )
                    await self._insert_audit_event(
                        listing_id,
                        actor_user_id,
                        f"listing_{target_status}",
                        row["current_version_id"],
                        {"from_status": row["status"], "to_status": target_status},
                    )
            record = await self.get_seller_listing(listing_id)
            if record is None:
                raise SellerListingNotFoundError
            return record
        except (SellerListingNotFoundError, SellerListingStateConflictError):
            raise
        except SQLAlchemyError as exc:
            raise SellerListingRepositoryError from exc

    async def _lock_listing(self, listing_id: UUID, organization_id: UUID):
        result = await self._session.execute(
            text(
                """
                select l.id, l.seller_organization_id, l.status::text as status, l.title,
                       l.current_version_id, lv.version_no as current_version_no,
                       o.verification_status::text as verification_status
                from public.listings l
                join public.organizations o on o.id = l.seller_organization_id
                join public.listing_versions lv on lv.id = l.current_version_id
                where l.id = :listing_id and l.seller_organization_id = :organization_id
                for update of l
                """
            ),
            {"listing_id": listing_id, "organization_id": organization_id},
        )
        return result.mappings().one_or_none()

    @staticmethod
    def _require_listing(row) -> None:
        if row is None:
            raise SellerListingNotFoundError

    async def _has_contracts(self, listing_id: UUID) -> bool:
        result = await self._session.execute(
            text("select exists (select 1 from public.contracts where listing_id = :id)"),
            {"id": listing_id},
        )
        return bool(result.scalar_one())

    async def _list_clauses(self, listing_version_id: UUID) -> list[SellerListingClauseRecord]:
        result = await self._session.execute(
            text(
                """
                select id, clause_order, clause_key, title, body
                from public.listing_clauses
                where listing_version_id = :version_id
                order by clause_order
                """
            ),
            {"version_id": listing_version_id},
        )
        return [SellerListingClauseRecord(**row) for row in result.mappings().all()]

    async def _claim_create_idempotency(
        self, organization_id: UUID, key: str, request_hash: str
    ) -> SellerListingCreatedRecord | None:
        await self._session.execute(
            text(
                """
                delete from public.idempotency_records
                where organization_id = :organization_id and operation = :operation
                  and idempotency_key = :key and expires_at <= now()
                """
            ),
            {
                "organization_id": organization_id,
                "operation": self._CREATE_OPERATION,
                "key": key,
            },
        )
        inserted = await self._session.execute(
            text(
                """
                insert into public.idempotency_records (
                    organization_id, operation, idempotency_key, request_hash, expires_at
                ) values (
                    :organization_id, :operation, :key, :request_hash,
                    now() + interval '24 hours'
                )
                on conflict (organization_id, operation, idempotency_key)
                    where organization_id is not null
                do nothing
                returning id
                """
            ),
            {
                "organization_id": organization_id,
                "operation": self._CREATE_OPERATION,
                "key": key,
                "request_hash": request_hash,
            },
        )
        if inserted.scalar_one_or_none() is not None:
            return None
        existing = await self._session.execute(
            text(
                """
                select request_hash, resource_id, response_body
                from public.idempotency_records
                where organization_id = :organization_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {
                "organization_id": organization_id,
                "operation": self._CREATE_OPERATION,
                "key": key,
            },
        )
        row = existing.mappings().one()
        if row["request_hash"] != request_hash or row["response_body"] is None:
            raise SellerListingIdempotencyConflictError
        return SellerListingCreatedRecord(
            listing_id=row["resource_id"],
            status=row["response_body"]["status"],
            version_no=row["response_body"]["version_no"],
        )

    async def _complete_create_idempotency(
        self, organization_id: UUID, key: str, listing_id: UUID
    ) -> None:
        await self._session.execute(
            text(
                """
                update public.idempotency_records
                set response_status = 201,
                    response_body = jsonb_build_object('status', 'draft', 'version_no', 1),
                    resource_type = 'listing', resource_id = :listing_id
                where organization_id = :organization_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {
                "listing_id": listing_id,
                "organization_id": organization_id,
                "operation": self._CREATE_OPERATION,
                "key": key,
            },
        )

    async def _insert_audit_event(
        self,
        listing_id: UUID,
        actor_user_id: UUID,
        event_type: str,
        target_id: UUID,
        event_data: dict[str, Any],
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.audit_events (
                    listing_id, actor_user_id, actor_role, event_type,
                    target_type, target_id, event_data
                ) values (
                    :listing_id, :actor_user_id, 'seller', :event_type,
                    'listing_version', :target_id, cast(:event_data as jsonb)
                )
                """
            ),
            {
                "listing_id": listing_id,
                "actor_user_id": actor_user_id,
                "event_type": event_type,
                "target_id": target_id,
                "event_data": json.dumps(event_data),
            },
        )
