from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class EvidenceDetailResponse(BaseModel):
    evidence_id: UUID
    finding_id: UUID
    document_version_id: UUID
    document_title: str
    source_kind: Literal["official", "template", "case_reference"]
    authority: str | None
    official_source_url: HttpUrl | None
    effective_from: date | None
    retrieved_at: datetime
    page_start: int = Field(gt=0)
    page_end: int = Field(gt=0)
    section: str | None
    bbox: dict[str, Any] | None
    excerpt: str
    viewer_url: str
    signed_pdf_url: str
    signed_url_expires_at: datetime
    disclaimer: str = "법률 자문이 아닌 계약 검토 보조 의견입니다."
