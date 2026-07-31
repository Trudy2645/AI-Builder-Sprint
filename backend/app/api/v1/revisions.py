from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.dependencies import get_revision_service
from app.core.auth import get_current_user
from app.domain.revisions.service import RevisionService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.revisions import (
    RevisionDecisionRequest,
    RevisionItemDecisionUpdate,
    RevisionItemInput,
    RevisionMutationResponse,
    RevisionRequestCreate,
    RevisionRequestResponse,
    RevisionResponseRequest,
    SellerRevisionRequestListItem,
)

router = APIRouter(tags=["revisions"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
OrganizationHeader = Annotated[str | None, Header(alias="X-Organization-Id")]


@router.post(
    "/contracts/{contract_id}/revision-requests",
    response_model=SuccessEnvelope[RevisionMutationResponse],
)
async def create_revision_request(
    request: Request,
    contract_id: UUID,
    payload: RevisionRequestCreate,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[RevisionMutationResponse]:
    return typed_envelope(
        request, await service.create(contract_id, actor, payload, idempotency_key)
    )


@router.get(
    "/revision-requests/{revision_request_id}",
    response_model=SuccessEnvelope[RevisionRequestResponse],
)
async def get_revision_request(
    request: Request,
    revision_request_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[RevisionRequestResponse]:
    return typed_envelope(request, await service.get(revision_request_id, actor, organization_id))


@router.get(
    "/seller/revision-requests",
    response_model=SuccessEnvelope[list[SellerRevisionRequestListItem]],
)
async def list_seller_revision_requests(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    organization_id: OrganizationHeader = None,
    status_filter: Annotated[
        list[Literal["sent", "countered"]] | None, Query(alias="status")
    ] = None,
) -> SuccessEnvelope[list[SellerRevisionRequestListItem]]:
    statuses = set(status_filter) if status_filter else {"sent", "countered"}
    return typed_envelope(request, await service.list_seller(actor, organization_id, statuses))


@router.post(
    "/revision-requests/{revision_request_id}/items",
    response_model=SuccessEnvelope[RevisionMutationResponse],
)
async def add_revision_item(
    request: Request,
    revision_request_id: UUID,
    payload: RevisionItemInput,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[RevisionMutationResponse]:
    return typed_envelope(
        request,
        await service.add_item(revision_request_id, actor, payload, idempotency_key),
    )


@router.patch(
    "/revision-requests/{revision_request_id}/items/{item_id}",
    response_model=SuccessEnvelope[RevisionRequestResponse],
)
async def patch_revision_item(
    request: Request,
    revision_request_id: UUID,
    item_id: UUID,
    payload: RevisionItemInput | RevisionItemDecisionUpdate,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[RevisionRequestResponse]:
    return typed_envelope(
        request,
        await service.patch_item(revision_request_id, item_id, actor, organization_id, payload),
    )


@router.delete(
    "/revision-requests/{revision_request_id}/items/{item_id}",
    response_model=SuccessEnvelope[dict[str, bool]],
)
async def delete_revision_item(
    request: Request,
    revision_request_id: UUID,
    item_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
) -> SuccessEnvelope[dict[str, bool]]:
    await service.delete_item(revision_request_id, item_id, actor)
    return typed_envelope(request, {"deleted": True})


@router.post(
    "/revision-requests/{revision_request_id}/send",
    response_model=SuccessEnvelope[RevisionMutationResponse],
)
async def send_revision_request(
    request: Request,
    revision_request_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[RevisionMutationResponse]:
    return typed_envelope(request, await service.send(revision_request_id, actor, idempotency_key))


@router.post(
    "/revision-requests/{revision_request_id}/decide",
    response_model=SuccessEnvelope[RevisionMutationResponse],
)
async def decide_revision_request(
    request: Request,
    revision_request_id: UUID,
    payload: RevisionDecisionRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    idempotency_key: IdempotencyKey,
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[RevisionMutationResponse]:
    return typed_envelope(
        request,
        await service.decide(revision_request_id, actor, organization_id, payload, idempotency_key),
    )


@router.post(
    "/revision-requests/{revision_request_id}/reject-all",
    response_model=SuccessEnvelope[RevisionMutationResponse],
)
async def reject_all_revision_items(
    request: Request,
    revision_request_id: UUID,
    payload: RevisionDecisionRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    idempotency_key: IdempotencyKey,
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[RevisionMutationResponse]:
    return typed_envelope(
        request,
        await service.reject_all(
            revision_request_id, actor, organization_id, payload, idempotency_key
        ),
    )


@router.post(
    "/revision-requests/{revision_request_id}/respond",
    response_model=SuccessEnvelope[RevisionMutationResponse],
)
async def respond_to_revision_decision(
    request: Request,
    revision_request_id: UUID,
    payload: RevisionResponseRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RevisionService, Depends(get_revision_service)],
    idempotency_key: IdempotencyKey,
) -> SuccessEnvelope[RevisionMutationResponse]:
    return typed_envelope(
        request,
        await service.respond(revision_request_id, actor, payload, idempotency_key),
    )
