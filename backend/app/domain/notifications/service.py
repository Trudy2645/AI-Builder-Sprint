from collections.abc import Callable
from datetime import date
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.repositories.notifications import (
    ContractAuditAccessRecord,
    NotificationRecord,
    NotificationRepository,
    NotificationRepositoryError,
)
from app.schemas.notifications import (
    ContractAuditEvent,
    NotificationItem,
    NotificationListResponse,
)


class NotificationService:
    _LISTING_EXPIRY_WARNING_DAYS = 7

    def __init__(
        self,
        repository: NotificationRepository,
        *,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._today = today

    async def list_notifications(
        self, actor: AuthenticatedUser, *, unread_only: bool, limit: int
    ) -> NotificationListResponse:
        try:
            await self._repository.materialize_listing_expiring_notifications(
                actor.id, self._today(), self._LISTING_EXPIRY_WARNING_DAYS
            )
            records = await self._repository.list_notifications(
                actor.id, unread_only=unread_only, limit=limit
            )
            unread_count = await self._repository.count_unread_notifications(actor.id)
        except NotificationRepositoryError as exc:
            self._database_unavailable(exc)
        return NotificationListResponse(
            items=[self._notification(record) for record in records],
            unread_count=unread_count,
        )

    async def mark_notification_read(
        self, notification_id: UUID, actor: AuthenticatedUser
    ) -> NotificationItem:
        try:
            record = await self._repository.mark_notification_read(notification_id, actor.id)
        except NotificationRepositoryError as exc:
            self._database_unavailable(exc)
        if record is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOTIFICATION_NOT_FOUND",
                message="Notification was not found.",
            )
        return self._notification(record)

    async def list_contract_audit_events(
        self,
        contract_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> list[ContractAuditEvent]:
        try:
            access = await self._repository.get_contract_audit_access(contract_id)
        except NotificationRepositoryError as exc:
            self._database_unavailable(exc)
        if access is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CONTRACT_NOT_FOUND",
                message="Contract was not found.",
            )
        await self._authorize_contract(access, actor, header_organization_id)
        try:
            records = await self._repository.list_contract_audit_events(contract_id)
        except NotificationRepositoryError as exc:
            self._database_unavailable(exc)
        return [
            ContractAuditEvent(
                id=record.id,
                event_type=record.event_type,
                actor_role=record.actor_role,
                target_type=record.target_type,
                target_id=record.target_id,
                event_data=record.event_data,
                created_at=record.created_at,
            )
            for record in records
        ]

    async def _authorize_contract(
        self,
        access: ContractAuditAccessRecord,
        actor: AuthenticatedUser,
        header: str | None,
    ) -> None:
        if access.buyer_user_id == actor.id:
            return
        organization_id = self._parse_organization_header(header)
        if organization_id != access.seller_organization_id:
            self._access_denied()
        try:
            member = await self._repository.is_seller_member(actor.id, organization_id)
        except NotificationRepositoryError as exc:
            self._database_unavailable(exc)
        if not member:
            self._access_denied()

    @staticmethod
    def _parse_organization_header(header: str | None) -> UUID:
        if header is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required for seller organization APIs.",
            )
        try:
            return UUID(header)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="X-Organization-Id must be a UUID.",
            ) from exc

    @staticmethod
    def _notification(record: NotificationRecord) -> NotificationItem:
        return NotificationItem(
            id=record.id,
            notification_type=record.notification_type,
            title=record.title,
            body=record.body,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            is_read=record.read_at is not None,
            read_at=record.read_at,
            created_at=record.created_at,
        )

    @staticmethod
    def _access_denied() -> None:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CONTRACT_ACCESS_DENIED",
            message="You do not have access to this contract.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
