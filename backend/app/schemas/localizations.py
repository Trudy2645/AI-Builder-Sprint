from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.listings import SupportedLocale


class ListingLocalizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_no: int = Field(gt=0)
    locales: list[SupportedLocale] = Field(
        default_factory=lambda: list(SupportedLocale), min_length=1, max_length=4
    )

    @field_validator("locales")
    @classmethod
    def unique_locales(cls, value: list[SupportedLocale]) -> list[SupportedLocale]:
        if len(value) != len(set(value)):
            raise ValueError("locales must not contain duplicates")
        return value


class LocalizationResult(BaseModel):
    locale: SupportedLocale
    status: Literal["succeeded", "cached", "failed"]
    localized_content_id: UUID | None = None
    job_id: UUID | None = None
    failure_code: str | None = None


class ListingLocalizationResponse(BaseModel):
    listing_id: UUID
    listing_version_id: UUID
    source_locale: SupportedLocale
    source_hash: str
    results: list[LocalizationResult]
