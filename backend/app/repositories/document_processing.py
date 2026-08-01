from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProcessingDocumentRecord:
    id: UUID
    listing_id: UUID | None
    contract_id: UUID | None
    purpose: str
    status: str
    storage_bucket: str
    storage_object_path: str
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    content_sha256: str | None
    failure_code: str | None
    extracted_data: dict[str, Any]
    uploaded_by: UUID | None
    seller_organization_id: UUID | None
    listing_title: str | None
    listing_category: str | None
    listing_language: str | None


@dataclass(frozen=True, slots=True)
class ProcessingMembershipRecord:
    organization_id: UUID
    organization_type: str


@dataclass(frozen=True, slots=True)
class ProcessingJobRecord:
    id: UUID
    job_type: str
    status: str
    result_metadata: dict[str, Any]
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentProcessingRepositoryError(Exception):
    pass


class DocumentProcessingRepository(Protocol):
    async def get_document(self, document_id: UUID) -> ProcessingDocumentRecord | None: ...

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> ProcessingMembershipRecord | None: ...

    async def ensure_job(
        self,
        *,
        document_id: UUID,
        job_type: str,
        idempotency_base: str,
        provider: str,
        model_name: str,
        prompt_version: str | None,
    ) -> ProcessingJobRecord: ...

    async def mark_document_processing(self, document_id: UUID) -> None: ...

    async def mark_job_processing(self, job_id: UUID) -> None: ...

    async def create_parse_artifact(
        self,
        *,
        artifact_id: UUID,
        source: ProcessingDocumentRecord,
        storage_bucket: str,
        storage_object_path: str,
        size_bytes: int,
        content_sha256: str,
    ) -> None: ...

    async def mark_job_succeeded(self, job_id: UUID, result_metadata: dict[str, Any]) -> None: ...

    async def save_extraction(
        self,
        *,
        document_id: UUID,
        job_id: UUID,
        extracted_data: dict[str, Any],
        result_metadata: dict[str, Any],
    ) -> None: ...

    async def mark_failed(self, document_id: UUID, job_id: UUID, failure_code: str) -> None: ...


class SqlAlchemyDocumentProcessingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_document(self, document_id: UUID) -> ProcessingDocumentRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select d.id, d.listing_id, d.contract_id, d.purpose::text, d.status::text,
                           d.storage_bucket, d.storage_object_path, d.original_filename,
                           d.mime_type, d.size_bytes, d.content_sha256, d.failure_code,
                           d.extracted_data,
                           d.uploaded_by, l.seller_organization_id, l.title as listing_title,
                           l.category::text as listing_category,
                           l.language::text as listing_language
                    from public.documents d
                    left join public.listings l on l.id = d.listing_id
                    where d.id = :document_id
                    """
                ),
                {"document_id": document_id},
            )
            row = result.mappings().one_or_none()
            return ProcessingDocumentRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> ProcessingMembershipRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.organization_type::text
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id and om.organization_id = :organization_id
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            row = result.mappings().one_or_none()
            return ProcessingMembershipRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc

    async def ensure_job(
        self,
        *,
        document_id: UUID,
        job_type: str,
        idempotency_base: str,
        provider: str,
        model_name: str,
        prompt_version: str | None,
    ) -> ProcessingJobRecord:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing_result = await self._session.execute(
                    text(
                        """
                        select id, job_type, status::text, result_metadata, failure_code,
                               created_at, started_at, completed_at
                        from public.ai_jobs
                        where document_id = :document_id and job_type = :job_type
                          and model_name = :model_name
                          and prompt_version is not distinct from :prompt_version
                        order by created_at desc
                        for update
                        """
                    ),
                    {
                        "document_id": document_id,
                        "job_type": job_type,
                        "model_name": model_name,
                        "prompt_version": prompt_version,
                    },
                )
                rows = existing_result.mappings().all()
                if rows and rows[0]["status"] != "failed":
                    return ProcessingJobRecord(**rows[0])
                retry_no = len(rows)
                job_id = uuid4()
                idempotency_key = (
                    idempotency_base if retry_no == 0 else f"{idempotency_base}:retry:{retry_no}"
                )
                inserted = await self._session.execute(
                    text(
                        """
                        insert into public.ai_jobs (
                            id, document_id, job_type, idempotency_key, provider,
                            model_name, prompt_version, result_metadata
                        ) values (
                            :id, :document_id, :job_type, :idempotency_key, :provider,
                            :model_name, :prompt_version, cast(:result_metadata as jsonb)
                        )
                        on conflict (idempotency_key) do nothing
                        returning id, job_type, status::text, result_metadata, failure_code,
                                  created_at, started_at, completed_at
                        """
                    ),
                    {
                        "id": job_id,
                        "document_id": document_id,
                        "job_type": job_type,
                        "idempotency_key": idempotency_key,
                        "provider": provider,
                        "model_name": model_name,
                        "prompt_version": prompt_version,
                        "result_metadata": json.dumps({"retry_no": retry_no}),
                    },
                )
                row = inserted.mappings().one_or_none()
                if row is None:
                    selected = await self._session.execute(
                        text(
                            """
                            select id, job_type, status::text, result_metadata, failure_code,
                                   created_at, started_at, completed_at
                            from public.ai_jobs where idempotency_key = :idempotency_key
                            """
                        ),
                        {"idempotency_key": idempotency_key},
                    )
                    row = selected.mappings().one()
                return ProcessingJobRecord(**row)
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc

    async def mark_document_processing(self, document_id: UUID) -> None:
        await self._execute_commit(
            """
            update public.documents
            set status = 'processing', failure_code = null
            where id = :document_id
              and status in ('uploaded', 'processing', 'ready', 'failed')
            """,
            {"document_id": document_id},
        )

    async def mark_job_processing(self, job_id: UUID) -> None:
        await self._execute_commit(
            """
            update public.ai_jobs
            set status = 'processing', started_at = coalesce(started_at, now()),
                attempt_count = attempt_count + 1, provider_status = 'processing',
                failure_code = null, failure_message = null
            where id = :job_id and status = 'queued'
            """,
            {"job_id": job_id},
        )

    async def create_parse_artifact(
        self,
        *,
        artifact_id: UUID,
        source: ProcessingDocumentRecord,
        storage_bucket: str,
        storage_object_path: str,
        size_bytes: int,
        content_sha256: str,
    ) -> None:
        try:
            await self._session.execute(
                text(
                    """
                    insert into public.documents (
                        id, listing_id, contract_id, purpose, status, storage_bucket,
                        storage_object_path, original_filename, mime_type, size_bytes,
                        content_sha256, expected_mime_type, expected_size_bytes,
                        expected_content_sha256, uploaded_by
                    ) values (
                        :id, :listing_id, :contract_id, 'parsed_artifact', 'ready',
                        :storage_bucket, :storage_object_path, :original_filename,
                        'application/json', :size_bytes, :content_sha256,
                        'application/json', :size_bytes, :content_sha256, :uploaded_by
                    )
                    """
                ),
                {
                    "id": artifact_id,
                    "listing_id": source.listing_id,
                    "contract_id": source.contract_id,
                    "storage_bucket": storage_bucket,
                    "storage_object_path": storage_object_path,
                    "original_filename": f"{source.id}.document-parse.json",
                    "size_bytes": size_bytes,
                    "content_sha256": content_sha256,
                    "uploaded_by": source.uploaded_by,
                },
            )
            await self._session.commit()
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc

    async def mark_job_succeeded(self, job_id: UUID, result_metadata: dict[str, Any]) -> None:
        await self._execute_commit(
            """
            update public.ai_jobs
            set status = 'succeeded', completed_at = now(), provider_status = 'succeeded',
                result_metadata = result_metadata || cast(:result_metadata as jsonb)
            where id = :job_id and status in ('queued', 'processing')
            """,
            {"job_id": job_id, "result_metadata": json.dumps(result_metadata)},
        )

    async def save_extraction(
        self,
        *,
        document_id: UUID,
        job_id: UUID,
        extracted_data: dict[str, Any],
        result_metadata: dict[str, Any],
    ) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        update public.documents
                        set status = 'ready', extracted_data = cast(:extracted_data as jsonb),
                            failure_code = null
                        where id = :document_id
                        """
                    ),
                    {
                        "document_id": document_id,
                        "extracted_data": json.dumps(extracted_data, ensure_ascii=False),
                    },
                )
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs
                        set status = 'succeeded', completed_at = now(),
                            provider_status = 'succeeded',
                            result_metadata = result_metadata || cast(:result_metadata as jsonb)
                        where id = :job_id and status in ('queued', 'processing')
                        """
                    ),
                    {"job_id": job_id, "result_metadata": json.dumps(result_metadata)},
                )
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc

    async def mark_failed(self, document_id: UUID, job_id: UUID, failure_code: str) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs
                        set status = 'failed', completed_at = now(), provider_status = 'failed',
                            failure_code = :failure_code, failure_message = null
                        where id = :job_id and status in ('queued', 'processing')
                        """
                    ),
                    {"job_id": job_id, "failure_code": failure_code},
                )
                await self._session.execute(
                    text(
                        """
                        update public.documents set status = 'failed', failure_code = :failure_code
                        where id = :document_id
                        """
                    ),
                    {"document_id": document_id, "failure_code": failure_code},
                )
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc

    async def _execute_commit(self, statement: str, parameters: dict[str, Any]) -> None:
        try:
            await self._session.execute(text(statement), parameters)
            await self._session.commit()
        except SQLAlchemyError as exc:
            raise DocumentProcessingRepositoryError from exc
