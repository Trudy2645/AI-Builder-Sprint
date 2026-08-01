import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class AIJobIdentity(BaseModel):
    """Immutable identity used to deduplicate cost-bearing AI executions."""

    model_config = ConfigDict(extra="forbid")

    task_type: str
    prompt_version: str | None = None
    model_name: str | None = None
    document_id: UUID | None = None
    listing_version_id: UUID | None = None
    contract_version_id: UUID | None = None
    viewer_role: Literal["buyer", "seller"] | None = None

    @model_validator(mode="after")
    def require_one_target(self) -> "AIJobIdentity":
        targets = (self.document_id, self.listing_version_id, self.contract_version_id)
        if sum(target is not None for target in targets) != 1:
            raise ValueError("Exactly one immutable AI job target is required.")
        return self

    def idempotency_key(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"ai:{hashlib.sha256(canonical.encode()).hexdigest()}"


ALLOWED_AI_JOB_TRANSITIONS = {
    "queued": frozenset({"processing", "failed"}),
    "processing": frozenset({"succeeded", "failed"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
}


def can_transition_ai_job(current: str, target: str) -> bool:
    return target in ALLOWED_AI_JOB_TRANSITIONS.get(current, frozenset())
