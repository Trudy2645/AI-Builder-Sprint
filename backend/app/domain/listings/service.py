# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.repositories.profiles import RepositoryUnavailableError
from app.repositories.public_listings import PublicListingRecord, PublicListingRepository
from app.schemas.public_listings import (
    Availability,
    ContractPreview,
    PriceEstimateRequest,
    PriceEstimateResponse,
    PriceSummary,
    PublicListingDetail,
    PublicListingQuery,
    PublicListingSummary,
    SellerPublicSummary,
)


class PublicListingService:
    def __init__(self, repository: PublicListingRepository) -> None:
        self._repository = repository

    async def list(self, query: PublicListingQuery) -> list[PublicListingSummary]:
        try:
            records = await self._repository.list(query)
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return [self._summary(record) for record in records]

    async def get(self, listing_id: UUID) -> PublicListingDetail:
        record = await self._get_record(listing_id)
        return PublicListingDetail(
            **self._summary(record).model_dump(), **self._detail_fields(record)
        )

    async def get_preview(self, listing_id: UUID) -> ContractPreview:
        try:
            preview = await self._repository.get_preview(listing_id)
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if preview is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LISTING_NOT_FOUND",
                message="The requested listing or its public contract preview was not found.",
            )
        return ContractPreview(
            listing_id=preview.listing_id,
            version_no=preview.version_no,
            title=preview.title,
            body=preview.body,
            clauses=preview.clauses,
        )

    async def estimate_price(
        self, listing_id: UUID, request: PriceEstimateRequest
    ) -> PriceEstimateResponse:
        record = await self._get_record(listing_id)
        if record.status != "published":
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="LISTING_NOT_AVAILABLE",
                message="This listing is paused and cannot accept a new price estimate.",
                details={"action": "Choose an active listing or ask the seller to resume it."},
            )
        if record.base_price_amount_minor is None or record.currency is None:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="PRICE_NOT_CONFIGURED",
                message="The seller has not configured a usable base price for this listing.",
            )
        if request.currency != record.currency:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="UNSUPPORTED_DISPLAY_CURRENCY",
                message="Live currency conversion is not available yet. Use the listing's base currency.",
                details={"supported_currency": record.currency},
            )
        if (
            record.service_start_date
            and request.start_date < record.service_start_date
            or (record.service_end_date and request.end_date > record.service_end_date)
        ):
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="SERVICE_PERIOD_UNAVAILABLE",
                message="The requested dates are outside this listing's available service period.",
                details={
                    "available_start_date": record.service_start_date,
                    "available_end_date": record.service_end_date,
                },
            )
        if (
            record.minimum_people
            and request.people < record.minimum_people
            or (record.maximum_people and request.people > record.maximum_people)
        ):
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="PEOPLE_OUT_OF_RANGE",
                message="The requested number of people is outside the seller's allowed range.",
                details={
                    "minimum_people": record.minimum_people,
                    "maximum_people": record.maximum_people,
                },
            )

        nights = request.nights or max(1, (request.end_date - request.start_date).days)
        unit = (record.price_unit or "").lower().replace(" ", "_")
        if "person" in unit or "인" in unit:
            billable_quantity = request.people
        else:
            if request.quantity is None:
                raise AppError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="QUANTITY_REQUIRED",
                    message="This listing is priced per unit. Enter the number of units to estimate.",
                    details={"price_unit": record.price_unit},
                )
            billable_quantity = request.quantity
        total = record.base_price_amount_minor * billable_quantity * nights
        formula = f"{record.base_price_amount_minor} × {billable_quantity} × {nights} night(s)"
        return PriceEstimateResponse(
            listing_id=record.id,
            base_price=PriceSummary(
                amount_minor=record.base_price_amount_minor,
                currency=record.currency,
                unit=record.price_unit,
            ),
            billable_quantity=billable_quantity,
            nights=nights,
            formula=formula,
            total_amount_minor=total,
            base_currency=record.currency,
            display_currency=request.currency,
            exchange_rate_as_of=datetime.now(UTC),
            disclaimer="This is a server-calculated estimate, not a final contract price. The final price is recalculated when you request a contract.",
        )

    async def _get_record(self, listing_id: UUID) -> PublicListingRecord:
        try:
            record = await self._repository.get(listing_id)
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if record is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LISTING_NOT_FOUND",
                message="The requested listing is not available to the public.",
            )
        return record

    @staticmethod
    def _summary(record: PublicListingRecord) -> PublicListingSummary:
        return PublicListingSummary(
            id=record.id,
            seller=SellerPublicSummary(
                name=record.seller_name,
                rating=float(record.seller_rating),
                rating_count=record.seller_rating_count,
                verified=record.seller_verified,
            ),
            title=record.display_title or record.title,
            district=record.district,
            category=record.category,
            ai_summary=record.ai_summary,
            base_price=PriceSummary(
                amount_minor=record.base_price_amount_minor,
                currency=record.currency,
                unit=record.price_unit,
            )
            if record.base_price_amount_minor is not None and record.currency
            else None,
            availability=Availability(
                start_date=record.service_start_date, end_date=record.service_end_date
            ),
            contract_available=record.status == "published",
        )

    @staticmethod
    def _detail_fields(record: PublicListingRecord) -> dict[str, object]:
        return {
            key: getattr(record, key)
            for key in (
                "supply_quantity",
                "quantity_unit",
                "minimum_people",
                "maximum_people",
                "cancellation_policy",
                "refund_policy",
                "settlement_policy",
                "safety_policy",
                "compensation_policy",
                "liability_policy",
                "price_display_basis",
                "contract_availability_note",
            )
        }

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="The service is temporarily unable to load listings. Please try again shortly.",
        ) from exc
