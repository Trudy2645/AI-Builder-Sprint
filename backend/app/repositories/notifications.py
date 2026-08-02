from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    id: UUID
    notification_type: str
    title: str
    body: str
    resource_type: str | None
    resource_id: UUID | None
    read_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ContractAuditAccessRecord:
    contract_id: UUID
    buyer_user_id: UUID
    seller_organization_id: UUID


@dataclass(frozen=True, slots=True)
class ContractAuditEventRecord:
    id: UUID
    event_type: str
    actor_role: str
    target_type: str | None
    target_id: UUID | None
    event_data: dict[str, Any]
    created_at: datetime


class NotificationRepositoryError(Exception):
    pass


class NotificationRepository(Protocol):
    async def materialize_listing_expiring_notifications(
        self, user_id: UUID, today: date, warning_days: int
    ) -> None: ...

    async def list_notifications(
        self, user_id: UUID, *, unread_only: bool, limit: int
    ) -> list[NotificationRecord]: ...

    async def count_unread_notifications(self, user_id: UUID) -> int: ...

    async def mark_notification_read(
        self, notification_id: UUID, user_id: UUID
    ) -> NotificationRecord | None: ...

    async def get_contract_audit_access(
        self, contract_id: UUID
    ) -> ContractAuditAccessRecord | None: ...

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...

    async def list_contract_audit_events(
        self, contract_id: UUID
    ) -> list[ContractAuditEventRecord]: ...


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize_listing_expiring_notifications(
        self, user_id: UUID, today: date, warning_days: int
    ) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        insert into public.notifications (
                            user_id, notification_type, title, body,
                            resource_type, resource_id, dedupe_key
                        )
                        select :user_id, 'listing_expiring', '공고 만료 예정',
                               coalesce(l.display_title, l.title) ||
                                   ' 공고의 공급 기간이 곧 종료됩니다.',
                               'listing', l.id,
                               'listing-expiring:' || l.id::text || ':' ||
                                   lt.service_end_date::text
                        from public.listings l
                        join public.listing_terms lt on lt.listing_id = l.id
                        where l.seller_organization_id in (
                            select organization_id
                            from public.organization_members
                            where user_id = :user_id
                        )
                          and l.status in ('published', 'paused')
                          and lt.service_end_date between cast(:today as date)
                              and (cast(:today as date) + cast(:warning_days as integer))
                        on conflict (user_id, dedupe_key)
                            where dedupe_key is not null
                        do nothing
                        """
                    ),
                    {
                        "user_id": user_id,
                        "today": today,
                        "warning_days": warning_days,
                    },
                )
        except SQLAlchemyError as exc:
            raise NotificationRepositoryError from exc

    async def list_notifications(
        self, user_id: UUID, *, unread_only: bool, limit: int
    ) -> list[NotificationRecord]:
        condition = "and read_at is null" if unread_only else ""
        try:
            result = await self._session.execute(
                text(
                    f"""
                    select id, notification_type, title, body, resource_type,
                           resource_id, read_at, created_at
                    from public.notifications
                    where user_id = :user_id {condition}
                    order by created_at desc, id desc
                    limit :limit
                    """  # noqa: S608 - condition is selected from a fixed boolean branch
                ),
                {"user_id": user_id, "limit": limit},
            )
            return [NotificationRecord(**row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            raise NotificationRepositoryError from exc

    async def count_unread_notifications(self, user_id: UUID) -> int:
        try:
            result = await self._session.execute(
                text(
                    """
                    select count(*)::integer
                    from public.notifications
                    where user_id = :user_id and read_at is null
                    """
                ),
                {"user_id": user_id},
            )
            return result.scalar_one()
        except SQLAlchemyError as exc:
            raise NotificationRepositoryError from exc

    async def mark_notification_read(
        self, notification_id: UUID, user_id: UUID
    ) -> NotificationRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    update public.notifications
                    set read_at = coalesce(read_at, now())
                    where id = :notification_id and user_id = :user_id
                    returning id, notification_type, title, body, resource_type,
                              resource_id, read_at, created_at
                    """
                ),
                {"notification_id": notification_id, "user_id": user_id},
            )
            row = result.mappings().one_or_none()
            await self._session.commit()
            return NotificationRecord(**row) if row else None
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise NotificationRepositoryError from exc

    async def get_contract_audit_access(
        self, contract_id: UUID
    ) -> ContractAuditAccessRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id as contract_id, buyer_user_id, seller_organization_id
                    from public.contracts
                    where id = :contract_id
                    """
                ),
                {"contract_id": contract_id},
            )
            row = result.mappings().one_or_none()
            return ContractAuditAccessRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise NotificationRepositoryError from exc

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        try:
            result = await self._session.execute(
                text(
                    """
                    select exists (
                        select 1 from public.organization_members
                        where user_id = :user_id and organization_id = :organization_id
                    )
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            return bool(result.scalar_one())
        except SQLAlchemyError as exc:
            raise NotificationRepositoryError from exc

    async def list_contract_audit_events(self, contract_id: UUID) -> list[ContractAuditEventRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, event_type, actor_role, target_type, target_id,
                           event_data, created_at
                    from public.audit_events
                    where contract_id = :contract_id
                    order by created_at, id
                    """
                ),
                {"contract_id": contract_id},
            )
            return [ContractAuditEventRecord(**row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            raise NotificationRepositoryError from exc
