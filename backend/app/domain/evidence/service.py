from __future__ import annotations

from typing import NoReturn
from urllib.parse import urlencode
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.integrations.storage import StorageProvider, StorageProviderError
from app.repositories.evidence import EvidenceRecord, EvidenceRepository, EvidenceRepositoryError
from app.schemas.evidence import EvidenceDetailResponse


class EvidenceService:
    def __init__(
        self,
        repository: EvidenceRepository,
        storage: StorageProvider,
        *,
        storage_bucket: str,
        viewer_url_prefix: str,
        signed_url_expires_seconds: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._bucket = storage_bucket
        self._viewer_prefix = viewer_url_prefix.rstrip("/")
        self._expires_seconds = signed_url_expires_seconds

    async def get_evidence(
        self,
        finding_id: UUID,
        evidence_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> EvidenceDetailResponse:
        try:
            record = await self._repository.get_evidence(finding_id, evidence_id)
        except EvidenceRepositoryError as exc:
            self._database_unavailable(exc)
        if record is None:
            self._not_found()
        await self._authorize(record, actor, organization_header)
        try:
            signed_url, expires_at = await self._storage.create_signed_download_url(
                self._bucket, record.storage_object_path, self._expires_seconds
            )
        except StorageProviderError as exc:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="STORAGE_PROVIDER_UNAVAILABLE",
                message="The evidence document is temporarily unavailable.",
            ) from exc
        query = urlencode({"page": record.page_start, "evidence": str(record.evidence_id)})
        source_kind = {
            "official": "official",
            "template": "template",
            "case_reference": "case_reference",
        }[record.corpus_type]
        return EvidenceDetailResponse(
            evidence_id=record.evidence_id,
            finding_id=record.finding_id,
            document_version_id=record.document_version_id,
            document_title=record.document_title,
            source_kind=source_kind,  # type: ignore[arg-type]
            authority=record.authority,
            official_source_url=record.official_source_url,  # type: ignore[arg-type]
            effective_from=record.effective_from,
            retrieved_at=record.retrieved_at,
            page_start=record.page_start,
            page_end=record.page_end,
            section=record.section_path,
            bbox=record.bbox,
            excerpt=record.excerpt,
            viewer_url=f"{self._viewer_prefix}/{record.document_version_id}/view?{query}",
            signed_pdf_url=signed_url,
            signed_url_expires_at=expires_at,
        )

    async def _authorize(
        self,
        record: EvidenceRecord,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> None:
        if record.buyer_user_id == actor.id:
            return
        if (
            record.buyer_user_id is None
            and record.viewer_role == "buyer"
            and record.is_public
            and record.listing_status in {"published", "paused"}
        ):
            return
        if organization_header:
            try:
                organization_id = UUID(organization_header)
            except ValueError:
                self._forbidden()
            if organization_id == record.seller_organization_id:
                try:
                    if await self._repository.is_seller_member(actor.id, organization_id):
                        return
                except EvidenceRepositoryError as exc:
                    self._database_unavailable(exc)
        self._forbidden()

    @staticmethod
    def _not_found() -> NoReturn:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="EVIDENCE_NOT_FOUND",
            message="Evidence was not found for this finding.",
        )

    @staticmethod
    def _forbidden() -> NoReturn:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="You do not have access to this evidence.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="The database is unavailable.",
        ) from exc


__all__ = ["EvidenceService"]
