from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContractGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_no: int = Field(gt=0)


class GeneratedListingClause(BaseModel):
    id: UUID
    clause_order: int = Field(gt=0)
    clause_key: str
    title: str
    body: str


class ContractGenerationResponse(BaseModel):
    listing_id: UUID
    job_id: UUID
    listing_version_id: UUID
    version_no: int = Field(gt=0)
    status: Literal["ready"]
    clauses: list[GeneratedListingClause]
