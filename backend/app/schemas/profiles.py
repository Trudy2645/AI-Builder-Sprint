from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportedLocale = Literal["ko-KR", "en-US", "ja-JP", "zh-CN"]
BusinessRole = Literal["buyer", "seller"]
OrganizationMemberRole = Literal["owner", "admin", "member"]
VerificationStatus = Literal["pending", "verified", "rejected"]


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str | None = Field(default=None, min_length=1, max_length=80)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    locale: SupportedLocale | None = None
    preferred_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    default_group_name: str | None = Field(default=None, max_length=160)

    @field_validator("username", "display_name", "locale", "preferred_currency")
    @classmethod
    def required_fields_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Field cannot be null when supplied.")
        return value


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    verification_status: VerificationStatus
    member_role: OrganizationMemberRole


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    username: str
    display_name: str
    phone: str | None
    country_code: str | None
    locale: SupportedLocale
    preferred_currency: str
    default_group_name: str | None
    role: BusinessRole
    created_at: datetime
    updated_at: datetime
    organizations: list[OrganizationSummary] = Field(default_factory=list)


class OrganizationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    business_registration_no: str | None = Field(default=None, max_length=80)

    @field_validator("name")
    @classmethod
    def name_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Field cannot be null when supplied.")
        return value


class OrganizationResponse(BaseModel):
    id: UUID
    organization_type: Literal["seller"]
    name: str
    legal_name: str | None
    business_registration_no: str | None
    verification_status: VerificationStatus
    rating_average: Decimal
    rating_count: int
    member_role: OrganizationMemberRole
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None
