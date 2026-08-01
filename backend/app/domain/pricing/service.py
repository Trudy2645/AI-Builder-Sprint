from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.domain.pricing.units import PRICE_UNIT_RULES, SUPPORTED_QUANTITY_UNITS
from app.integrations.exchange_rates import (
    ExchangeRateProvider,
    ExchangeRateProviderError,
    ExchangeRateQuote,
)
from app.repositories.pricing import (
    ListingPriceTermsRecord,
    PriceTermsRepository,
    PriceTermsRepositoryUnavailableError,
)
from app.schemas.pricing import PriceEstimate, PriceEstimateRequest

PRICE_ESTIMATE_DISCLAIMER = (
    "This is an estimated price based on the current listing terms and exchange rate. "
    "The final contract price may differ."
)


class PriceEstimateService:
    def __init__(
        self,
        repository: PriceTermsRepository,
        exchange_rate_provider: ExchangeRateProvider,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._calculator = PriceCalculator(exchange_rate_provider, now=now)

    async def _get_terms(self, listing_id: UUID) -> ListingPriceTermsRecord:
        try:
            terms = await self._repository.get_listing_price_terms(listing_id)
        except PriceTermsRepositoryUnavailableError as exc:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="DATABASE_UNAVAILABLE",
                message="Database connection is unavailable.",
            ) from exc
        if terms is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LISTING_NOT_FOUND",
                message="Listing was not found.",
            )
        return terms

    async def estimate(self, listing_id: UUID, request: PriceEstimateRequest) -> PriceEstimate:
        terms = await self._get_terms(listing_id)
        return await self._calculator.calculate(terms, request)


class PriceCalculator:
    def __init__(
        self,
        exchange_rate_provider: ExchangeRateProvider,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._exchange_rate_provider = exchange_rate_provider
        self._now = now or (lambda: datetime.now(UTC))

    async def calculate(
        self, terms: ListingPriceTermsRecord, request: PriceEstimateRequest
    ) -> PriceEstimate:
        now = self._now()
        self._validate_listing(terms, request, now)
        expected_quantity_unit, uses_nights = self._validate_units(terms, request)

        if terms.price_unit == "person" and request.people != request.quantity:
            self._raise(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_BILLING_QUANTITY",
                "For per-person pricing, quantity must equal people.",
            )

        base_price = terms.base_price_amount_minor
        base_currency = terms.currency
        if base_price is None or base_currency is None:  # narrowed by _validate_listing
            raise AssertionError("validated price terms are incomplete")
        multiplier = request.quantity * (request.nights if uses_nights else 1)
        base_total = base_price * multiplier
        quote = await self._exchange_rate(base_currency, request.currency, now)
        display_total = int(
            (Decimal(base_total) * quote.rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        formula = f"{base_price} {base_currency} × {request.quantity} {expected_quantity_unit}"
        if uses_nights:
            formula += f" × {request.nights} nights"
        if request.currency != base_currency:
            formula += f" × {quote.rate} {request.currency}/{base_currency}"

        return PriceEstimate(
            base_unit_price_amount_minor=base_price,
            billing_quantity=request.quantity,
            quantity_unit=expected_quantity_unit,
            nights=request.nights,
            start_date=request.start_date,
            end_date=request.end_date,
            formula=formula,
            total_estimated_amount_minor=display_total,
            base_currency=base_currency,
            display_currency=request.currency,
            exchange_rate=quote.rate,
            exchange_rate_as_of=quote.as_of,
            disclaimer=PRICE_ESTIMATE_DISCLAIMER,
        )

    @classmethod
    def _validate_listing(
        cls,
        terms: ListingPriceTermsRecord,
        request: PriceEstimateRequest,
        now: datetime,
    ) -> None:
        if terms.status == "expired" or (terms.expires_at is not None and terms.expires_at < now):
            cls._raise(
                status.HTTP_410_GONE,
                "LISTING_EXPIRED",
                "The listing has expired.",
            )
        if terms.status not in {"published", "paused"}:
            cls._raise(
                status.HTTP_409_CONFLICT,
                "LISTING_NOT_PRICEABLE",
                "The listing is not available for price estimates.",
            )
        if terms.service_end_date is not None and terms.service_end_date < now.date():
            cls._raise(
                status.HTTP_410_GONE,
                "LISTING_EXPIRED",
                "The listing supply period has ended.",
            )
        if (
            terms.service_start_date is not None and request.start_date < terms.service_start_date
        ) or (terms.service_end_date is not None and request.end_date > terms.service_end_date):
            cls._raise(
                status.HTTP_400_BAD_REQUEST,
                "SERVICE_PERIOD_OUT_OF_RANGE",
                "The requested dates are outside the listing supply period.",
            )
        if terms.base_price_amount_minor is None or terms.currency is None:
            cls._raise(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "PRICE_TERMS_INCOMPLETE",
                "The listing does not have a base price and currency.",
            )

    @classmethod
    def _validate_units(
        cls,
        terms: ListingPriceTermsRecord,
        request: PriceEstimateRequest,
    ) -> tuple[str, bool]:
        if request.quantity_unit not in SUPPORTED_QUANTITY_UNITS:
            cls._raise(
                status.HTTP_400_BAD_REQUEST,
                "UNSUPPORTED_QUANTITY_UNIT",
                "The requested quantity unit is not supported.",
            )
        if terms.price_unit not in PRICE_UNIT_RULES:
            cls._raise(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "UNSUPPORTED_PRICE_UNIT",
                "The listing price unit is not supported.",
            )
        expected_quantity_unit, uses_nights = PRICE_UNIT_RULES[terms.price_unit]
        if terms.quantity_unit != expected_quantity_unit:
            cls._raise(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "UNSUPPORTED_QUANTITY_UNIT",
                "The listing quantity unit does not match its price unit.",
            )
        if request.quantity_unit != expected_quantity_unit:
            cls._raise(
                status.HTTP_400_BAD_REQUEST,
                "UNSUPPORTED_QUANTITY_UNIT",
                "The requested quantity unit does not match the listing price unit.",
            )
        return expected_quantity_unit, uses_nights

    async def _exchange_rate(
        self, base_currency: str, display_currency: str, now: datetime
    ) -> ExchangeRateQuote:
        if base_currency == display_currency:
            return ExchangeRateQuote(rate=Decimal("1"), as_of=now)
        try:
            quote = await self._exchange_rate_provider.get_rate(base_currency, display_currency)
        except (ExchangeRateProviderError, TimeoutError) as exc:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="EXCHANGE_RATE_UNAVAILABLE",
                message="The exchange rate is temporarily unavailable.",
            ) from exc
        if quote.rate <= 0 or quote.as_of.tzinfo is None:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="EXCHANGE_RATE_UNAVAILABLE",
                message="The exchange rate is temporarily unavailable.",
            )
        return quote

    @staticmethod
    def _raise(status_code: int, code: str, message: str) -> None:
        raise AppError(status_code=status_code, code=code, message=message)
