from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContractReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    viewer_role: Literal["buyer", "seller"]
    analysis_types: list[Literal["summary", "risk", "missing_terms"]] = Field(
        default_factory=lambda: ["risk", "missing_terms"], min_length=1
    )


class ContractReviewAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    job_type: Literal["risk_analysis"] = "risk_analysis"
    execution_mode: Literal["single_agent"] = "single_agent"
    agent_name: Literal["contract_review"] = "contract_review"
    max_iterations: int = Field(default=2, ge=1, le=2)
    status: Literal["queued", "processing", "succeeded", "failed"]


class ContractReviewFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    viewer_role: Literal["buyer", "seller"]
    clause_id: UUID | None
    category: str
    severity: Literal["high", "medium", "low", "none"]
    importance: Literal["high", "medium", "low"]
    title: str
    explanation: str
    suggested_text: str | None
    suggested_text_hash: str | None
    grounding_status: Literal["grounded", "insufficient_evidence", "not_required"]
    confidence: float | None
    source_location: dict[str, Any]
    evidence: list[dict[str, Any]]
    disclaimer: str
    is_public: bool
    model_name: str
    prompt_version: str


class ContractReviewRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job_id: UUID | None
    target_type: Literal["listing_version", "contract_version"]
    target_id: UUID
    viewer_role: Literal["buyer", "seller"]
    status: Literal["queued", "processing", "succeeded", "failed"]
    execution_mode: Literal["single_agent"]
    agent_name: Literal["contract_review"]
    max_iterations: int = Field(ge=1, le=2)
    iterations_used: int = Field(ge=0, le=2)
    stop_reason: (
        Literal["completed", "max_iterations", "insufficient_evidence", "provider_error"] | None
    )
    model_name: str
    prompt_version: str
    findings: list[ContractReviewFindingResponse]


class FindingApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    base_version_no: int = Field(gt=0)
    suggested_text_hash: str = Field(pattern=r"^(sha256:)?[0-9a-f]{64}$")
    edited_text: str | None = Field(default=None, min_length=1, max_length=20_000)


class FindingApplyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    finding_status: Literal["applied"] = "applied"
    target_type: Literal["listing_version", "contract_version"]
    resource_id: UUID
    previous_version_id: UUID
    version_id: UUID
    version_no: int = Field(gt=0)
    analysis_job_ids: list[UUID] = Field(min_length=1, max_length=2)
    replayed: bool = False


class FindingDismissRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)


class FindingDismissResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: UUID
    finding_status: Literal["dismissed"] = "dismissed"
    replayed: bool = False
