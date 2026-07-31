from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.listings import ListingCategory, PublicListingSort


@dataclass(frozen=True, slots=True)
class ListingSearchFilters:
    q: str | None
    contract_available_only: bool
    districts: tuple[str, ...]
    people: int | None
    min_price: int | None
    max_price: int | None
    currency: str | None
    category: ListingCategory | None
    start_date: date | None
    end_date: date | None
    sort: PublicListingSort


@dataclass(frozen=True, slots=True)
class ListingCursor:
    value: str
    listing_id: UUID


@dataclass(frozen=True, slots=True)
class PublicListingRecord:
    id: UUID
    title: str
    district: str
    category: str
    language: str
    ai_summary: str | None
    status: str
    seller_name: str
    verification_status: str
    rating_average: Decimal
    rating_count: int
    service_start_date: date | None
    service_end_date: date | None
    supply_quantity: int | None
    quantity_unit: str | None
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
    attention_required_count: int
    current_version_id: UUID | None
    sort_value: Decimal | int | datetime


@dataclass(frozen=True, slots=True)
class PublicListingVersionRecord:
    id: UUID
    body: str


@dataclass(frozen=True, slots=True)
class PublicClauseRecord:
    id: UUID
    clause_key: str | None
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class PublicFindingRecord:
    clause_id: UUID | None
    severity: str
    explanation: str
    suggested_text: str | None
    disclaimer: str


class ListingRepositoryUnavailableError(Exception):
    pass


class PublicListingRepository(Protocol):
    async def search_public_listings(
        self,
        filters: ListingSearchFilters,
        cursor: ListingCursor | None,
        limit: int,
    ) -> list[PublicListingRecord]: ...

    async def get_public_listing(self, listing_id: UUID) -> PublicListingRecord | None: ...

    async def get_public_version(
        self, listing_id: UUID, version_id: UUID
    ) -> PublicListingVersionRecord | None: ...

    async def list_public_clauses(self, version_id: UUID) -> list[PublicClauseRecord]: ...

    async def list_public_findings(self, version_id: UUID) -> list[PublicFindingRecord]: ...


class SqlAlchemyPublicListingRepository:
    _RECOMMENDED_SCORE = """
        (case when o.verification_status = 'verified' then 1000000 else 0 end)
        + (case when l.status = 'published' then 100000 else 0 end)
        + (case when l.current_version_id is not null then 10000 else 0 end)
        + (case when l.ai_summary is not null then 1000 else 0 end)
        + coalesce(l.popularity_score, 0)
    """
    _SORTS = {
        PublicListingSort.RECOMMENDED: (_RECOMMENDED_SCORE, "desc", "numeric"),
        PublicListingSort.POPULAR: ("coalesce(l.popularity_score, 0)", "desc", "numeric"),
        PublicListingSort.LATEST: (
            "coalesce(l.published_at, l.created_at)",
            "desc",
            "timestamptz",
        ),
        PublicListingSort.PRICE_ASC: (
            "coalesce(lt.base_price_amount_minor, 9223372036854775807)",
            "asc",
            "bigint",
        ),
        PublicListingSort.PRICE_DESC: (
            "coalesce(lt.base_price_amount_minor, -1)",
            "desc",
            "bigint",
        ),
    }
    _ATTENTION_REQUIRED_COUNT = """
        coalesce((
            select count(distinct af.listing_clause_id)
            from public.ai_findings af
            where af.analysis_run_id = (
                select ar.id
                from public.ai_analysis_runs ar
                where ar.listing_version_id = l.current_version_id
                  and ar.viewer_role = 'buyer'
                  and ar.status = 'succeeded'
                order by ar.completed_at desc nulls last, ar.created_at desc
                limit 1
            )
              and af.status in ('open', 'applied')
              and af.listing_clause_id is not null
        ), 0)::integer
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_public_listings(
        self,
        filters: ListingSearchFilters,
        cursor: ListingCursor | None,
        limit: int,
    ) -> list[PublicListingRecord]:
        sort_expression, direction, cursor_type = self._SORTS[filters.sort]
        conditions = [
            "l.status in ('published', 'paused')",
            "(l.expires_at is null or l.expires_at >= now())",
            "(lt.service_end_date is null or lt.service_end_date >= current_date)",
        ]
        params: dict[str, object] = {"limit": limit}

        if filters.contract_available_only:
            conditions.append("l.status = 'published'")
        if filters.q:
            conditions.append(
                """position(lower(:q) in lower(
                    coalesce(l.display_title, l.title) || ' ' ||
                    coalesce(l.display_company_name, o.name)
                )) > 0"""
            )
            params["q"] = filters.q
        if filters.districts:
            conditions.append("l.district = any(cast(:districts as text[]))")
            params["districts"] = list(filters.districts)
        if filters.people is not None:
            conditions.extend(
                [
                    "(lt.minimum_people is null or lt.minimum_people <= :people)",
                    "(lt.maximum_people is null or lt.maximum_people >= :people)",
                ]
            )
            params["people"] = filters.people
        if filters.min_price is not None:
            conditions.append("lt.base_price_amount_minor >= :min_price")
            params["min_price"] = filters.min_price
        if filters.max_price is not None:
            conditions.append("lt.base_price_amount_minor <= :max_price")
            params["max_price"] = filters.max_price
        if filters.currency is not None:
            conditions.append("lt.currency = :currency")
            params["currency"] = filters.currency
        if filters.category is not None:
            conditions.append("l.category = cast(:category as public.contract_category)")
            params["category"] = filters.category.value
        if filters.start_date is not None:
            conditions.append(
                "(lt.service_start_date is null or lt.service_start_date <= :start_date)"
            )
            params["start_date"] = filters.start_date
        if filters.end_date is not None:
            conditions.append("(lt.service_end_date is null or lt.service_end_date >= :end_date)")
            params["end_date"] = filters.end_date
        if cursor is not None:
            operator = ">" if direction == "asc" else "<"
            conditions.append(
                f"""(
                    {sort_expression} {operator} cast(:cursor_value as {cursor_type})
                    or (
                        {sort_expression} = cast(:cursor_value as {cursor_type})
                        and l.id {operator} cast(:cursor_id as uuid)
                    )
                )"""
            )
            params.update(cursor_value=cursor.value, cursor_id=cursor.listing_id)

        where_clause = " and ".join(f"({condition})" for condition in conditions)
        query = text(
            f"""
            select l.id, coalesce(l.display_title, l.title) as title, l.district,
                   l.category::text as category, l.language::text as language, l.ai_summary,
                   l.status::text as status,
                   coalesce(l.display_company_name, o.name) as seller_name,
                   o.verification_status::text as verification_status,
                   o.rating_average, o.rating_count,
                   lt.service_start_date, lt.service_end_date, lt.supply_quantity,
                   lt.quantity_unit, lt.people_per_unit, lt.base_price_amount_minor,
                   lt.currency, lt.price_unit,
                   lt.minimum_people, lt.maximum_people,
                   lt.cancellation_policy, lt.no_show_policy, lt.refund_policy,
                   lt.settlement_policy, lt.safety_policy, lt.compensation_policy,
                   lt.liability_policy, lt.termination_policy, lt.special_terms,
                   lt.price_display_basis, lt.contract_availability_note,
                   {self._ATTENTION_REQUIRED_COUNT} as attention_required_count,
                   l.current_version_id,
                   {sort_expression} as sort_value
            from public.listings l
            join public.organizations o on o.id = l.seller_organization_id
            left join public.listing_terms lt on lt.listing_id = l.id
            where {where_clause}
            order by sort_value {direction}, l.id {direction}
            limit :limit
            """  # noqa: S608 - dynamic fragments come only from fixed allowlists
        )
        return await self._listing_records(query, params)

    async def get_public_listing(self, listing_id: UUID) -> PublicListingRecord | None:
        query = text(
            f"""
            select l.id, coalesce(l.display_title, l.title) as title, l.district,
                   l.category::text as category, l.language::text as language, l.ai_summary,
                   l.status::text as status,
                   coalesce(l.display_company_name, o.name) as seller_name,
                   o.verification_status::text as verification_status,
                   o.rating_average, o.rating_count,
                   lt.service_start_date, lt.service_end_date, lt.supply_quantity,
                   lt.quantity_unit, lt.people_per_unit, lt.base_price_amount_minor,
                   lt.currency, lt.price_unit,
                   lt.minimum_people, lt.maximum_people,
                   lt.cancellation_policy, lt.no_show_policy, lt.refund_policy,
                   lt.settlement_policy, lt.safety_policy, lt.compensation_policy,
                   lt.liability_policy, lt.termination_policy, lt.special_terms,
                   lt.price_display_basis, lt.contract_availability_note,
                   {self._ATTENTION_REQUIRED_COUNT} as attention_required_count,
                   l.current_version_id,
                   {self._RECOMMENDED_SCORE} as sort_value
            from public.listings l
            join public.organizations o on o.id = l.seller_organization_id
            left join public.listing_terms lt on lt.listing_id = l.id
            where l.id = :listing_id
              and l.status in ('published', 'paused')
              and (l.expires_at is null or l.expires_at >= now())
              and (lt.service_end_date is null or lt.service_end_date >= current_date)
            """  # noqa: S608 - score is a fixed expression
        )
        records = await self._listing_records(query, {"listing_id": listing_id})
        return records[0] if records else None

    async def get_public_version(
        self, listing_id: UUID, version_id: UUID
    ) -> PublicListingVersionRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, body
                    from public.listing_versions
                    where id = :version_id and listing_id = :listing_id
                    """
                ),
                {"listing_id": listing_id, "version_id": version_id},
            )
        except SQLAlchemyError as exc:
            raise ListingRepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return PublicListingVersionRecord(**row) if row else None

    async def list_public_clauses(self, version_id: UUID) -> list[PublicClauseRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, clause_key, title, body
                    from public.listing_clauses
                    where listing_version_id = :version_id
                    order by clause_order
                    """
                ),
                {"version_id": version_id},
            )
        except SQLAlchemyError as exc:
            raise ListingRepositoryUnavailableError from exc
        return [PublicClauseRecord(**row) for row in result.mappings().all()]

    async def list_public_findings(self, version_id: UUID) -> list[PublicFindingRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    with latest_buyer_analysis as (
                        select id
                        from public.ai_analysis_runs
                        where listing_version_id = :version_id
                          and viewer_role = 'buyer'
                          and status = 'succeeded'
                        order by completed_at desc nulls last, created_at desc
                        limit 1
                    )
                    select af.listing_clause_id as clause_id, af.severity::text as severity,
                           af.explanation, af.suggested_text, af.disclaimer
                    from public.ai_findings af
                    where af.analysis_run_id = (select id from latest_buyer_analysis)
                      and af.status in ('open', 'applied')
                    order by
                        case af.severity
                            when 'high' then 1 when 'medium' then 2
                            when 'low' then 3 else 4
                        end,
                        af.created_at,
                        af.id
                    """
                ),
                {"version_id": version_id},
            )
        except SQLAlchemyError as exc:
            raise ListingRepositoryUnavailableError from exc
        return [PublicFindingRecord(**row) for row in result.mappings().all()]

    async def _listing_records(
        self, query: object, params: dict[str, object]
    ) -> list[PublicListingRecord]:
        try:
            result = await self._session.execute(query, params)
        except SQLAlchemyError as exc:
            raise ListingRepositoryUnavailableError from exc
        return [PublicListingRecord(**row) for row in result.mappings().all()]
