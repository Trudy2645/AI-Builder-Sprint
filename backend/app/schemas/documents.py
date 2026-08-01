from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DocumentPurpose(StrEnum):
    SOURCE_CONTRACT = "source_contract"
    BUSINESS_VERIFICATION = "business_verification"
    REFERENCE = "reference"
    LISTING_HERO = "listing_hero"


class DocumentStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentUploadUrlRequest(BaseModel):
    organization_id: UUID | None = None
    listing_id: UUID | None = None
    contract_id: UUID | None = None
    purpose: DocumentPurpose
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(gt=0)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exactly_one_owner(self) -> "DocumentUploadUrlRequest":
        if sum(value is not None for value in self.owner_ids) != 1:
            raise ValueError(
                "exactly one of organization_id, listing_id, or contract_id is required"
            )
        return self

    @property
    def owner_ids(self) -> tuple[UUID | None, UUID | None, UUID | None]:
        return self.organization_id, self.listing_id, self.contract_id


class DocumentView(BaseModel):
    id: UUID
    organization_id: UUID | None
    listing_id: UUID | None
    contract_id: UUID | None
    purpose: DocumentPurpose
    status: DocumentStatus
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    content_sha256: str | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadUrl(BaseModel):
    document: DocumentView
    upload_url: str
    method: str = "PUT"
    expires_at: datetime


class DocumentDownloadUrl(BaseModel):
    document_id: UUID
    download_url: str
    expires_at: datetime
