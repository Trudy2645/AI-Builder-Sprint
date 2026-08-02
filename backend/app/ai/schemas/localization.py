from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocalizedClause(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    clause_id: UUID
    clause_no: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    easy_explanation: str = Field(min_length=1, max_length=4000)


class LocalizedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    finding_id: UUID
    clause_id: UUID | None
    severity: Literal["high", "medium", "low", "none"]
    explanation: str = Field(min_length=1, max_length=4000)
    suggested_text: str | None = Field(default=None, max_length=8000)
    disclaimer: str = Field(min_length=1, max_length=1000)
    evidence_numbers: list[int] = Field(default_factory=list)


class LocalizedPublicContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    locale: Literal["ko-KR", "en-US", "ja-JP", "zh-CN"]
    title: str = Field(min_length=1, max_length=500)
    public_headline: str | None = Field(default=None, max_length=1000)
    summary: str = Field(min_length=1, max_length=2000)
    easy_explanation: str = Field(min_length=1, max_length=8000)
    terms: dict[str, str | None]
    clauses: list[LocalizedClause]
    findings: list[LocalizedFinding]
    preserved_facts: dict[str, Any]
    preserved_names: list[str]
    disclaimer: str = Field(min_length=1, max_length=1000)
