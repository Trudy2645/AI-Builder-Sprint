from __future__ import annotations

from uuid import UUID

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.integrations.modusign import ModusignClient, ModusignParticipant, ModusignParticipantField
from app.integrations.storage import (
    StorageObjectNotFoundError,
    StorageProvider,
    StorageProviderError,
)
from app.repositories.document_processing import DocumentProcessingRepository
from app.schemas.modusign import SignatureRequestFromDocumentCreate, SignatureRequestResponse


class ModusignService:
    """Coordinates seller authorization, source-PDF loading, and signing."""

    def __init__(
        self,
        repository: DocumentProcessingRepository,
        storage: StorageProvider,
        client: ModusignClient,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._client = client

    async def create_from_document(
        self,
        payload: SignatureRequestFromDocumentCreate,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> SignatureRequestResponse:
        try:
            document_id = UUID(payload.document_id)
        except ValueError as exc:
            raise AppError(
                status_code=400,
                code="DOCUMENT_ID_INVALID",
                message="document_id must be a valid UUID.",
            ) from exc

        record = await self._repository.get_document(document_id)
        if record is None:
            raise AppError(
                status_code=404, code="DOCUMENT_NOT_FOUND", message="Document not found."
            )
        if record.purpose != "source_contract":
            raise AppError(
                status_code=409,
                code="INVALID_DOCUMENT_PURPOSE",
                message="Only an uploaded source contract can be sent for signing.",
            )
        if record.status not in {"uploaded", "ready", "completed"}:
            raise AppError(
                status_code=409,
                code="DOCUMENT_NOT_READY",
                message="The source contract is not ready for signing.",
                details={"status": record.status},
            )
        if record.seller_organization_id is None:
            raise AppError(
                status_code=403,
                code="DOCUMENT_ACCESS_DENIED",
                message="Seller ownership could not be verified.",
            )
        if organization_header != str(record.seller_organization_id):
            raise AppError(
                status_code=403,
                code="DOCUMENT_ACCESS_DENIED",
                message="The organization does not own this document.",
            )
        membership = await self._repository.get_membership(actor.id, record.seller_organization_id)
        if membership is None or membership.organization_type != "seller":
            raise AppError(
                status_code=403,
                code="DOCUMENT_ACCESS_DENIED",
                message="Seller membership is required.",
            )
        if record.mime_type != "application/pdf":
            raise AppError(
                status_code=415,
                code="SOURCE_PDF_REQUIRED",
                message="Only PDF source contracts can be sent for signing.",
            )

        try:
            pdf_bytes = b"".join(
                [
                    chunk
                    async for chunk in self._storage.iter_object(
                        record.storage_bucket, record.storage_object_path
                    )
                ]
            )
        except StorageObjectNotFoundError as exc:
            raise AppError(
                status_code=404,
                code="SOURCE_FILE_NOT_FOUND",
                message="The original source file is not available.",
            ) from exc
        except StorageProviderError as exc:
            raise AppError(
                status_code=503,
                code="STORAGE_UNAVAILABLE",
                message="Could not read the original source file.",
            ) from exc

        raw = await self._client.create_signature_request_from_pdf(
            title=payload.title,
            pdf_bytes=pdf_bytes,
            buyer=ModusignParticipant(
                role=payload.buyer.role, name=payload.buyer.name, email=payload.buyer.email
            ),
            buyer_fields=[
                ModusignParticipantField(
                    field_type=field.field_type,
                    data_label=field.data_label,
                    position=field.position,
                    size=field.size,
                    required=field.required,
                )
                for field in payload.fields
            ],
        )
        return SignatureRequestResponse(
            document_id=raw.get("id", ""),
            title=raw.get("title", payload.title),
            status=raw.get("status", "ON_PROCESSING"),
        )
