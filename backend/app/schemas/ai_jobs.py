from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AIJobView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    task_type: str
    status: Literal["queued", "processing", "succeeded", "failed"]
    progress: int = Field(ge=0, le=100)
    result_resource_type: str | None = None
    result_resource_id: UUID | None = None
    failure_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
