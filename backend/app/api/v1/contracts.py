from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status

from app.api.dependencies import (
    get_contract_review_service,
    get_contract_service,
    get_modusign_client,
    get_storage_provider,
)
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.domain.contract_review.service import ContractReviewService
from app.domain.contracts.service import ContractService
from app.integrations.auth import AuthenticatedUser
from app.integrations.modusign import ModusignClient
from app.integrations.storage import StorageProvider
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.contract_review import ContractReviewAccepted, ContractReviewRequest
from app.schemas.contracts import (
    BuyerContractListItem,
    ContractBucket,
    ContractCancelResponse,
    ContractDetail,
    ContractRequestCreate,
    ContractRequestCreated,
    ContractSignatureRequestCreate,
    ContractVersionApprovalsResponse,
    ContractVersionApproveResponse,
    ContractVersionCompareResponse,
    ContractVersionListItem,
    SellerContractListItem,
    SellerDashboard,
    SignatureRequestCreated,
)

router = APIRouter(tags=["contracts"])


@router.post(
    "/contracts/{contract_id}/analyses",
    response_model=SuccessEnvelope[ContractReviewAccepted],
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_contract_version(
    request: Request,
    contract_id: UUID,
    payload: ContractReviewRequest,
    background_tasks: BackgroundTasks,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractReviewService, Depends(get_contract_review_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractReviewAccepted]:
    started = await service.start_contract_review(
        contract_id, payload, actor, organization_id, idempotency_key
    )
    if started.should_schedule:
        background_tasks.add_task(
            service.run,
            job_id=started.response.job_id,
            target=started.target,
            viewer_role=started.viewer_role,
        )
    return typed_envelope(request, started.response)


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


@router.post(
    "/contracts/{contract_id}/versions/{version_id}/approve",
    response_model=SuccessEnvelope[ContractVersionApproveResponse],
)
async def approve_contract_version(
    request: Request,
    contract_id: UUID,
    version_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractVersionApproveResponse]:
    approval = await service.approve_contract_version(
        contract_id, version_id, actor, organization_id
    )
    return typed_envelope(request, approval)


@router.get(
    "/contracts/{contract_id}/versions/{version_id}/approvals",
    response_model=SuccessEnvelope[ContractVersionApprovalsResponse],
)
async def get_contract_version_approvals(
    request: Request,
    contract_id: UUID,
    version_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[ContractVersionApprovalsResponse]:
    approvals = await service.get_contract_version_approvals(
        contract_id, version_id, actor, organization_id
    )
    return typed_envelope(request, approvals)


@router.post(
    "/contracts/{contract_id}/versions/{version_id}/signature-requests",
    response_model=SuccessEnvelope[SignatureRequestCreated],
)
async def create_contract_signature_request(
    request: Request,
    contract_id: UUID,
    version_id: UUID,
    payload: ContractSignatureRequestCreate,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[SignatureRequestCreated]:
    result = await service.create_signature_request(
        contract_id,
        version_id,
        payload,
        actor,
        organization_id,
        idempotency_key,
        client,
        settings.modusign_template_id,
    )
    return typed_envelope(request, result)


@router.get(
    "/signature-requests/{signature_request_id}",
    response_model=SuccessEnvelope[SignatureRequestCreated],
)
async def get_contract_signature_request(
    request: Request,
    signature_request_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[SignatureRequestCreated]:
    return typed_envelope(
        request, await service.get_signature_request(signature_request_id, actor, organization_id)
    )


@router.post(
    "/signature-requests/{signature_request_id}/sync",
    response_model=SuccessEnvelope[SignatureRequestCreated],
)
async def sync_contract_signature_request(
    request: Request,
    signature_request_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[SignatureRequestCreated]:
    return typed_envelope(
        request,
        await service.sync_signature_request(
            signature_request_id, actor, organization_id, client, storage
        ),
    )


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
