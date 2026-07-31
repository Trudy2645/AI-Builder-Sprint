from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.contracts import ContractClauseResponse


class RevisionRequestType(StrEnum):
    MODIFY = "modify"
    DELETE = "delete"
    ADD = "add"


class RevisionItemDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTERED = "countered"


class RevisionStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_ACCEPTED = "partially_accepted"
    COUNTERED = "countered"
    CANCELLED = "cancelled"


class RevisionItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_type: RevisionRequestType
    clause_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=2000)
    requested_text: str | None = Field(default=None, min_length=1, max_length=20_000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_shape(self) -> "RevisionItemInput":
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must not contain duplicates")
        if self.request_type == RevisionRequestType.MODIFY:
            if self.clause_id is None or self.requested_text is None:
                raise ValueError("modify requires clause_id and requested_text")
        elif self.request_type == RevisionRequestType.DELETE:
            if self.clause_id is None or self.requested_text is not None:
                raise ValueError("delete requires clause_id and null requested_text")
        elif self.clause_id is not None or self.requested_text is None:
            raise ValueError("add requires null clause_id and requested_text")
        return self


class RevisionRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    base_version_no: int = Field(gt=0)
    message: str | None = Field(default=None, max_length=2000)
    items: list[RevisionItemInput] = Field(default_factory=list, max_length=50)


class RevisionItemDecisionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["accepted", "rejected", "countered"]
    seller_reason: str | None = Field(default=None, max_length=2000)
    counter_text: str | None = Field(default=None, min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def validate_counter(self) -> "RevisionItemDecisionUpdate":
        if self.decision == "countered" and self.counter_text is None:
            raise ValueError("countered requires counter_text")
        if self.decision != "countered" and self.counter_text is not None:
            raise ValueError("counter_text is only allowed for countered decisions")
        return self


RevisionItemPatch = RevisionItemInput | RevisionItemDecisionUpdate


class RevisionDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    seller_message: str | None = Field(default=None, max_length=2000)


class RevisionResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["accepted", "rejected"]
    message: str | None = Field(default=None, max_length=2000)


class RevisionItemResponse(BaseModel):
    id: UUID
    item_order: int
    request_type: RevisionRequestType
    clause_id: UUID | None
    reason: str
    requested_text: str | None
    document_ids: list[UUID]
    decision: RevisionItemDecision
    seller_reason: str | None
    counter_text: str | None
    decided_at: datetime | None


class RevisionDecisionPreview(BaseModel):
    resulting_clauses: list[ContractClauseResponse]
    pending_item_count: int = Field(ge=0)
    requires_buyer_response: bool
    will_create_version: bool


class RevisionRequestResponse(BaseModel):
    id: UUID
    contract_id: UUID
    base_version_no: int
    status: RevisionStatus
    requested_by_user_id: UUID
    message: str | None
    seller_message: str | None
    response_message: str | None
    items: list[RevisionItemResponse]
    decision_preview: RevisionDecisionPreview
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    decided_at: datetime | None
    responded_at: datetime | None


class RevisionMutationResponse(BaseModel):
    revision_request_id: UUID
    status: RevisionStatus
    contract_id: UUID
    contract_status: str
    version_no: int | None = None
    replayed: bool = False


class SellerRevisionRequestListItem(BaseModel):
    id: UUID
    contract_id: UUID
    listing_title: str
    buyer_name: str
    status: RevisionStatus
    message: str | None
    item_count: int = Field(ge=0)
    item_summary: list[str]
    has_unread: bool
    sent_at: datetime | None
    updated_at: datetime
