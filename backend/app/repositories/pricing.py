from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ListingPriceTermsRecord:
    listing_id: UUID
    status: str
    expires_at: datetime | None
    service_start_date: date | None
    service_end_date: date | None
    quantity_unit: str | None
    base_price_amount_minor: int | None
    currency: str | None
    price_unit: str | None


class PriceTermsRepositoryUnavailableError(Exception):
    pass


class PriceTermsRepository(Protocol):
    async def get_listing_price_terms(self, listing_id: UUID) -> ListingPriceTermsRecord | None: ...


class SqlAlchemyPriceTermsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_listing_price_terms(self, listing_id: UUID) -> ListingPriceTermsRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select l.id as listing_id, l.status::text as status, l.expires_at,
                           lt.service_start_date, lt.service_end_date, lt.quantity_unit,
                           lt.base_price_amount_minor, lt.currency, lt.price_unit
                    from public.listings l
                    left join public.listing_terms lt on lt.listing_id = l.id
                    where l.id = :listing_id
                    """
                ),
                {"listing_id": listing_id},
            )
        except SQLAlchemyError as exc:
            raise PriceTermsRepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return ListingPriceTermsRecord(**row) if row else None
