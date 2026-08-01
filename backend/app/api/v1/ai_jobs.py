from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import get_ai_job_service
from app.core.auth import get_current_user
from app.domain.ai_jobs.service import AIJobService
from app.integrations.auth import AuthenticatedUser
from app.schemas.ai_jobs import AIJobView
from app.schemas.common import SuccessEnvelope, typed_envelope

router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])
OrganizationHeader = Annotated[str | None, Header(alias="X-Organization-Id")]


@router.get("/{job_id}", response_model=SuccessEnvelope[AIJobView])
async def get_ai_job(
    request: Request,
    job_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AIJobService, Depends(get_ai_job_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[AIJobView]:
    return typed_envelope(request, await service.get(job_id, actor, organization_id))
