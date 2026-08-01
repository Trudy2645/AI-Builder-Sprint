from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, status

from app.api.dependencies import get_contract_review_service, get_evidence_service
from app.core.auth import get_current_user
from app.domain.contract_review.service import ContractReviewService
from app.domain.evidence.service import EvidenceService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.contract_review import (
    FindingApplyRequest,
    FindingApplyResponse,
    FindingDismissRequest,
    FindingDismissResponse,
)
from app.schemas.evidence import EvidenceDetailResponse

router = APIRouter(prefix="/ai-findings", tags=["ai-findings"])


@router.get(
    "/{finding_id}/evidence/{evidence_id}",
    response_model=SuccessEnvelope[EvidenceDetailResponse],
)
async def get_ai_finding_evidence(
    request: Request,
    finding_id: UUID,
    evidence_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[EvidenceDetailResponse]:
    evidence = await service.get_evidence(finding_id, evidence_id, actor, organization_id)
    return typed_envelope(request, evidence)


@router.post(
    "/{finding_id}/apply",
    response_model=SuccessEnvelope[FindingApplyResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def apply_ai_finding(
    request: Request,
    finding_id: UUID,
    payload: FindingApplyRequest,
    background_tasks: BackgroundTasks,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractReviewService, Depends(get_contract_review_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[FindingApplyResponse]:
    started = await service.apply_finding(
        finding_id, payload, actor, organization_id, idempotency_key
    )
    for review in started.reviews:
        background_tasks.add_task(
            service.run,
            job_id=review.job.job_id,
            target=review.target,
            viewer_role=review.job.viewer_role,
        )
    return typed_envelope(request, started.response)


@router.post("/{finding_id}/dismiss", response_model=SuccessEnvelope[FindingDismissResponse])
async def dismiss_ai_finding(
    request: Request,
    finding_id: UUID,
    payload: FindingDismissRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractReviewService, Depends(get_contract_review_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[FindingDismissResponse]:
    dismissed = await service.dismiss_finding(
        finding_id, payload, actor, organization_id, idempotency_key
    )
    return typed_envelope(request, dismissed)
