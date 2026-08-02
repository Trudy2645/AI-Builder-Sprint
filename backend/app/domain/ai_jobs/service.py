from typing import NoReturn
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.repositories.ai_jobs import AIJobRecord, AIJobRepository, AIJobRepositoryError
from app.schemas.ai_jobs import AIJobView


class AIJobService:
    def __init__(self, repository: AIJobRepository) -> None:
        self._repository = repository

    async def get(
        self,
        job_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> AIJobView:
        try:
            record = await self._repository.get_job(job_id)
            if record is None:
                self._not_found()
            await self._authorize(record, actor, organization_header)
            return self._view(record)
        except AIJobRepositoryError as exc:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="DATABASE_UNAVAILABLE",
                message="The database is temporarily unavailable.",
            ) from exc

    async def _authorize(
        self,
        record: AIJobRecord,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> None:
        if record.buyer_user_id == actor.id:
            return
        organization_id = record.seller_organization_id
        if organization_id is None:
            self._access_denied()
        if organization_header is None:
            self._access_denied("X-Organization-Id is required for seller AI job access.")
        try:
            header_id = UUID(organization_header)
        except (ValueError, AttributeError):
            self._access_denied("X-Organization-Id must be a valid UUID.")
        if header_id != organization_id:
            self._access_denied()
        membership = await self._repository.get_membership(actor.id, organization_id)
        if membership is None or membership.organization_type != "seller":
            self._access_denied()

    @staticmethod
    def _view(record: AIJobRecord) -> AIJobView:
        metadata = record.result_metadata or {}
        default_progress = {
            "queued": 0,
            "processing": 50,
            "succeeded": 100,
            "failed": 100,
        }[record.status]
        raw_progress = metadata.get("progress", default_progress)
        progress = raw_progress if isinstance(raw_progress, int) else default_progress
        progress = min(max(progress, 0), 100)
        raw_resource_id = metadata.get("result_resource_id")
        try:
            resource_id = UUID(raw_resource_id) if raw_resource_id else None
        except (ValueError, TypeError, AttributeError):
            resource_id = None
        return AIJobView(
            id=record.id,
            task_type=record.job_type,
            status=record.status,  # type: ignore[arg-type]
            progress=progress,
            result_resource_type=metadata.get("result_resource_type"),
            result_resource_id=resource_id,
            failure_code=record.failure_code,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )

    @staticmethod
    def _not_found() -> NoReturn:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="AI_JOB_NOT_FOUND",
            message="AI job not found.",
        )

    @staticmethod
    def _access_denied(message: str = "You do not have access to this AI job.") -> NoReturn:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="AI_JOB_ACCESS_DENIED",
            message=message,
        )
