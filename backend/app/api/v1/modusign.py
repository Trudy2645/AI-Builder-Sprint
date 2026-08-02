from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.api.dependencies import get_modusign_client, get_modusign_service
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.domain.modusign.service import ModusignService
from app.integrations.auth import AuthenticatedUser
from app.integrations.modusign import (
    ModusignClient,
    ModusignNotFoundError,
    ModusignParticipant,
    ModusignRequestError,
    ModusignUnavailableError,
)
from app.schemas.common import SuccessEnvelope, typed_envelope
from app.schemas.modusign import (
    DocumentFile,
    DocumentStatusResponse,
    SignatureRequestCreate,
    SignatureRequestFromDocumentCreate,
    SignatureRequestResponse,
)

router = APIRouter(prefix="/modusign", tags=["modusign"])


def _handle_modusign_error(exc: Exception) -> AppError:
    if isinstance(exc, ModusignNotFoundError):
        return AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODUSIGN_DOCUMENT_NOT_FOUND",
            message="The requested signature document was not found in Modusign.",
        )
    if isinstance(exc, ModusignRequestError):
        return AppError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="MODUSIGN_REQUEST_REJECTED",
            message="Modusign rejected the request. Check the template id and participant details.",
            details={"modusign_status_code": exc.status_code, "modusign_detail": exc.detail},
        )
    if isinstance(exc, ModusignUnavailableError):
        return AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODUSIGN_UNAVAILABLE",
            message="Could not reach Modusign. Please try again shortly.",
        )
    return AppError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="MODUSIGN_UNKNOWN_ERROR",
        message="An unexpected error occurred while talking to Modusign.",
    )


def _to_status_response(document_id: str, raw: dict[str, Any]) -> DocumentStatusResponse:
    file_info = raw.get("file") or {}
    audit_info = raw.get("auditTrail") or {}
    return DocumentStatusResponse(
        document_id=raw.get("id", document_id),
        status=raw.get("status", "ON_PROCESSING"),
        current_signing_order=raw.get("currentSigningOrder"),
        file=DocumentFile(download_url=file_info.get("downloadUrl")),
        audit_trail=DocumentFile(download_url=audit_info.get("downloadUrl")),
    )


@router.post("/requests", response_model=SuccessEnvelope[SignatureRequestResponse])
async def create_signature_request(
    request: Request,
    payload: SignatureRequestCreate,
    _actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SuccessEnvelope[SignatureRequestResponse]:
    if not settings.modusign_template_id:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODUSIGN_TEMPLATE_NOT_CONFIGURED",
            message="MODUSIGN_TEMPLATE_ID is not configured on the server.",
        )

    try:
        raw = await client.create_signature_request(
            template_id=settings.modusign_template_id,
            title=payload.title,
            participants=[
                ModusignParticipant(
                    role=payload.buyer.role, name=payload.buyer.name, email=payload.buyer.email
                )
            ],
        )
    except (ModusignNotFoundError, ModusignRequestError, ModusignUnavailableError) as exc:
        raise _handle_modusign_error(exc) from exc

    result = SignatureRequestResponse(
        document_id=raw.get("id", ""),
        title=raw.get("title", payload.title),
        status=raw.get("status", "ON_PROCESSING"),
    )
    return typed_envelope(request, result)


@router.post("/requests/from-document", response_model=SuccessEnvelope[SignatureRequestResponse])
async def create_signature_request_from_document(
    request: Request,
    payload: SignatureRequestFromDocumentCreate,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ModusignService, Depends(get_modusign_service)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
) -> SuccessEnvelope[SignatureRequestResponse]:
    try:
        result = await service.create_from_document(payload, actor, organization_id)
    except (ModusignNotFoundError, ModusignRequestError, ModusignUnavailableError) as exc:
        raise _handle_modusign_error(exc) from exc
    return typed_envelope(request, result)


@router.get(
    "/documents/{document_id}",
    response_model=SuccessEnvelope[DocumentStatusResponse],
)
async def get_document_status(
    request: Request,
    document_id: str,
    _actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
) -> SuccessEnvelope[DocumentStatusResponse]:
    try:
        raw = await client.get_document(document_id)
    except (ModusignNotFoundError, ModusignRequestError, ModusignUnavailableError) as exc:
        raise _handle_modusign_error(exc) from exc

    return typed_envelope(request, _to_status_response(document_id, raw))


@router.get("/documents/{document_id}/download")
async def download_signed_document(
    document_id: str,
    _actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
) -> Response:
    return await _stream_document_file(document_id, client, kind="file", filename_suffix="signed")


@router.get("/documents/{document_id}/audit-trail")
async def download_audit_trail(
    document_id: str,
    _actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
) -> Response:
    return await _stream_document_file(
        document_id, client, kind="auditTrail", filename_suffix="audit-trail"
    )


async def _stream_document_file(
    document_id: str,
    client: ModusignClient,
    *,
    kind: str,
    filename_suffix: str,
) -> Response:
    try:
        raw = await client.get_document(document_id)
    except (ModusignNotFoundError, ModusignRequestError, ModusignUnavailableError) as exc:
        raise _handle_modusign_error(exc) from exc

    if raw.get("status") != "COMPLETED":
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="MODUSIGN_DOCUMENT_NOT_COMPLETED",
            message="Both parties must finish signing before this file is available.",
            details={"status": raw.get("status", "UNKNOWN")},
        )

    download_url = (raw.get(kind) or {}).get("downloadUrl")
    if not download_url:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODUSIGN_FILE_NOT_AVAILABLE",
            message="Modusign has not published a download link for this file yet.",
        )

    try:
        content, content_type = await client.fetch_file(download_url)
    except (ModusignNotFoundError, ModusignRequestError, ModusignUnavailableError) as exc:
        raise _handle_modusign_error(exc) from exc

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document_id}-{filename_suffix}.pdf"'
        },
    )
