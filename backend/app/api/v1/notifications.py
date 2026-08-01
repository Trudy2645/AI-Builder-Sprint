from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.dependencies import get_notification_service
from app.core.auth import get_current_user
from app.domain.notifications.service import NotificationService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.notifications import (
    ContractAuditEvent,
    NotificationItem,
    NotificationListResponse,
    NotificationReadPatch,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=SuccessEnvelope[NotificationListResponse])
async def list_notifications(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SuccessEnvelope[NotificationListResponse]:
    notifications = await service.list_notifications(actor, unread_only=unread_only, limit=limit)
    return typed_envelope(request, notifications)


@router.patch(
    "/notifications/{notification_id}",
    response_model=SuccessEnvelope[NotificationItem],
)
async def mark_notification_read(
    request: Request,
    notification_id: UUID,
    payload: NotificationReadPatch,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> SuccessEnvelope[NotificationItem]:
    del payload
    notification = await service.mark_notification_read(notification_id, actor)
    return typed_envelope(request, notification)


@router.get(
    "/contracts/{contract_id}/audit-events",
    response_model=SuccessEnvelope[list[ContractAuditEvent]],
)
async def list_contract_audit_events(
    request: Request,
    contract_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[list[ContractAuditEvent]]:
    events = await service.list_contract_audit_events(contract_id, actor, organization_id)
    return typed_envelope(request, events)
