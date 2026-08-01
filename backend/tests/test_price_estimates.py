from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_price_estimate_service
from app.domain.pricing.service import PriceEstimateService
from app.integrations.exchange_rates import (
    ExchangeRateProvider,
    ExchangeRateProviderError,
    ExchangeRateQuote,
    FakeExchangeRateProvider,
)
from app.repositories.pricing import (
    ListingPriceTermsRecord,
    PriceTermsRepositoryUnavailableError,
)

LISTING_ID = UUID("70000000-0000-0000-0000-000000000001")
MISSING_ID = UUID("70000000-0000-0000-0000-000000000099")
NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)
RATE_AS_OF = datetime(2026, 7, 31, 9, tzinfo=UTC)


class FakePriceTermsRepository:
    def __init__(self) -> None:
        self.record = ListingPriceTermsRecord(
            listing_id=LISTING_ID,
            status="published",
            expires_at=datetime(2026, 12, 31, tzinfo=UTC),
            service_start_date=date(2026, 7, 1),
            service_end_date=date(2026, 12, 31),
            quantity_unit="person",
            base_price_amount_minor=10_000,
            currency="KRW",
            price_unit="person",
        )
        self.unavailable = False
        self.read_count = 0
        self.write_count = 0
        self.internal_seller_note = "never expose this"
        self.provider_credential = "never expose this either"

    async def get_listing_price_terms(self, listing_id: UUID) -> ListingPriceTermsRecord | None:
        self.read_count += 1
        if self.unavailable:
            raise PriceTermsRepositoryUnavailableError
        return self.record if listing_id == LISTING_ID else None


class FailingExchangeRateProvider:
    async def get_rate(self, _: str, __: str) -> ExchangeRateQuote:
        raise ExchangeRateProviderError("private provider details")


class TimeoutExchangeRateProvider:
    async def get_rate(self, _: str, __: str) -> ExchangeRateQuote:
        raise TimeoutError("private provider timeout details")


def request_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "people": 2,
        "quantity": 2,
        "quantity_unit": "person",
        "nights": 2,
        "start_date": "2026-08-10",
        "end_date": "2026-08-12",
        "currency": "KRW",
    }
    payload.update(changes)
    return payload


@pytest.fixture
def price_repository() -> FakePriceTermsRepository:
    return FakePriceTermsRepository()


@pytest.fixture
def exchange_provider() -> FakeExchangeRateProvider:
    return FakeExchangeRateProvider(
        {("KRW", "JPY"): Decimal("0.10345")},
        as_of=RATE_AS_OF,
    )


@pytest.fixture
def price_client(
    app: FastAPI,
    price_repository: FakePriceTermsRepository,
    exchange_provider: FakeExchangeRateProvider,
) -> TestClient:
    service = PriceEstimateService(
        price_repository,
        exchange_provider,
        now=lambda: NOW,
    )
    app.dependency_overrides[get_price_estimate_service] = lambda: service
    with TestClient(app) as client:
        yield client


def post_estimate(client: TestClient, payload: dict[str, object] | None = None):
    return client.post(
        f"/api/v1/public/listings/{LISTING_ID}/price-estimates",
        json=payload or request_payload(),
    )


def test_per_person_price_uses_people_as_explicit_quantity(price_client: TestClient) -> None:
    response = post_estimate(price_client)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["base_unit_price_amount_minor"] == 10_000
    assert data["billing_quantity"] == 2
    assert data["quantity_unit"] == "person"
    assert data["total_estimated_amount_minor"] == 20_000
    assert data["formula"] == "10000 KRW × 2 person"


@pytest.mark.parametrize(
    ("price_unit", "quantity_unit", "quantity", "expected"),
    [
        ("room", "room", 3, 30_000),
        ("vehicle", "vehicle", 2, 20_000),
    ],
)
def test_per_unit_prices_do_not_assume_people_per_unit(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
    price_unit: str,
    quantity_unit: str,
    quantity: int,
    expected: int,
) -> None:
    price_repository.record = replace(
        price_repository.record,
        price_unit=price_unit,
        quantity_unit=quantity_unit,
    )

    response = post_estimate(
        price_client,
        request_payload(
            people=30,
            quantity=quantity,
            quantity_unit=quantity_unit,
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["total_estimated_amount_minor"] == expected


def test_room_night_price_multiplies_nights(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    price_repository.record = replace(
        price_repository.record,
        price_unit="room_night",
        quantity_unit="room",
    )

    response = post_estimate(
        price_client,
        request_payload(people=30, quantity=15, quantity_unit="room"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_estimated_amount_minor"] == 300_000
    assert data["formula"] == "10000 KRW × 15 room × 2 nights"


def test_same_currency_uses_rate_one_without_provider_call(
    price_client: TestClient,
    exchange_provider: FakeExchangeRateProvider,
) -> None:
    response = post_estimate(price_client)

    assert response.status_code == 200
    assert response.json()["data"]["exchange_rate"] == "1"
    assert exchange_provider.calls == []


def test_currency_conversion_uses_decimal_and_half_up_rounding(
    price_client: TestClient,
    exchange_provider: FakeExchangeRateProvider,
) -> None:
    response = post_estimate(price_client, request_payload(currency="JPY"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_estimated_amount_minor"] == 2069
    assert data["exchange_rate"] == "0.10345"
    assert data["exchange_rate_as_of"] == RATE_AS_OF.isoformat().replace("+00:00", "Z")
    assert exchange_provider.calls == [("KRW", "JPY")]


@pytest.mark.parametrize("listing_status", ["published", "paused"])
def test_published_and_paused_listings_are_priceable(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
    listing_status: str,
) -> None:
    price_repository.record = replace(price_repository.record, status=listing_status)

    assert post_estimate(price_client).status_code == 200


def test_non_public_listing_is_rejected(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    price_repository.record = replace(price_repository.record, status="draft")

    response = post_estimate(price_client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LISTING_NOT_PRICEABLE"


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "expired"},
        {"expires_at": datetime(2026, 7, 30, tzinfo=UTC)},
        {"service_end_date": date(2026, 7, 30)},
    ],
)
def test_expired_listing_or_supply_period_is_rejected(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
    changes: dict[str, object],
) -> None:
    price_repository.record = replace(price_repository.record, **changes)

    response = post_estimate(price_client)

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "LISTING_EXPIRED"


def test_request_outside_supply_period_is_rejected(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    price_repository.record = replace(
        price_repository.record,
        service_start_date=date(2026, 9, 1),
    )

    response = post_estimate(price_client)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SERVICE_PERIOD_OUT_OF_RANGE"


@pytest.mark.parametrize(
    ("field", "value"),
    [("people", 0), ("people", -1), ("quantity", 0), ("quantity", -1), ("nights", 0)],
)
def test_non_positive_inputs_are_rejected(price_client: TestClient, field: str, value: int) -> None:
    response = post_estimate(price_client, request_payload(**{field: value}))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "changes",
    [
        {"start_date": "2026-08-12", "end_date": "2026-08-10"},
        {"start_date": "2026-08-10", "end_date": "2026-08-12", "nights": 3},
    ],
)
def test_invalid_dates_and_night_mismatch_are_rejected(
    price_client: TestClient, changes: dict[str, object]
) -> None:
    response = post_estimate(price_client, request_payload(**changes))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_per_person_quantity_must_equal_people(price_client: TestClient) -> None:
    response = post_estimate(price_client, request_payload(people=3, quantity=2))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_BILLING_QUANTITY"


def test_unsupported_request_quantity_unit_is_rejected(price_client: TestClient) -> None:
    response = post_estimate(
        price_client,
        request_payload(quantity_unit="guest"),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_QUANTITY_UNIT"


def test_unsupported_listing_price_unit_is_rejected(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    price_repository.record = replace(price_repository.record, price_unit="package")

    response = post_estimate(price_client)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_PRICE_UNIT"


@pytest.mark.parametrize(
    "changes",
    [
        {"base_price_amount_minor": None},
        {"currency": None},
    ],
)
def test_missing_price_or_currency_is_rejected(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
    changes: dict[str, object],
) -> None:
    price_repository.record = replace(price_repository.record, **changes)

    response = post_estimate(price_client)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRICE_TERMS_INCOMPLETE"


@pytest.mark.parametrize(
    "provider",
    [FailingExchangeRateProvider(), TimeoutExchangeRateProvider()],
)
def test_exchange_rate_failure_hides_provider_details(
    app: FastAPI,
    price_repository: FakePriceTermsRepository,
    provider: ExchangeRateProvider,
) -> None:
    service = PriceEstimateService(
        price_repository,
        provider,
        now=lambda: NOW,
    )
    app.dependency_overrides[get_price_estimate_service] = lambda: service
    with TestClient(app) as client:
        response = post_estimate(client, request_payload(currency="JPY"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EXCHANGE_RATE_UNAVAILABLE"
    assert "private provider" not in response.text


def test_database_failure_is_safe(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    price_repository.unavailable = True

    response = post_estimate(price_client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "SQL" not in response.text


def test_missing_listing_is_distinct(price_client: TestClient) -> None:
    response = price_client.post(
        f"/api/v1/public/listings/{MISSING_ID}/price-estimates",
        json=request_payload(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LISTING_NOT_FOUND"


def test_preview_response_exposes_no_private_or_internal_fields(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    response = post_estimate(price_client)

    assert response.status_code == 200
    body = response.text
    assert price_repository.internal_seller_note not in body
    assert price_repository.provider_credential not in body
    assert "seller" not in response.json()["data"]


def test_preview_is_stateless_and_does_not_write_database_rows(
    price_client: TestClient,
    price_repository: FakePriceTermsRepository,
) -> None:
    assert post_estimate(price_client).status_code == 200
    assert post_estimate(price_client).status_code == 200

    assert price_repository.read_count == 2
    assert price_repository.write_count == 0


def test_openapi_exposes_price_estimate_endpoint_and_schemas(price_client: TestClient) -> None:
    document = price_client.get("/openapi.json").json()
    operation = document["paths"]["/api/v1/public/listings/{listing_id}/price-estimates"]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "PriceEstimateRequest"
    )
    assert "PriceEstimate" in document["components"]["schemas"]
