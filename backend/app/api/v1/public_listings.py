from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import get_price_estimate_service, get_public_listing_service
from app.domain.listings.service import PublicListingService
from app.domain.pricing.service import PriceEstimateService
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.listings import (
    PublicContractPreview,
    PublicListingDetail,
    PublicListingListEnvelope,
    PublicListingListMeta,
    PublicListingQuery,
    SupportedLocale,
)
from app.schemas.pricing import PriceEstimate, PriceEstimateRequest

router = APIRouter(prefix="/public/listings", tags=["public-listings"])


@router.post(
    "/{listing_id}/price-estimates",
    response_model=SuccessEnvelope[PriceEstimate],
)
async def create_price_estimate(
    request: Request,
    listing_id: UUID,
    payload: PriceEstimateRequest,
    service: Annotated[PriceEstimateService, Depends(get_price_estimate_service)],
) -> SuccessEnvelope[PriceEstimate]:
    return typed_envelope(request, await service.estimate(listing_id, payload))


@router.get("", response_model=PublicListingListEnvelope)
async def list_public_listings(
    request: Request,
    query: Annotated[PublicListingQuery, Query()],
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
) -> PublicListingListEnvelope:
    listings, next_cursor, has_more = await service.list_listings(query)
    return PublicListingListEnvelope(
        data=listings,
        meta=PublicListingListMeta(
            request_id=request.state.request_id,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
    )


@router.get("/{listing_id}", response_model=SuccessEnvelope[PublicListingDetail])
async def get_public_listing(
    request: Request,
    listing_id: UUID,
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
    locale: Annotated[SupportedLocale, Query()] = SupportedLocale.KO_KR,
) -> SuccessEnvelope[PublicListingDetail]:
    return typed_envelope(request, await service.get_listing(listing_id, locale))


@router.get(
    "/{listing_id}/contract-preview",
    response_model=SuccessEnvelope[PublicContractPreview],
)
async def get_public_contract_preview(
    request: Request,
    listing_id: UUID,
    service: Annotated[PublicListingService, Depends(get_public_listing_service)],
    locale: Annotated[SupportedLocale, Query()] = SupportedLocale.KO_KR,
) -> SuccessEnvelope[PublicContractPreview]:
    preview = await service.get_contract_preview(listing_id, locale)
    return typed_envelope(request, preview)
