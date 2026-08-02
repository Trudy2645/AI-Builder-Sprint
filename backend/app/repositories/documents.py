from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class DocumentMembershipRecord:
    organization_id: UUID
    organization_type: str
    role: str


@dataclass(frozen=True, slots=True)
class ContractDocumentAccessRecord:
    buyer_user_id: UUID
    seller_organization_id: UUID


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: UUID
    organization_id: UUID | None
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
    expected_mime_type: str
    expected_size_bytes: int
    expected_content_sha256: str
    failure_code: str | None
    created_at: datetime
    updated_at: datetime


class DocumentRepositoryError(Exception):
    pass


class DocumentIdempotencyConflictError(Exception):
    pass


class DocumentRepository(Protocol):
    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> DocumentMembershipRecord | None: ...

    async def get_listing_organization_id(self, listing_id: UUID) -> UUID | None: ...

    async def get_contract_access(
        self, contract_id: UUID
    ) -> ContractDocumentAccessRecord | None: ...

    async def create_pending_document(
        self,
        *,
        document_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
        organization_id: UUID | None,
        listing_id: UUID | None,
        contract_id: UUID | None,
        purpose: str,
        storage_bucket: str,
        storage_object_path: str,
        original_filename: str,
        expected_mime_type: str,
        expected_size_bytes: int,
        expected_content_sha256: str,
    ) -> DocumentRecord: ...

    async def get_document(self, document_id: UUID) -> DocumentRecord | None: ...

    async def get_buyer_listing_document(
        self, listing_id: UUID, buyer_user_id: UUID
    ) -> DocumentRecord | None: ...

    async def mark_uploaded(
        self,
        document_id: UUID,
        *,
        mime_type: str,
        size_bytes: int,
        content_sha256: str,
    ) -> DocumentRecord: ...

    async def mark_failed(self, document_id: UUID, failure_code: str) -> None: ...


class SqlAlchemyDocumentRepository:
    _UPLOAD_OPERATION = "document_upload_url"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> DocumentMembershipRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.organization_type::text, om.role::text
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id and om.organization_id = :organization_id
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            row = result.mappings().one_or_none()
            return DocumentMembershipRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def get_listing_organization_id(self, listing_id: UUID) -> UUID | None:
        try:
            result = await self._session.execute(
                text("select seller_organization_id from public.listings where id = :id"),
                {"id": listing_id},
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def get_contract_access(self, contract_id: UUID) -> ContractDocumentAccessRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select buyer_user_id, seller_organization_id
                    from public.contracts where id = :id
                    """
                ),
                {"id": contract_id},
            )
            row = result.mappings().one_or_none()
            return ContractDocumentAccessRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def create_pending_document(
        self,
        *,
        document_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
        organization_id: UUID | None,
        listing_id: UUID | None,
        contract_id: UUID | None,
        purpose: str,
        storage_bucket: str,
        storage_object_path: str,
        original_filename: str,
        expected_mime_type: str,
        expected_size_bytes: int,
        expected_content_sha256: str,
    ) -> DocumentRecord:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing_id = await self._claim_idempotency(
                    actor_user_id, idempotency_key, request_hash
                )
                if existing_id is not None:
                    existing = await self._get_document(existing_id)
                    if existing is None:
                        raise DocumentRepositoryError
                    return existing
                await self._session.execute(
                    text(
                        """
                        insert into public.documents (
                            id, organization_id, listing_id, contract_id, purpose,
                            storage_bucket, storage_object_path, original_filename,
                            expected_mime_type, expected_size_bytes, expected_content_sha256,
                            uploaded_by
                        ) values (
                            :id, :organization_id, :listing_id, :contract_id,
                            cast(:purpose as public.document_purpose), :storage_bucket,
                            :storage_object_path, :original_filename, :expected_mime_type,
                            :expected_size_bytes, :expected_content_sha256, :actor_user_id
                        )
                        """
                    ),
                    {
                        "id": document_id,
                        "organization_id": organization_id,
                        "listing_id": listing_id,
                        "contract_id": contract_id,
                        "purpose": purpose,
                        "storage_bucket": storage_bucket,
                        "storage_object_path": storage_object_path,
                        "original_filename": original_filename,
                        "expected_mime_type": expected_mime_type,
                        "expected_size_bytes": expected_size_bytes,
                        "expected_content_sha256": expected_content_sha256,
                        "actor_user_id": actor_user_id,
                    },
                )
                await self._session.execute(
                    text(
                        """
                        update public.idempotency_records
                        set response_status = 201,
                            response_body = cast(:response_body as jsonb),
                            resource_type = 'document', resource_id = :document_id
                        where actor_user_id = :actor_user_id and operation = :operation
                          and idempotency_key = :key
                        """
                    ),
                    {
                        "response_body": json.dumps({"document_id": str(document_id)}),
                        "document_id": document_id,
                        "actor_user_id": actor_user_id,
                        "operation": self._UPLOAD_OPERATION,
                        "key": idempotency_key,
                    },
                )
            record = await self.get_document(document_id)
            if record is None:
                raise DocumentRepositoryError
            return record
        except DocumentIdempotencyConflictError:
            raise
        except DocumentRepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def get_document(self, document_id: UUID) -> DocumentRecord | None:
        try:
            return await self._get_document(document_id)
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def get_buyer_listing_document(
        self, listing_id: UUID, buyer_user_id: UUID
    ) -> DocumentRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select d.id, d.organization_id, d.listing_id, d.contract_id,
                           d.purpose::text, d.status::text, d.storage_bucket,
                           d.storage_object_path, d.original_filename, d.mime_type,
                           d.size_bytes, d.content_sha256, d.expected_mime_type,
                           d.expected_size_bytes, d.expected_content_sha256,
                           d.failure_code, d.created_at, d.updated_at
                    from public.listings l
                    join public.documents d on d.listing_id = l.id
                    join public.contracts c on c.listing_id = l.id
                    where l.id = :listing_id
                      and l.status = 'published'
                      and d.purpose = 'source_contract'
                      -- The original upload is safe to download as soon as it
                      -- passes upload verification.  AI processing changes its
                      -- analysis state, not the validity of the stored PDF.
                      and d.status in ('uploaded', 'ready')
                      and c.buyer_user_id = :buyer_user_id
                    order by d.created_at desc
                    limit 1
                    """
                ),
                {"listing_id": listing_id, "buyer_user_id": buyer_user_id},
            )
            row = result.mappings().one_or_none()
            return DocumentRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def mark_uploaded(
        self,
        document_id: UUID,
        *,
        mime_type: str,
        size_bytes: int,
        content_sha256: str,
    ) -> DocumentRecord:
        try:
            await self._session.execute(
                text(
                    """
                    update public.documents
                    set status = 'uploaded', mime_type = :mime_type,
                        size_bytes = :size_bytes, content_sha256 = :content_sha256,
                        failure_code = null
                    where id = :id and status = 'pending_upload'
                    """
                ),
                {
                    "id": document_id,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                    "content_sha256": content_sha256,
                },
            )
            await self._session.commit()
            record = await self._get_document(document_id)
            if record is None:
                raise DocumentRepositoryError
            return record
        except DocumentRepositoryError:
            raise
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def mark_failed(self, document_id: UUID, failure_code: str) -> None:
        try:
            await self._session.execute(
                text(
                    """
                    update public.documents set status = 'failed', failure_code = :failure_code
                    where id = :id and status = 'pending_upload'
                    """
                ),
                {"id": document_id, "failure_code": failure_code},
            )
            await self._session.commit()
        except SQLAlchemyError as exc:
            raise DocumentRepositoryError from exc

    async def _claim_idempotency(
        self, actor_user_id: UUID, key: str, request_hash: str
    ) -> UUID | None:
        await self._session.execute(
            text(
                """
                delete from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key and expires_at <= now()
                """
            ),
            {"actor_user_id": actor_user_id, "operation": self._UPLOAD_OPERATION, "key": key},
        )
        inserted = await self._session.execute(
            text(
                """
                insert into public.idempotency_records (
                    actor_user_id, operation, idempotency_key, request_hash, expires_at
                ) values (
                    :actor_user_id, :operation, :key, :request_hash, now() + interval '24 hours'
                )
                on conflict (actor_user_id, operation, idempotency_key)
                    where actor_user_id is not null
                do nothing returning id
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "operation": self._UPLOAD_OPERATION,
                "key": key,
                "request_hash": request_hash,
            },
        )
        if inserted.scalar_one_or_none() is not None:
            return None
        existing = await self._session.execute(
            text(
                """
                select request_hash, resource_id, response_body
                from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {"actor_user_id": actor_user_id, "operation": self._UPLOAD_OPERATION, "key": key},
        )
        row = existing.mappings().one()
        if row["request_hash"] != request_hash or row["response_body"] is None:
            raise DocumentIdempotencyConflictError
        return row["resource_id"]

    async def _get_document(self, document_id: UUID) -> DocumentRecord | None:
        result = await self._session.execute(
            text(
                """
                select id, organization_id, listing_id, contract_id, purpose::text, status::text,
                       storage_bucket, storage_object_path, original_filename, mime_type,
                       size_bytes, content_sha256, expected_mime_type, expected_size_bytes,
                       expected_content_sha256, failure_code, created_at, updated_at
                from public.documents where id = :id
                """
            ),
            {"id": document_id},
        )
        row = result.mappings().one_or_none()
        return DocumentRecord(**row) if row else None
