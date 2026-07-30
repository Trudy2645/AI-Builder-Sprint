from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ResponseMeta


class ListingCategory(StrEnum):
    VEHICLE_RENTAL = "vehicle_rental"
    ACTIVITY = "activity"
    TOUR = "tour"
    ACCOMMODATION = "accommodation"


class SupportedLocale(StrEnum):
    KO_KR = "ko-KR"
    EN_US = "en-US"
    JA_JP = "ja-JP"
    ZH_CN = "zh-CN"


class PublicListingSort(StrEnum):
    RECOMMENDED = "recommended"
    POPULAR = "popular"
    LATEST = "latest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class PublicListingQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str | None = Field(default=None, min_length=1, max_length=200)
    contract_available_only: bool = Field(
        default=False,
        description="Return only published listings that accept new contract requests.",
    )
    sort: PublicListingSort = PublicListingSort.RECOMMENDED
    district: list[str] = Field(default_factory=list)
    people: int | None = Field(default=None, gt=0)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    category: ListingCategory | None = None
    start_date: date | None = None
    end_date: date | None = None
    locale: SupportedLocale = SupportedLocale.KO_KR
    cursor: str | None = Field(default=None, min_length=1, max_length=2000)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_ranges(self) -> "PublicListingQuery":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must be less than or equal to max_price")
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be less than or equal to end_date")
        return self


class PublicSeller(BaseModel):
    name: str
    rating: Decimal
    rating_count: int
    verified: bool


class Money(BaseModel):
    amount_minor: int
    currency: str
    unit: str | None


class Availability(BaseModel):
    start_date: date | None
    end_date: date | None


class PublicListingCard(BaseModel):
    id: UUID
    seller: PublicSeller
    title: str
    district: str
    category: ListingCategory
    hero_image_url: str | None
    ai_summary: str | None
    base_price: Money | None
    availability: Availability
    status: Literal["published", "paused"]
    contract_available: bool
    attention_required_count: int = Field(
        ge=0,
        description=(
            "Distinct clauses with non-dismissed findings from the latest successful "
            "buyer analysis."
        ),
    )


class PublicListingListMeta(ResponseMeta):
    next_cursor: str | None
    has_more: bool


class PublicListingListEnvelope(BaseModel):
    data: list[PublicListingCard]
    meta: PublicListingListMeta


class PublicClause(BaseModel):
    id: UUID
    clause_key: str | None
    title: str
    body: str
    highlight: Literal["critical", "warning", "info"] | None = None


class PublicListingDetail(PublicListingCard):
    supply_quantity: int | None
    quantity_unit: str | None
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
    no_show_policy: None = Field(
        default=None,
        description="Unsupported until a canonical no-show policy source is available.",
    )
    vat_included: None = Field(
        default=None,
        description="Unsupported until a canonical VAT inclusion source is available.",
    )
    clauses: list[PublicClause]
    requested_locale: SupportedLocale
    content_locale: SupportedLocale
    fallback_locale: SupportedLocale | None


class PublicFinding(BaseModel):
    clause_id: UUID | None
    severity: Literal["high", "medium", "low", "none"]
    explanation: str
    suggested_text: str | None
    disclaimer: str


class PublicContractPreview(BaseModel):
    listing_version_id: UUID
    body: str
    clauses: list[PublicClause]
    findings: list[PublicFinding]
    requested_locale: SupportedLocale
    content_locale: SupportedLocale
    fallback_locale: SupportedLocale | None
