from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import get_document_service
from app.core.auth import get_current_user
from app.domain.documents.service import DocumentService
from app.integrations.auth import AuthenticatedUser
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.documents import (
    DocumentDownloadUrl,
    DocumentUploadUrl,
    DocumentUploadUrlRequest,
    DocumentView,
)

router = APIRouter(prefix="/documents", tags=["documents"])
OrganizationHeader = Annotated[str | None, Header(alias="X-Organization-Id")]


@router.post(
    "/upload-url",
    response_model=SuccessEnvelope[DocumentUploadUrl],
    status_code=status.HTTP_201_CREATED,
)
async def create_document_upload_url(
    request: Request,
    payload: DocumentUploadUrlRequest,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[DocumentUploadUrl]:
    result = await service.create_upload_url(payload, actor, organization_id, idempotency_key)
    return typed_envelope(request, result)


@router.post(
    "/{document_id}/complete",
    response_model=SuccessEnvelope[DocumentView],
)
async def complete_document_upload(
    request: Request,
    document_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[DocumentView]:
    result = await service.complete(document_id, actor, organization_id)
    return typed_envelope(request, result)


@router.get("/{document_id}", response_model=SuccessEnvelope[DocumentView])
async def get_document(
    request: Request,
    document_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[DocumentView]:
    return typed_envelope(request, await service.get(document_id, actor, organization_id))


@router.post(
    "/{document_id}/download-url",
    response_model=SuccessEnvelope[DocumentDownloadUrl],
)
async def create_document_download_url(
    request: Request,
    document_id: UUID,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    organization_id: OrganizationHeader = None,
) -> SuccessEnvelope[DocumentDownloadUrl]:
    result = await service.create_download_url(document_id, actor, organization_id)
    return typed_envelope(request, result)
