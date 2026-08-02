import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentStatus = Literal["ON_PROCESSING", "ON_GOING", "COMPLETED"]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignatureParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["바이어"]
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_must_look_valid(cls, value: str) -> str:
        if not _EMAIL_PATTERN.match(value):
            raise ValueError("email must be a valid email address")
        return value


class SignatureRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    buyer: SignatureParticipant


class SignatureRequestResponse(BaseModel):
    document_id: str
    title: str
    status: DocumentStatus


class DocumentFile(BaseModel):
    download_url: str | None = None


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    current_signing_order: int | None = None
    file: DocumentFile | None = None
    audit_trail: DocumentFile | None = None
