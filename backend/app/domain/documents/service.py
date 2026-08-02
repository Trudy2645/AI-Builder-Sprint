import hashlib
import json
import tempfile
import zipfile
from pathlib import PurePath
from typing import BinaryIO
from uuid import UUID, uuid4

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.integrations.storage import (
    StorageObjectNotFoundError,
    StorageProvider,
    StorageProviderError,
)
from app.repositories.documents import (
    DocumentIdempotencyConflictError,
    DocumentMembershipRecord,
    DocumentRecord,
    DocumentRepository,
    DocumentRepositoryError,
)
from app.schemas.documents import (
    DocumentDownloadUrl,
    DocumentPurpose,
    DocumentUploadUrl,
    DocumentUploadUrlRequest,
    DocumentView,
)

_ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: StorageProvider,
        *,
        max_size_bytes: int,
        download_url_expires_seconds: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_size_bytes = max_size_bytes
        self._download_url_expires_seconds = download_url_expires_seconds

    async def create_upload_url(
        self,
        payload: DocumentUploadUrlRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> DocumentUploadUrl:
        extension, mime_type = self._validate_upload_metadata(payload)
        await self._authorize_new_owner(payload, actor, organization_header)
        document_id = uuid4()
        bucket = self._bucket_for(payload.purpose)
        owner_type, owner_id = self._owner(payload)
        object_path = f"{owner_type}/{owner_id}/{document_id}/{uuid4().hex}{extension}"
        request_hash = hashlib.sha256(
            json.dumps(
                payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        try:
            record = await self._repository.create_pending_document(
                document_id=document_id,
                actor_user_id=actor.id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                organization_id=payload.organization_id,
                listing_id=payload.listing_id,
                contract_id=payload.contract_id,
                purpose=payload.purpose.value,
                storage_bucket=bucket,
                storage_object_path=object_path,
                original_filename=payload.original_filename,
                expected_mime_type=mime_type,
                expected_size_bytes=payload.size_bytes,
                expected_content_sha256=payload.content_sha256,
            )
        except DocumentIdempotencyConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_CONFLICT",
                message="The Idempotency-Key was already used with a different request.",
            ) from exc
        except DocumentRepositoryError as exc:
            self._database_unavailable(exc)
        try:
            upload_url, expires_at = await self._storage.create_signed_upload_url(
                record.storage_bucket, record.storage_object_path
            )
        except StorageProviderError as exc:
            self._storage_unavailable(exc)
        return DocumentUploadUrl(
            document=self._view(record), upload_url=upload_url, expires_at=expires_at
        )

    async def complete(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> DocumentView:
        record = await self._get_authorized(document_id, actor, organization_header)
        if record.status in {"uploaded", "processing", "ready"}:
            return self._view(record)
        if record.status == "failed":
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DOCUMENT_VALIDATION_FAILED",
                message="The uploaded document has already failed validation.",
                details={"failure_code": record.failure_code},
            )
        digest = hashlib.sha256()
        size_bytes = 0
        signature = bytearray()
        docx_file: BinaryIO | None = None
        if record.expected_mime_type == _ALLOWED_TYPES[".docx"]:
            docx_file = tempfile.TemporaryFile()
        try:
            try:
                async for chunk in self._storage.iter_object(
                    record.storage_bucket, record.storage_object_path
                ):
                    size_bytes += len(chunk)
                    if size_bytes > self._max_size_bytes:
                        await self._fail(record.id, "FILE_TOO_LARGE")
                        raise AppError(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            code="FILE_TOO_LARGE",
                            message="The uploaded file exceeds the maximum allowed size.",
                        )
                    if len(signature) < 16:
                        signature.extend(chunk[: 16 - len(signature)])
                    if docx_file is not None:
                        docx_file.write(chunk)
                    digest.update(chunk)
            except StorageObjectNotFoundError as exc:
                raise AppError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="STORAGE_OBJECT_NOT_FOUND",
                    message="The file has not been uploaded to Storage.",
                ) from exc
            except StorageProviderError as exc:
                self._storage_unavailable(exc)
            detected_mime = self._detect_mime(bytes(signature), docx_file)
        finally:
            if docx_file is not None:
                docx_file.close()
        if detected_mime != record.expected_mime_type:
            await self._fail(record.id, "MIME_TYPE_MISMATCH")
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="MIME_TYPE_MISMATCH",
                message="The uploaded file content does not match its declared MIME type.",
            )
        if size_bytes != record.expected_size_bytes:
            await self._fail(record.id, "FILE_SIZE_MISMATCH")
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="FILE_SIZE_MISMATCH",
                message="The uploaded file size does not match the declared size.",
            )
        content_sha256 = digest.hexdigest()
        if content_sha256 != record.expected_content_sha256:
            await self._fail(record.id, "FILE_HASH_MISMATCH")
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="FILE_HASH_MISMATCH",
                message="The uploaded file hash does not match the declared SHA-256.",
            )
        try:
            uploaded = await self._repository.mark_uploaded(
                record.id,
                mime_type=detected_mime,
                size_bytes=size_bytes,
                content_sha256=content_sha256,
            )
        except DocumentRepositoryError as exc:
            self._database_unavailable(exc)
        return self._view(uploaded)

    async def get(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> DocumentView:
        return self._view(await self._get_authorized(document_id, actor, organization_header))

    async def create_download_url(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> DocumentDownloadUrl:
        record = await self._get_authorized(document_id, actor, organization_header)
        if record.status not in {"uploaded", "processing", "ready"}:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DOCUMENT_NOT_READY",
                message="The document is not available for download.",
            )
        try:
            download_url, expires_at = await self._storage.create_signed_download_url(
                record.storage_bucket,
                record.storage_object_path,
                self._download_url_expires_seconds,
            )
        except StorageObjectNotFoundError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="STORAGE_OBJECT_NOT_FOUND",
                message="The document object is missing from Storage.",
            ) from exc
        except StorageProviderError as exc:
            self._storage_unavailable(exc)
        return DocumentDownloadUrl(
            document_id=record.id, download_url=download_url, expires_at=expires_at
        )

    def _validate_upload_metadata(self, payload: DocumentUploadUrlRequest) -> tuple[str, str]:
        if payload.size_bytes > self._max_size_bytes:
            raise AppError(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="FILE_TOO_LARGE",
                message="The file exceeds the maximum allowed size.",
                details={"max_size_bytes": self._max_size_bytes},
            )
        if (
            PurePath(payload.original_filename).name != payload.original_filename
            or "\\" in payload.original_filename
            or any(ord(character) < 32 for character in payload.original_filename)
        ):
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_FILENAME",
                message="The original filename is invalid.",
            )
        extension = PurePath(payload.original_filename).suffix.lower()
        expected_mime = _ALLOWED_TYPES.get(extension)
        if expected_mime is None or payload.mime_type.lower() != expected_mime:
            raise AppError(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                code="UNSUPPORTED_FILE_TYPE",
                message="Only PDF, DOCX, JPG, JPEG, and PNG files are allowed.",
            )
        if (
            payload.purpose is DocumentPurpose.LISTING_HERO
            and expected_mime not in _IMAGE_MIME_TYPES
        ):
            raise AppError(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                code="UNSUPPORTED_FILE_TYPE",
                message="Listing hero documents must be JPG, JPEG, or PNG images.",
            )
        return extension, expected_mime

    async def _authorize_new_owner(
        self,
        payload: DocumentUploadUrlRequest,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> None:
        try:
            if payload.organization_id is not None:
                if payload.purpose is not DocumentPurpose.BUSINESS_VERIFICATION:
                    self._invalid_owner_purpose()
                membership = await self._seller_membership(
                    actor.id, payload.organization_id, organization_header
                )
                if membership.role not in {"owner", "admin"}:
                    self._access_denied()
                return
            if payload.listing_id is not None:
                if payload.purpose not in {
                    DocumentPurpose.SOURCE_CONTRACT,
                    DocumentPurpose.REFERENCE,
                    DocumentPurpose.LISTING_HERO,
                }:
                    self._invalid_owner_purpose()
                owner_id = await self._repository.get_listing_organization_id(payload.listing_id)
                if owner_id is None:
                    self._owner_not_found()
                await self._seller_membership(actor.id, owner_id, organization_header)
                return
            if payload.purpose not in {
                DocumentPurpose.SOURCE_CONTRACT,
                DocumentPurpose.REFERENCE,
            }:
                self._invalid_owner_purpose()
            access = await self._repository.get_contract_access(payload.contract_id)  # type: ignore[arg-type]
            if access is None:
                self._owner_not_found()
            if access.buyer_user_id == actor.id:
                return
            await self._seller_membership(
                actor.id, access.seller_organization_id, organization_header
            )
        except DocumentRepositoryError as exc:
            self._database_unavailable(exc)

    async def _get_authorized(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> DocumentRecord:
        try:
            record = await self._repository.get_document(document_id)
            if record is None:
                raise AppError(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="DOCUMENT_NOT_FOUND",
                    message="Document not found.",
                )
            if record.organization_id is not None:
                membership = await self._seller_membership(
                    actor.id, record.organization_id, organization_header
                )
                if record.purpose == "business_verification" and membership.role not in {
                    "owner",
                    "admin",
                }:
                    self._access_denied()
                return record
            if record.listing_id is not None:
                owner_id = await self._repository.get_listing_organization_id(record.listing_id)
                if owner_id is None:
                    self._access_denied()
                await self._seller_membership(actor.id, owner_id, organization_header)
                return record
            access = await self._repository.get_contract_access(record.contract_id)  # type: ignore[arg-type]
            if access is None:
                self._access_denied()
            if access.buyer_user_id == actor.id:
                return record
            await self._seller_membership(
                actor.id, access.seller_organization_id, organization_header
            )
            return record
        except DocumentRepositoryError as exc:
            self._database_unavailable(exc)

    async def _seller_membership(
        self, actor_id: UUID, organization_id: UUID, organization_header: str | None
    ) -> DocumentMembershipRecord:
        if organization_header is None:
            self._access_denied("X-Organization-Id is required for seller document access.")
        try:
            header_id = UUID(organization_header)
        except (ValueError, AttributeError):
            self._access_denied("X-Organization-Id must be a valid UUID.")
        if header_id != organization_id:
            self._access_denied()
        membership = await self._repository.get_membership(actor_id, organization_id)
        if membership is None or membership.organization_type != "seller":
            self._access_denied()
        return membership

    async def _fail(self, document_id: UUID, failure_code: str) -> None:
        try:
            await self._repository.mark_failed(document_id, failure_code)
        except DocumentRepositoryError as exc:
            self._database_unavailable(exc)

    @staticmethod
    def _detect_mime(signature: bytes, docx_file: BinaryIO | None = None) -> str | None:
        if signature.startswith(b"%PDF-"):
            return "application/pdf"
        if signature.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if signature.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if signature.startswith(b"PK\x03\x04") and docx_file is not None:
            try:
                docx_file.seek(0)
                with zipfile.ZipFile(docx_file) as archive:
                    names = set(archive.namelist())
                if {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    return _ALLOWED_TYPES[".docx"]
            except (OSError, zipfile.BadZipFile):
                return None
        return None

    @staticmethod
    def _bucket_for(purpose: DocumentPurpose) -> str:
        if purpose is DocumentPurpose.LISTING_HERO:
            return "listing-assets"
        if purpose is DocumentPurpose.BUSINESS_VERIFICATION:
            return "business-verification"
        return "contract-documents"

    @staticmethod
    def _owner(payload: DocumentUploadUrlRequest) -> tuple[str, UUID]:
        if payload.organization_id is not None:
            return "organizations", payload.organization_id
        if payload.listing_id is not None:
            return "listings", payload.listing_id
        return "contracts", payload.contract_id  # type: ignore[return-value]

    @staticmethod
    def _view(record: DocumentRecord) -> DocumentView:
        return DocumentView(
            id=record.id,
            organization_id=record.organization_id,
            listing_id=record.listing_id,
            contract_id=record.contract_id,
            purpose=record.purpose,
            status=record.status,
            original_filename=record.original_filename,
            mime_type=record.mime_type or record.expected_mime_type,
            size_bytes=record.size_bytes or record.expected_size_bytes,
            content_sha256=record.content_sha256,
            failure_code=record.failure_code,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _access_denied(message: str = "You do not have access to this document.") -> None:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="DOCUMENT_ACCESS_DENIED",
            message=message,
        )

    @staticmethod
    def _owner_not_found() -> None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DOCUMENT_OWNER_NOT_FOUND",
            message="The document owner resource was not found.",
        )

    @staticmethod
    def _invalid_owner_purpose() -> None:
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_DOCUMENT_OWNER",
            message="The document purpose is not valid for the selected owner.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="The database is temporarily unavailable.",
        ) from exc

    @staticmethod
    def _storage_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="STORAGE_PROVIDER_UNAVAILABLE",
            message="The Storage provider is temporarily unavailable.",
        ) from exc
