# ruff: noqa: E501

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_public_listing_service
from app.domain.listings.service import PublicListingService
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.public_listings import (
    ContractPreview,
    PriceEstimateRequest,
    PriceEstimateResponse,
    PublicListingDetail,
    PublicListingQuery,
    PublicListingSummary,
)

router = APIRouter(prefix="/public/listings", tags=["public listings"])


@router.get("", response_model=SuccessEnvelope[list[PublicListingSummary]])
async def list_public_listings(
    request: Request,
    query: Annotated[PublicListingQuery, Depends()],
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
):
    return typed_envelope(request, await service.list(query))


@router.get("/{listing_id}", response_model=SuccessEnvelope[PublicListingDetail])
async def get_public_listing(
    request: Request,
    listing_id: UUID,
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
):
    return typed_envelope(request, await service.get(listing_id))


@router.get("/{listing_id}/contract-preview", response_model=SuccessEnvelope[ContractPreview])
async def get_contract_preview(
    request: Request,
    listing_id: UUID,
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
):
    return typed_envelope(request, await service.get_preview(listing_id))


@router.post("/{listing_id}/price-estimates", response_model=SuccessEnvelope[PriceEstimateResponse])
async def estimate_price(
    request: Request,
    listing_id: UUID,
    payload: PriceEstimateRequest,
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
):
    return typed_envelope(request, await service.estimate_price(listing_id, payload))
