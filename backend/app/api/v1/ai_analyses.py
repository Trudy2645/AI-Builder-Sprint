from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import get_contract_review_service
from app.core.auth import get_current_user
from app.domain.contract_review.service import ContractReviewService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.contract_review import ContractReviewRunResponse

router = APIRouter(prefix="/ai-analysis-runs", tags=["ai-analysis-runs"])


@router.get("/{run_id}", response_model=SuccessEnvelope[ContractReviewRunResponse])
async def get_contract_review_run(
    request: Request,
    run_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractReviewService, Depends(get_contract_review_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractReviewRunResponse]:
    return typed_envelope(request, await service.get_run(run_id, actor, organization_id))
