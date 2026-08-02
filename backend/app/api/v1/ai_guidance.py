from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.ai.schemas.guidance import (
    ChangeSummaryRequest,
    ContractAssistantOutput,
    ContractAssistantRequest,
    ContractTranslationOutput,
    ContractTranslationRequest,
    RevisionGuidanceOutput,
    RevisionGuidanceRequest,
    RevisionSuggestionOutput,
    RevisionSuggestionRequest,
)
from app.ai.schemas.public_summary import PublicSummaryOutput
from app.api.dependencies import get_ai_guidance_service
from app.core.auth import get_current_user
from app.domain.ai_guidance.service import AIGuidanceService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope

router = APIRouter(prefix="/ai-guidance", tags=["ai-guidance"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]


@router.post("/revision-impact", response_model=SuccessEnvelope[RevisionGuidanceOutput])
async def revision_impact(
    request: Request,
    payload: RevisionGuidanceRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AIGuidanceService, Depends(get_ai_guidance_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[RevisionGuidanceOutput]:
    del actor, idempotency_key
    return typed_envelope(request, await service.revision_guidance(payload))


@router.post(
    "/revision-suggestion",
    response_model=SuccessEnvelope[RevisionSuggestionOutput],
)
async def revision_suggestion(
    request: Request,
    payload: RevisionSuggestionRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AIGuidanceService, Depends(get_ai_guidance_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[RevisionSuggestionOutput]:
    del actor, idempotency_key
    return typed_envelope(request, await service.revision_suggestion(payload))


@router.post("/change-summary", response_model=SuccessEnvelope[PublicSummaryOutput])
async def change_summary(
    request: Request,
    payload: ChangeSummaryRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AIGuidanceService, Depends(get_ai_guidance_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[PublicSummaryOutput]:
    del actor, idempotency_key
    return typed_envelope(request, await service.change_summary(payload))


@router.post(
    "/contract-translation",
    response_model=SuccessEnvelope[ContractTranslationOutput],
)
async def contract_translation(
    request: Request,
    payload: ContractTranslationRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AIGuidanceService, Depends(get_ai_guidance_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[ContractTranslationOutput]:
    del actor, idempotency_key
    return typed_envelope(request, await service.contract_translation(payload))


@router.post(
    "/contract-assistant",
    response_model=SuccessEnvelope[ContractAssistantOutput],
)
async def contract_assistant(
    request: Request,
    payload: ContractAssistantRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AIGuidanceService, Depends(get_ai_guidance_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[ContractAssistantOutput]:
    del actor, idempotency_key
    return typed_envelope(request, await service.contract_assistant(payload))
