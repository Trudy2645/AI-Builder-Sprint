from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import get_seller_listing_service
from app.core.auth import get_current_user
from app.domain.seller_listings.service import SellerListingService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.listings import (
    SellerListingCreate,
    SellerListingCreated,
    SellerListingDetail,
    SellerListingMutationResponse,
    SellerListingPresentationPatch,
    SellerListingSummary,
    SellerListingTermsPatch,
)

router = APIRouter(prefix="/seller/listings", tags=["seller-listings"])
OrganizationHeader = Annotated[str | None, Header(alias="X-Organization-Id")]


@router.get("", response_model=SuccessEnvelope[list[SellerListingSummary]])
async def list_seller_listings(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[list[SellerListingSummary]]:
    return typed_envelope(request, await service.list_listings(actor, organization_id))


@router.get("/{listing_id}", response_model=SuccessEnvelope[SellerListingDetail])
async def get_seller_listing(
    request: Request,
    listing_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingDetail]:
    return typed_envelope(request, await service.get_listing(listing_id, actor, organization_id))


@router.post(
    "",
    response_model=SuccessEnvelope[SellerListingCreated],
    status_code=status.HTTP_201_CREATED,
)
async def create_seller_listing(
    request: Request,
    payload: SellerListingCreate,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingCreated]:
    created = await service.create_listing(payload, actor, organization_id, idempotency_key)
    return typed_envelope(request, created)


@router.patch("/{listing_id}/terms", response_model=SuccessEnvelope[SellerListingDetail])
async def update_seller_listing_terms(
    request: Request,
    listing_id: UUID,
    payload: SellerListingTermsPatch,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingDetail]:
    listing = await service.update_terms(listing_id, payload, actor, organization_id)
    return typed_envelope(request, listing)


@router.post(
    "/{listing_id}/complete",
    response_model=SuccessEnvelope[SellerListingMutationResponse],
)
async def complete_seller_listing(
    request: Request,
    listing_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingMutationResponse]:
    result = await service.complete_listing(listing_id, actor, organization_id)
    return typed_envelope(request, result)


@router.patch(
    "/{listing_id}/presentation",
    response_model=SuccessEnvelope[SellerListingDetail],
)
async def update_seller_listing_presentation(
    request: Request,
    listing_id: UUID,
    payload: SellerListingPresentationPatch,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingDetail]:
    listing = await service.update_presentation(listing_id, payload, actor, organization_id)
    return typed_envelope(request, listing)


@router.post(
    "/{listing_id}/publish",
    response_model=SuccessEnvelope[SellerListingMutationResponse],
)
async def publish_seller_listing(
    request: Request,
    listing_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingMutationResponse]:
    result = await service.publish_listing(listing_id, actor, organization_id)
    return typed_envelope(request, result)


@router.post(
    "/{listing_id}/pause",
    response_model=SuccessEnvelope[SellerListingMutationResponse],
)
async def pause_seller_listing(
    request: Request,
    listing_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingMutationResponse]:
    result = await service.pause_listing(listing_id, actor, organization_id)
    return typed_envelope(request, result)


@router.post(
    "/{listing_id}/archive",
    response_model=SuccessEnvelope[SellerListingMutationResponse],
)
async def archive_seller_listing(
    request: Request,
    listing_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[SellerListingService, Depends(get_seller_listing_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[SellerListingMutationResponse]:
    result = await service.archive_listing(listing_id, actor, organization_id)
    return typed_envelope(request, result)
