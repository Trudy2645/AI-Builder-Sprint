from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class AIJobRecord:
    id: UUID
    job_type: str
    status: str
    failure_code: str | None
    result_metadata: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    seller_organization_id: UUID | None
    buyer_user_id: UUID | None


@dataclass(frozen=True, slots=True)
class AIJobMembershipRecord:
    organization_id: UUID
    organization_type: str


class AIJobRepositoryError(Exception):
    pass


class AIJobRepository(Protocol):
    async def get_job(self, job_id: UUID) -> AIJobRecord | None: ...

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> AIJobMembershipRecord | None: ...


class SqlAlchemyAIJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_job(self, job_id: UUID) -> AIJobRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select j.id, j.job_type, j.status::text, j.failure_code,
                           j.result_metadata, j.created_at, j.started_at, j.completed_at,
                           coalesce(
                               d.organization_id,
                               dl.seller_organization_id,
                               dc.seller_organization_id,
                               l.seller_organization_id,
                               c.seller_organization_id
                           ) as seller_organization_id,
                           coalesce(dc.buyer_user_id, c.buyer_user_id) as buyer_user_id
                    from public.ai_jobs j
                    left join public.documents d on d.id = j.document_id
                    left join public.listings dl on dl.id = d.listing_id
                    left join public.contracts dc on dc.id = d.contract_id
                    left join public.listing_versions lv on lv.id = j.listing_version_id
                    left join public.listings l on l.id = lv.listing_id
                    left join public.contract_versions cv on cv.id = j.contract_version_id
                    left join public.contracts c on c.id = cv.contract_id
                    where j.id = :job_id
                    """
                ),
                {"job_id": job_id},
            )
            row = result.mappings().one_or_none()
            return AIJobRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise AIJobRepositoryError from exc

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> AIJobMembershipRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.organization_type::text
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id and om.organization_id = :organization_id
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            row = result.mappings().one_or_none()
            return AIJobMembershipRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise AIJobRepositoryError from exc
