from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.schemas import LocalizedPublicContent
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


class ListingStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    PUBLISHED = "published"
    PAUSED = "paused"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class ListingCreationMethod(StrEnum):
    MANUAL = "manual"
    UPLOAD = "upload"


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
    public_headline: str | None
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
    requested_locale: SupportedLocale = SupportedLocale.KO_KR
    content_locale: SupportedLocale = SupportedLocale.KO_KR
    fallback_locale: SupportedLocale | None = None


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
    supply_quantity_description: str | None
    quantity_unit: str | None
    minimum_quantity: int | None
    maximum_quantity: int | None
    people_per_unit: int | None
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
    vat_included: None = Field(
        default=None,
        description="Unsupported until a canonical VAT inclusion source is available.",
    )
    clauses: list[PublicClause]
    localized_content: LocalizedPublicContent | None = None


class PublicEvidenceReference(BaseModel):
    id: UUID
    label: str = Field(pattern=r"^\[[1-9][0-9]*\]$")
    document_title: str
    source_kind: Literal["official", "case_reference"]
    page: int = Field(gt=0)
    section: str | None = None
    excerpt: str


class PublicFinding(BaseModel):
    id: UUID | None = None
    clause_id: UUID | None
    severity: Literal["high", "medium", "low", "none"]
    explanation: str
    suggested_text: str | None
    disclaimer: str
    evidence_refs: list[PublicEvidenceReference] = Field(default_factory=list)


class PublicContractPreview(BaseModel):
    listing_version_id: UUID
    body: str
    clauses: list[PublicClause]
    findings: list[PublicFinding]
    requested_locale: SupportedLocale
    content_locale: SupportedLocale
    fallback_locale: SupportedLocale | None
    localized_content: LocalizedPublicContent | None = None


class SellerListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    creation_method: ListingCreationMethod
    title: str = Field(min_length=1, max_length=200)
    category: ListingCategory
    district: str = Field(min_length=1, max_length=100)
    language: SupportedLocale = SupportedLocale.KO_KR


class SellerListingTermsPatchValues(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_start_date: date | None = None
    service_end_date: date | None = None
    supply_quantity: int | None = Field(default=None, gt=0)
    supply_quantity_description: str | None = Field(default=None, min_length=1, max_length=500)
    quantity_unit: str | None = Field(default=None, min_length=1, max_length=32)
    minimum_quantity: int | None = Field(default=None, gt=0)
    maximum_quantity: int | None = Field(default=None, gt=0)
    people_per_unit: int | None = Field(default=None, gt=0)
    base_price_amount_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    price_unit: str | None = Field(default=None, min_length=1, max_length=32)
    minimum_people: int | None = Field(default=None, gt=0)
    maximum_people: int | None = Field(default=None, gt=0)
    cancellation_policy: str | None = Field(default=None, max_length=10000)
    no_show_policy: str | None = Field(default=None, max_length=10000)
    refund_policy: str | None = Field(default=None, max_length=10000)
    settlement_policy: str | None = Field(default=None, max_length=10000)
    safety_policy: str | None = Field(default=None, max_length=10000)
    compensation_policy: str | None = Field(default=None, max_length=10000)
    liability_policy: str | None = Field(default=None, max_length=10000)
    termination_policy: str | None = Field(default=None, max_length=10000)
    special_terms: str | None = Field(default=None, max_length=10000)
    price_display_basis: str | None = Field(default=None, max_length=500)
    contract_availability_note: str | None = Field(default=None, max_length=1000)


class SellerListingTermsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_no: int = Field(gt=0)
    terms: SellerListingTermsPatchValues


class SellerListingPresentationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_company_name: str | None = Field(default=None, max_length=200)
    display_title: str | None = Field(default=None, max_length=200)
    hero_document_id: UUID | None = None
    seller_description: str | None = Field(default=None, max_length=5000)
    public_headline: str | None = Field(default=None, max_length=1000)
    price_display_basis: str | None = Field(default=None, max_length=500)
    contract_availability_note: str | None = Field(default=None, max_length=1000)


class SellerListingClause(BaseModel):
    id: UUID
    clause_order: int = Field(gt=0)
    clause_key: str | None
    title: str
    body: str


class SellerListingVersion(BaseModel):
    id: UUID
    version_no: int = Field(gt=0)
    title: str
    body: str
    created_at: datetime
    clauses: list[SellerListingClause]


class SellerListingTerms(BaseModel):
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


class SellerListingSummary(BaseModel):
    id: UUID
    title: str
    display_title: str | None
    category: ListingCategory
    district: str
    status: ListingStatus
    creation_method: ListingCreationMethod
    public_headline: str | None
    service_start_date: date | None
    service_end_date: date | None
    supply_quantity_description: str | None
    base_price: Money | None
    contract_available: bool
    attention_required_count: int = Field(ge=0)
    current_version_no: int
    contract_request_count: int = Field(ge=0)
    missing_fields: list[str]
    created_at: datetime
    updated_at: datetime


class SellerListingDetail(SellerListingSummary):
    language: SupportedLocale
    display_company_name: str | None
    seller_description: str | None
    ai_summary: str | None
    hero_document_id: UUID | None
    terms: SellerListingTerms
    current_version: SellerListingVersion
    processing_job: None = None
    published_at: datetime | None
    paused_at: datetime | None


class SellerListingCreated(BaseModel):
    listing_id: UUID
    status: Literal["draft"] = "draft"
    version_no: int = 1


class SellerListingMutationResponse(BaseModel):
    listing_id: UUID
    status: ListingStatus
    version_no: int
    missing_fields: list[str]
