from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentProcessAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    job_id: UUID
    task_type: Literal["document_parse", "information_extract"]
    status: Literal["queued", "processing", "succeeded"]


class DocumentProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    status: Literal["processing", "ready", "failed"]
    schema_version: str | None = None
    extraction: dict[str, Any] | None = None
    confirmation_required: list[str]
    validation_warnings: list[str]
    listing_candidate: dict[str, Any] | None = None
    parsed_artifact_document_id: UUID | None = None
    failure_code: str | None = None
