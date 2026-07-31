from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.dependencies import get_contract_service
from app.core.auth import get_current_user
from app.domain.contracts.service import ContractService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.contracts import (
    BuyerContractListItem,
    ContractBucket,
    ContractCancelResponse,
    ContractDetail,
    ContractRequestCreate,
    ContractRequestCreated,
    ContractVersionCompareResponse,
    ContractVersionListItem,
    SellerContractListItem,
    SellerDashboard,
)

router = APIRouter(tags=["contracts"])


@router.post(
    "/listings/{listing_id}/contract-requests",
    response_model=SuccessEnvelope[ContractRequestCreated],
)
async def create_contract_request(
    request: Request,
    listing_id: UUID,
    payload: ContractRequestCreate,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> SuccessEnvelope[ContractRequestCreated]:
    created = await service.create_request(listing_id, actor, payload, idempotency_key)
    return typed_envelope(request, created)


@router.get("/contracts/{contract_id}", response_model=SuccessEnvelope[ContractDetail])
async def get_contract(
    request: Request,
    contract_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractDetail]:
    contract = await service.get_contract(contract_id, actor, organization_id)
    return typed_envelope(request, contract)


@router.get(
    "/contracts/{contract_id}/versions",
    response_model=SuccessEnvelope[list[ContractVersionListItem]],
)
async def list_contract_versions(
    request: Request,
    contract_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[list[ContractVersionListItem]]:
    versions = await service.list_contract_versions(contract_id, actor, organization_id)
    return typed_envelope(request, versions)


@router.get(
    "/contracts/{contract_id}/versions/compare",
    response_model=SuccessEnvelope[ContractVersionCompareResponse],
)
async def compare_contract_versions(
    request: Request,
    contract_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    from_version: Annotated[int, Query(alias="from", gt=0)],
    to_version: Annotated[int, Query(alias="to", gt=0)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractVersionCompareResponse]:
    comparison = await service.compare_contract_versions(
        contract_id, from_version, to_version, actor, organization_id
    )
    return typed_envelope(request, comparison)


@router.get("/me/contracts", response_model=SuccessEnvelope[list[BuyerContractListItem]])
async def list_my_contracts(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    bucket: Annotated[ContractBucket | None, Query()] = None,
) -> SuccessEnvelope[list[BuyerContractListItem]]:
    return typed_envelope(request, await service.list_my_contracts(actor, bucket))


@router.get(
    "/seller/contracts/received",
    response_model=SuccessEnvelope[list[SellerContractListItem]],
)
async def list_received_contracts(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[list[SellerContractListItem]]:
    contracts = await service.list_received_contracts(actor, organization_id)
    return typed_envelope(request, contracts)


@router.get("/seller/dashboard", response_model=SuccessEnvelope[SellerDashboard])
async def get_seller_dashboard(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[SellerDashboard]:
    dashboard = await service.get_seller_dashboard(actor, organization_id)
    return typed_envelope(request, dashboard)


@router.post(
    "/contracts/{contract_id}/cancel",
    response_model=SuccessEnvelope[ContractCancelResponse],
)
async def cancel_contract(
    request: Request,
    contract_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractCancelResponse]:
    cancelled = await service.cancel_contract(contract_id, actor, organization_id, idempotency_key)
    return typed_envelope(request, cancelled)
