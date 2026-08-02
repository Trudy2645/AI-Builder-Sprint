from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.listings import ListingCategory, SupportedLocale

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class SignupCommon(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=72)
    password_confirmation: str = Field(min_length=8, max_length=72)
    username: str | None = Field(default=None, min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def passwords_match(self) -> "SignupCommon":
        if self.password != self.password_confirmation:
            raise ValueError("password and password_confirmation must match")
        return self


class BuyerSignupRequest(SignupCommon):
    role: Literal["buyer"]
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    locale: SupportedLocale
    affiliation_name: str | None = Field(default=None, max_length=200)
    business_type: str | None = Field(default=None, max_length=80)
    default_group_name: str | None = Field(default=None, max_length=160)
    preferred_currency: str = Field(pattern=r"^[A-Z]{3}$")


class SellerSignupRequest(SignupCommon):
    role: Literal["seller"]
    organization_name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    representative_name: str = Field(min_length=1, max_length=120)
    business_registration_no: str = Field(min_length=1, max_length=80)
    business_address: str = Field(min_length=1, max_length=500)
    supply_categories: list[ListingCategory] = Field(min_length=1, max_length=4)
    job_title: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def categories_are_unique(self) -> "SellerSignupRequest":
        if len(set(self.supply_categories)) != len(self.supply_categories):
            raise ValueError("supply_categories must not contain duplicates")
        return self


SignupRequest = Annotated[BuyerSignupRequest | SellerSignupRequest, Field(discriminator="role")]


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int = Field(gt=0)
    expires_at: int | None = None


class SignupResponse(BaseModel):
    user_id: UUID
    email: str
    role: Literal["buyer", "seller"]
    organization_id: UUID | None = None
    organization_verification_status: Literal["pending"] | None = None
    email_confirmation_required: bool
    session: AuthSessionResponse | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=72)


class LoginResponse(BaseModel):
    user_id: UUID
    email: str
    session: AuthSessionResponse


class DemoLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["buyer", "seller"]


class LogoutResponse(BaseModel):
    logged_out: Literal[True] = True


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=8, max_length=72)
    new_password_confirmation: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.new_password_confirmation:
            raise ValueError("new_password and new_password_confirmation must match")
        return self


class PasswordChangeResponse(BaseModel):
    password_changed: Literal[True] = True


class PasswordResetEmailResponse(BaseModel):
    email_sent: Literal[True] = True
