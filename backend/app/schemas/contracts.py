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


class ContractSummary(BaseModel):
    id: UUID
    listing_id: UUID | None
    listing_title: str
    status: str
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


class ContractDetail(ContractSummary):
    parties: list[ContractPartySummary]
    terms: ContractTermsResponse
    current_version: ContractVersionResponse


class ContractCancelResponse(BaseModel):
    contract_id: UUID
    status: Literal["cancelled"]
    cancelled_at: datetime
