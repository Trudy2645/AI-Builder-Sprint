from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.errors import AppError
from app.domain.listings.service import PublicListingService
from app.repositories.public_listings import ListingPreviewRecord, PublicListingRecord
from app.schemas.public_listings import PriceEstimateRequest, PublicListingQuery


class FakePublicListingRepository:
    def __init__(self, listing: PublicListingRecord) -> None:
        self.listing = listing

    async def list(self, _: PublicListingQuery) -> list[PublicListingRecord]:
        return [self.listing] if self.listing.status == "published" else []

    async def get(self, listing_id: UUID) -> PublicListingRecord | None:
        return self.listing if listing_id == self.listing.id else None

    async def get_preview(self, listing_id: UUID) -> ListingPreviewRecord | None:
        if listing_id != self.listing.id:
            return None
        return ListingPreviewRecord(
            listing_id=listing_id,
            version_no=1,
            title=self.listing.title,
            body="Contract body",
            clauses=[],
        )


def listing(*, price_unit: str = "person_night", status: str = "published") -> PublicListingRecord:
    return PublicListingRecord(
        id=uuid4(),
        status=status,
        title="Busan activity",
        display_title=None,
        district="해운대구",
        category="activity",
        ai_summary="A summary",
        expires_at=None,
        seller_name="Busan Seller",
        seller_rating=Decimal("4.5"),
        seller_rating_count=10,
        seller_verified=True,
        service_start_date=date(2026, 8, 1),
        service_end_date=date(2026, 8, 31),
        supply_quantity=50,
        quantity_unit="person",
        base_price_amount_minor=10_000,
        currency="KRW",
        price_unit=price_unit,
        minimum_people=2,
        maximum_people=50,
        cancellation_policy=None,
        refund_policy=None,
        settlement_policy=None,
        safety_policy=None,
        compensation_policy=None,
        liability_policy=None,
        price_display_basis=None,
        contract_availability_note=None,
        current_version_id=None,
    )


@pytest.mark.asyncio
async def test_public_listing_is_returned_with_contract_availability() -> None:
    record = listing()
    service = PublicListingService(FakePublicListingRepository(record))

    result = await service.list(PublicListingQuery())

    assert result[0].id == record.id
    assert result[0].contract_available is True
    assert result[0].seller.verified is True


@pytest.mark.asyncio
async def test_price_estimate_is_calculated_on_server_for_person_price() -> None:
    record = listing()
    service = PublicListingService(FakePublicListingRepository(record))

    result = await service.estimate_price(
        record.id,
        PriceEstimateRequest(
            people=3,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 12),
            currency="KRW",
        ),
    )

    assert result.billable_quantity == 3
    assert result.nights == 2
    assert result.total_amount_minor == 60_000


@pytest.mark.asyncio
async def test_unit_priced_listing_requires_explicit_quantity() -> None:
    record = listing(price_unit="room_night")
    service = PublicListingService(FakePublicListingRepository(record))

    with pytest.raises(AppError, match="Enter the number of units") as raised:
        await service.estimate_price(
            record.id,
            PriceEstimateRequest(
                people=3,
                start_date=date(2026, 8, 10),
                end_date=date(2026, 8, 12),
                currency="KRW",
            ),
        )

    assert raised.value.code == "QUANTITY_REQUIRED"


@pytest.mark.asyncio
async def test_price_estimate_rejects_unavailable_dates() -> None:
    record = listing()
    service = PublicListingService(FakePublicListingRepository(record))

    with pytest.raises(AppError) as raised:
        await service.estimate_price(
            record.id,
            PriceEstimateRequest(
                people=3,
                start_date=date(2026, 7, 31),
                end_date=date(2026, 8, 2),
                currency="KRW",
            ),
        )

    assert raised.value.code == "SERVICE_PERIOD_UNAVAILABLE"


@pytest.mark.asyncio
async def test_paused_listing_rejects_new_price_estimate() -> None:
    record = listing(status="paused")
    service = PublicListingService(FakePublicListingRepository(record))

    with pytest.raises(AppError) as raised:
        await service.estimate_price(
            record.id,
            PriceEstimateRequest(
                people=3,
                start_date=date(2026, 8, 10),
                end_date=date(2026, 8, 12),
                currency="KRW",
            ),
        )

    assert raised.value.code == "LISTING_NOT_AVAILABLE"
