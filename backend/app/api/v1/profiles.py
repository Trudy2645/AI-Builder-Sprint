from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import get_profile_service
from app.core.auth import get_current_user
from app.domain.profiles.service import ProfileService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.profiles import MeResponse, OrganizationPatch, OrganizationResponse, ProfilePatch

router = APIRouter(tags=["profiles"])


@router.get("/me", response_model=SuccessEnvelope[MeResponse])
async def get_me(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> SuccessEnvelope[MeResponse]:
    return typed_envelope(request, await service.get_me(actor))


@router.patch("/me", response_model=SuccessEnvelope[MeResponse])
async def update_me(
    request: Request,
    patch: ProfilePatch,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> SuccessEnvelope[MeResponse]:
    return typed_envelope(request, await service.update_me(actor, patch))


@router.get(
    "/organizations/{organization_id}",
    response_model=SuccessEnvelope[OrganizationResponse],
)
async def get_organization(
    request: Request,
    organization_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
    header_organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[OrganizationResponse]:
    organization = await service.get_organization(actor, organization_id, header_organization_id)
    return typed_envelope(request, organization)


@router.patch(
    "/organizations/{organization_id}",
    response_model=SuccessEnvelope[OrganizationResponse],
)
async def update_organization(
    request: Request,
    organization_id: UUID,
    patch: OrganizationPatch,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
    header_organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[OrganizationResponse]:
    organization = await service.update_organization(
        actor, organization_id, header_organization_id, patch
    )
    return typed_envelope(request, organization)
