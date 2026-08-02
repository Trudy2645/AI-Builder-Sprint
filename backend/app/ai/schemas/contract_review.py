from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractReviewToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ContractReviewToolBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_calls: list[ContractReviewToolCall] = Field(min_length=1, max_length=12)


class ContractReviewFindingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: UUID | None = None
    category: str = Field(min_length=1, max_length=100)
    severity: Literal["high", "medium", "low", "none"]
    importance: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=4000)
    suggested_text: str | None = Field(default=None, max_length=8000)
    grounding_status: Literal["grounded", "insufficient_evidence", "not_required"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_location: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list, max_length=5)
    disclaimer: str = Field(min_length=1, max_length=1000)
    is_public: bool = False

    @model_validator(mode="after")
    def validate_legal_language_and_grounding(self) -> ContractReviewFindingCandidate:
        combined = " ".join(
            value for value in (self.title, self.explanation, self.suggested_text) if value
        ).lower()
        forbidden = ("위법", "무효", "불법", "illegal", "unlawful", "legally void")
        if any(term in combined for term in forbidden):
            raise ValueError("Definitive legal conclusions are not allowed.")
        if self.grounding_status == "grounded" and not self.evidence_ids:
            raise ValueError("Grounded findings require evidence_ids.")
        if self.grounding_status != "grounded" and self.evidence_ids:
            raise ValueError("Only grounded findings may reference evidence_ids.")
        return self


class ContractReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ContractReviewFindingCandidate] = Field(default_factory=list, max_length=50)
