from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(ge=0)
    height: float = Field(ge=0)


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    content: bytes = Field(min_length=1, repr=False)


class ParsedBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    content: str
    page_number: int = Field(ge=1)
    bbox: BoundingBox | None = None


class ParsedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    blocks: list[ParsedBlock] = Field(default_factory=list)


class DocumentParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[ParsedPage] = Field(default_factory=list)
    markdown: str | None = None
    html: str | None = None
    provider_request_id: str | None = None
    model_name: str = "document-parse"


class ExtractedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_page: int | None = Field(default=None, ge=1)
    source_quote: str | None = None
    bbox: BoundingBox | None = None
    missing: bool = False

    @model_validator(mode="after")
    def validate_missing_value(self) -> ExtractedValue:
        if self.missing and self.value is not None:
            raise ValueError("A missing extracted value cannot contain a value.")
        return self


class ExtractedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, ExtractedValue] = Field(default_factory=dict)
    missing: bool = False


class ContractExtraction(BaseModel):
    """Required Information Extract areas; absent source data remains explicit."""

    model_config = ConfigDict(extra="forbid")

    price: ExtractedSection
    service_period: ExtractedSection
    cancellation: ExtractedSection
    refund: ExtractedSection
    safety: ExtractedSection
    compensation: ExtractedSection
    liability: ExtractedSection
    provider_request_id: str | None = None
    model_name: str = "information-extract"


class LanguageModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: Literal[
        "contract_generate",
        "contract_review",
        "public_summary",
        "localize_explain",
        "revision_draft",
    ]
    system_prompt: str = Field(min_length=1)
    input_data: dict[str, Any]
    prompt_version: str = Field(min_length=1)
    reasoning_effort: Literal["low", "medium", "high"] | None = None


class FileSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    vector_store_id: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=5, ge=1, le=5)


class FileSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(min_length=1)
    chunk_id: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    excerpt: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hits: list[FileSearchHit]
    provider_request_id: str | None = None


class VectorStoreRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str | None = None


class KnowledgeFileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    filename: str = Field(min_length=1)


class VectorStoreFileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    status: Literal["in_progress", "completed", "failed", "cancelled"]
    last_error: str | None = None
