# ruff: noqa: E501

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ListingCategory = Literal["vehicle_rental", "activity", "tour", "accommodation"]
Currency = str


class PublicListingQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ListingCategory | None = None
    district: str | None = Field(default=None, max_length=120)
    people: int | None = Field(default=None, gt=0)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    currency: Currency | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    start_date: date | None = None
    end_date: date | None = None
    contract_available_only: bool = False
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_period_and_price_range(self) -> "PublicListingQuery":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("end_date must not be earlier than start_date.")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("max_price must be greater than or equal to min_price.")
        return self


class SellerPublicSummary(BaseModel):
    name: str
    rating: float
    rating_count: int
    verified: bool


class PriceSummary(BaseModel):
    amount_minor: int
    currency: Currency
    unit: str | None = None


class Availability(BaseModel):
    start_date: date | None
    end_date: date | None


class PublicListingSummary(BaseModel):
    id: UUID
    seller: SellerPublicSummary
    title: str
    district: str
    category: ListingCategory
    hero_image_url: str | None = None
    ai_summary: str | None = None
    base_price: PriceSummary | None = None
    availability: Availability
    contract_available: bool


class PublicListingDetail(PublicListingSummary):
    supply_quantity: int | None = None
    quantity_unit: str | None = None
    minimum_people: int | None = None
    maximum_people: int | None = None
    cancellation_policy: str | None = None
    refund_policy: str | None = None
    no_show_policy: str | None = None
    settlement_policy: str | None = None
    safety_policy: str | None = None
    compensation_policy: str | None = None
    liability_policy: str | None = None
    price_display_basis: str | None = None
    contract_availability_note: str | None = None
    risk_clause_count: int = 0


class PreviewClause(BaseModel):
    id: UUID
    order: int
    title: str
    body: str


class ContractPreview(BaseModel):
    listing_id: UUID
    version_no: int
    title: str
    body: str
    clauses: list[PreviewClause]


class PriceEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    people: int = Field(gt=0)
    quantity: int | None = Field(default=None, gt=0)
    quantity_unit: str | None = Field(default=None, max_length=80)
    nights: int | None = Field(default=None, gt=0)
    start_date: date
    end_date: date
    currency: Currency = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_dates(self) -> "PriceEstimateRequest":
        if self.start_date > self.end_date:
            raise ValueError("end_date must not be earlier than start_date.")
        return self


class PriceEstimateResponse(BaseModel):
    listing_id: UUID
    base_price: PriceSummary
    billable_quantity: int
    nights: int
    formula: str
    total_amount_minor: int
    base_currency: Currency
    display_currency: Currency
    exchange_rate: float = 1
    exchange_rate_as_of: datetime | None = None
    disclaimer: str
