from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationItem(BaseModel):
    id: UUID
    notification_type: str
    title: str
    body: str
    resource_type: str | None
    resource_id: UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int = Field(ge=0)


class NotificationReadPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read: Literal[True]


class ContractAuditEvent(BaseModel):
    id: UUID
    event_type: str
    actor_role: str
    target_type: str | None
    target_id: UUID | None
    event_data: dict[str, Any]
    created_at: datetime
