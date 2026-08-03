from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SigningCapacity(StrEnum):
    SELF = "self"
    GROUP_REPRESENTATIVE = "group_representative"


class InitialRequestKind(StrEnum):
    AS_IS = "as_is"
    REVISION = "revision"


class ContractBucket(StrEnum):
    DRAFT = "draft"
    SELLER_REVIEW = "seller_review"
    REVISION_REQUESTED = "revision_requested"
    SIGNING = "signing"
    SIGNED = "signed"
    CANCELLED = "cancelled"
    FINISHED = "finished"


class ContractRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    people: int = Field(gt=0)
    quantity: int = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=32)
    nights: int = Field(gt=0)
    start_date: date
    end_date: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    group_name: str | None = Field(default=None, min_length=1, max_length=160)
    signing_capacity: SigningCapacity = SigningCapacity.SELF
    request_message: str | None = Field(default=None, max_length=2000)
    initial_request_kind: InitialRequestKind

    @model_validator(mode="after")
    def validate_request(self) -> "ContractRequestCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be later than start_date")
        if (self.end_date - self.start_date).days != self.nights:
            raise ValueError("nights must equal the number of days between start_date and end_date")
        if self.signing_capacity == SigningCapacity.GROUP_REPRESENTATIVE and not self.group_name:
            raise ValueError("group_name is required for a group representative")
        return self


class ContractRequestCreated(BaseModel):
    contract_id: UUID
    version_no: int = 1
    status: Literal["seller_review", "revision_requested"]


class ContractPartySummary(BaseModel):
    role: Literal["buyer", "seller"]
    name: str
    country_code: str | None = None
    group_name: str | None = None
    signing_capacity: SigningCapacity | None = None


class ContractTermsResponse(BaseModel):
    people: int
    quantity: int
    quantity_unit: str
    nights: int
    start_date: date
    end_date: date
    amount_minor: int | None
    currency: str | None
    formula: str


class ContractClauseResponse(BaseModel):
    id: UUID
    clause_order: int
    clause_key: str | None
    title: str
    body: str


class ContractVersionResponse(BaseModel):
    id: UUID
    version_no: int
    title: str
    body: str
    clauses: list[ContractClauseResponse]


class ContractVersionPartyApproval(BaseModel):
    party_role: Literal["buyer", "seller"]
    approved: bool
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None


class ContractVersionApprovalsResponse(BaseModel):
    contract_id: UUID
    contract_version_id: UUID
    version_no: int = Field(gt=0)
    is_current_version: bool
    buyer: ContractVersionPartyApproval
    seller: ContractVersionPartyApproval
    all_approved: bool
    final_approval_requested: bool = False


class ContractVersionApproveResponse(ContractVersionApprovalsResponse):
    approved_role: Literal["buyer", "seller"]
    already_approved: bool
    contract_status: str


class ContractFinalApprovalRequestResponse(BaseModel):
    contract_id: UUID
    contract_version_id: UUID
    requested: bool
    already_requested: bool


class ContractSummary(BaseModel):
    id: UUID
    listing_id: UUID | None
    listing_title: str
    status: str
    bucket: ContractBucket
    status_label: str
    has_unread_response: bool
    initial_request_kind: InitialRequestKind
    request_message: str | None
    requested_people: int
    buyer_group_name: str | None
    signing_capacity: SigningCapacity
    amount_minor: int | None
    currency: str | None
    service_start_date: date
    service_end_date: date
    created_at: datetime
    updated_at: datetime
    seller_approved: bool = False
    final_approval_requested: bool = False


class ContractDetail(ContractSummary):
    parties: list[ContractPartySummary]
    terms: ContractTermsResponse
    current_version: ContractVersionResponse


class BuyerContractListItem(ContractSummary):
    seller_name: str


class SellerContractListItem(BaseModel):
    contract_id: UUID
    listing_id: UUID | None
    listing_title: str
    buyer_name: str
    buyer_group_name: str | None
    requested_people: int
    service_start_date: date
    service_end_date: date
    amount_minor: int | None
    currency: str | None
    initial_request_kind: InitialRequestKind
    request_kind_label: str
    status: str
    status_label: str
    buyer_approved: bool = False
    seller_approved: bool = False
    final_approval_requested: bool = False
    requested_at: datetime


class SellerDashboardStats(BaseModel):
    published_listings: int = Field(ge=0)
    received_requests: int = Field(ge=0)
    seller_review: int = Field(ge=0)
    revision_requested: int = Field(ge=0)
    signing: int = Field(ge=0)
    signed: int = Field(ge=0)
    cancelled: int = Field(ge=0)


class ListingRequestCount(BaseModel):
    listing_id: UUID
    listing_title: str
    listing_status: str
    request_count: int = Field(ge=0)


class SellerDashboard(BaseModel):
    stats: SellerDashboardStats
    recent_requests: list[SellerContractListItem]
    listing_request_counts: list[ListingRequestCount]


class ContractCancelResponse(BaseModel):
    contract_id: UUID
    status: Literal["cancelled"]
    cancelled_at: datetime


class SignatureRequestStatusResponse(BaseModel):
    id: UUID
    contract_id: UUID
    contract_version_id: UUID
    status: Literal["preparing", "in_progress", "completed", "failed", "cancelled"]
    provider: Literal["modusign"]
    provider_document_id: str | None = None
    provider_status: str | None = None
    current_signing_order: int | None = None
    completed_at: datetime | None = None
    signed_document_id: UUID | None = None
    audit_trail_document_id: UUID | None = None
    signing_delivery: Literal["email"] = "email"


class SignatureRequestCreated(SignatureRequestStatusResponse):
    reused: bool = False


class ContractSignatureParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)


class ContractSignatureRequestCreate(BaseModel):
    """Contact snapshots used for one immutable contract signing request."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    buyer: ContractSignatureParticipant
    seller: ContractSignatureParticipant
