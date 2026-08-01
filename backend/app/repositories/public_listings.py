# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profiles import RepositoryUnavailableError
from app.schemas.public_listings import PublicListingQuery


@dataclass(frozen=True, slots=True)
class PublicListingRecord:
    id: UUID
    status: str
    title: str
    display_title: str | None
    district: str
    category: str
    ai_summary: str | None
    expires_at: date | None
    seller_name: str
    seller_rating: Decimal
    seller_rating_count: int
    seller_verified: bool
    service_start_date: date | None
    service_end_date: date | None
    supply_quantity: int | None
    quantity_unit: str | None
    base_price_amount_minor: int | None
    currency: str | None
    price_unit: str | None
    minimum_people: int | None
    maximum_people: int | None
    cancellation_policy: str | None
    refund_policy: str | None
    settlement_policy: str | None
    safety_policy: str | None
    compensation_policy: str | None
    liability_policy: str | None
    price_display_basis: str | None
    contract_availability_note: str | None
    current_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class ListingPreviewRecord:
    listing_id: UUID
    version_no: int
    title: str
    body: str
    clauses: list[dict[str, object]]


class PublicListingRepository(Protocol):
    async def list(self, query: PublicListingQuery) -> list[PublicListingRecord]: ...

    async def get(self, listing_id: UUID) -> PublicListingRecord | None: ...

    async def get_preview(self, listing_id: UUID) -> ListingPreviewRecord | None: ...


class SqlAlchemyPublicListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, query: PublicListingQuery) -> list[PublicListingRecord]:
        filters = [
            "l.status = 'published'",
            "(l.expires_at is null or l.expires_at >= current_date)",
        ]
        params: dict[str, object] = {"limit": query.limit}
        for field, column in (
            ("category", "l.category"),
            ("district", "l.district"),
            ("currency", "t.currency"),
        ):
            value = getattr(query, field)
            if value is not None:
                filters.append(f"{column} = :{field}")
                params[field] = value
        if query.people is not None:
            filters.append("(t.minimum_people is null or t.minimum_people <= :people)")
            filters.append("(t.maximum_people is null or t.maximum_people >= :people)")
            params["people"] = query.people
        if query.min_price is not None:
            filters.append("t.base_price_amount_minor >= :min_price")
            params["min_price"] = query.min_price
        if query.max_price is not None:
            filters.append("t.base_price_amount_minor <= :max_price")
            params["max_price"] = query.max_price
        if query.start_date is not None:
            filters.append("(t.service_start_date is null or t.service_start_date <= :start_date)")
            params["start_date"] = query.start_date
        if query.end_date is not None:
            filters.append("(t.service_end_date is null or t.service_end_date >= :end_date)")
            params["end_date"] = query.end_date
        return await self._fetch_many(" and ".join(filters), params)

    async def get(self, listing_id: UUID) -> PublicListingRecord | None:
        records = await self._fetch_many(
            "l.id = :listing_id and l.status in ('published', 'paused') and "
            "(l.expires_at is null or l.expires_at >= current_date)",
            {"listing_id": listing_id, "limit": 1},
        )
        return records[0] if records else None

    async def get_preview(self, listing_id: UUID) -> ListingPreviewRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select lv.version_no, lv.title, lv.body,
                           coalesce(jsonb_agg(jsonb_build_object(
                             'id', lc.id, 'order', lc.clause_order, 'title', lc.title, 'body', lc.body
                           ) order by lc.clause_order) filter (where lc.id is not null), '[]'::jsonb) as clauses
                    from public.listings l
                    join public.listing_versions lv on lv.id = l.current_version_id
                    left join public.listing_clauses lc on lc.listing_version_id = lv.id
                    where l.id = :listing_id and l.status in ('published', 'paused')
                      and (l.expires_at is null or l.expires_at >= current_date)
                    group by lv.id
                    """
                ),
                {"listing_id": listing_id},
            )
        except SQLAlchemyError as exc:
            raise RepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return ListingPreviewRecord(listing_id=listing_id, **row)

    async def _fetch_many(
        self, where_clause: str, params: dict[str, object]
    ) -> list[PublicListingRecord]:
        try:
            result = await self._session.execute(
                text(
                    f"""
                    select l.id, l.status::text, l.title, l.display_title, l.district, l.category::text,
                           l.ai_summary, l.expires_at::date, o.name as seller_name,
                           o.rating_average as seller_rating, o.rating_count as seller_rating_count,
                           (o.verification_status = 'verified') as seller_verified, l.current_version_id,
                           t.service_start_date, t.service_end_date, t.supply_quantity, t.quantity_unit,
                           t.base_price_amount_minor, t.currency, t.price_unit, t.minimum_people,
                           t.maximum_people, t.cancellation_policy, t.refund_policy, t.settlement_policy,
                           t.safety_policy, t.compensation_policy, t.liability_policy,
                           t.price_display_basis, t.contract_availability_note
                    from public.listings l
                    join public.organizations o on o.id = l.seller_organization_id
                    left join public.listing_terms t on t.listing_id = l.id
                    where {where_clause}
                    order by l.published_at desc nulls last, l.id
                    limit :limit
                    """  # noqa: S608 - where_clause uses only fixed fragments above
                ),
                params,
            )
        except SQLAlchemyError as exc:
            raise RepositoryUnavailableError from exc
        return [PublicListingRecord(**row) for row in result.mappings().all()]
