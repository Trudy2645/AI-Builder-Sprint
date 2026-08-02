from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.manifests import KnowledgeManifestEntry


@dataclass(frozen=True, slots=True)
class KnowledgeBaseRecord:
    id: UUID
    code: str
    vector_store_id: str | None


@dataclass(frozen=True, slots=True)
class KnowledgeVersionRecord:
    id: UUID
    status: str
    upstage_file_id: str | None = None


class KnowledgeRepositoryError(Exception):
    pass


class KnowledgeRepository(Protocol):
    async def get_version_by_hash(self, content_sha256: str) -> KnowledgeVersionRecord | None: ...

    async def get_or_create_base(
        self, *, code: str, name: str, corpus_type: str
    ) -> KnowledgeBaseRecord: ...

    async def set_vector_store(self, base_id: UUID, vector_store_id: str) -> None: ...

    async def register_reviewed_version(
        self,
        *,
        version_id: UUID,
        base_id: UUID,
        entry: KnowledgeManifestEntry,
        approved_by: UUID,
        storage_object_path: str,
        metadata: dict[str, Any],
    ) -> None: ...

    async def mark_uploaded(
        self,
        version_id: UUID,
        *,
        upstage_file_id: str,
        vector_store_file_id: str,
    ) -> None: ...

    async def mark_active(self, version_id: UUID) -> None: ...

    async def mark_failed(self, version_id: UUID, failure_code: str) -> None: ...

    async def reopen_failed(
        self, version_id: UUID, *, provider_content_sha256: str, retry_mode: str
    ) -> None: ...


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_version_by_hash(self, content_sha256: str) -> KnowledgeVersionRecord | None:
        row = await self._one(
            """
            select id, status::text, upstage_file_id
            from public.knowledge_document_versions where content_sha256 = :content_sha256
            """,
            {"content_sha256": content_sha256},
        )
        return KnowledgeVersionRecord(**dict(row)) if row else None

    async def get_or_create_base(
        self, *, code: str, name: str, corpus_type: str
    ) -> KnowledgeBaseRecord:
        row = await self._one(
            """
            insert into public.knowledge_bases (code, name, corpus_type, status)
            values (:code, :name, cast(:corpus_type as public.knowledge_corpus_type), 'inactive')
            on conflict (code) do update set name = excluded.name
            returning id, code, upstage_vector_store_id as vector_store_id
            """,
            {"code": code, "name": name, "corpus_type": corpus_type},
        )
        return KnowledgeBaseRecord(**dict(row))

    async def set_vector_store(self, base_id: UUID, vector_store_id: str) -> None:
        await self._execute(
            """
            update public.knowledge_bases
            set upstage_vector_store_id = :vector_store_id, status = 'active'
            where id = :base_id
            """,
            {"base_id": base_id, "vector_store_id": vector_store_id},
        )

    async def register_reviewed_version(
        self,
        *,
        version_id: UUID,
        base_id: UUID,
        entry: KnowledgeManifestEntry,
        approved_by: UUID,
        storage_object_path: str,
        metadata: dict[str, Any],
    ) -> None:
        document_params = {
            "base_id": base_id,
            "source_key": entry.source_key,
            "title": entry.title,
            "source_type": entry.source_type,
            "authority": entry.authority,
            "source_url": str(entry.source_url) if entry.source_url else None,
            "categories": [item for item in entry.contract_categories],
            "activity_subtypes": entry.activity_subtypes,
            "party_type": entry.party_type,
            "applicability_note": entry.applicability_note,
        }
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                document = await self._session.execute(
                    text(
                        """
                        insert into public.knowledge_documents (
                            knowledge_base_id, source_key, title, source_type, authority,
                            source_url, contract_categories, activity_subtypes, party_type,
                            applicability_note
                        ) values (
                            :base_id, :source_key, :title, :source_type, :authority, :source_url,
                            cast(:categories as public.contract_category[]), :activity_subtypes,
                            :party_type, :applicability_note
                        )
                        on conflict (knowledge_base_id, source_key) do update
                        set title = excluded.title, authority = excluded.authority,
                            source_url = excluded.source_url,
                            applicability_note = excluded.applicability_note
                        returning id
                        """
                    ),
                    document_params,
                )
                document_id = document.scalar_one()
                await self._session.execute(
                    text(
                        """
                        insert into public.knowledge_document_versions (
                            id, document_id, version_label, effective_from, effective_to,
                            retrieved_at, content_sha256, storage_object_path, status,
                            approved_by, approved_at, metadata
                        ) values (
                            :id, :document_id, :version_label, :effective_from, :effective_to,
                            :retrieved_at, :content_sha256, :storage_object_path, 'reviewed',
                            :approved_by, :approved_at, cast(:metadata as jsonb)
                        )
                        """
                    ),
                    {
                        "id": version_id,
                        "document_id": document_id,
                        "version_label": entry.version_label,
                        "effective_from": entry.effective_from,
                        "effective_to": entry.effective_to,
                        "retrieved_at": entry.retrieved_at,
                        "content_sha256": entry.content_sha256,
                        "storage_object_path": storage_object_path,
                        "approved_by": approved_by,
                        "approved_at": entry.approved_at,
                        "metadata": _json(metadata),
                    },
                )
        except SQLAlchemyError as exc:
            raise KnowledgeRepositoryError from exc

    async def mark_uploaded(
        self,
        version_id: UUID,
        *,
        upstage_file_id: str,
        vector_store_file_id: str,
    ) -> None:
        await self._execute(
            """
            update public.knowledge_document_versions
            set upstage_file_id = :file_id,
                upstage_vector_store_file_id = :vector_file_id, status = 'indexed'
            where id = :version_id and status = 'reviewed'
            """,
            {
                "version_id": version_id,
                "file_id": upstage_file_id,
                "vector_file_id": vector_store_file_id,
            },
        )

    async def mark_active(self, version_id: UUID) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        update public.knowledge_document_versions old
                        set status = 'superseded'
                        from public.knowledge_document_versions current
                        where current.id = :version_id and old.document_id = current.document_id
                          and old.id <> current.id and old.status = 'active'
                        """
                    ),
                    {"version_id": version_id},
                )
                await self._session.execute(
                    text(
                        """
                        update public.knowledge_document_versions set status = 'active'
                        where id = :version_id and status = 'indexed'
                        """
                    ),
                    {"version_id": version_id},
                )
        except SQLAlchemyError as exc:
            raise KnowledgeRepositoryError from exc

    async def mark_failed(self, version_id: UUID, failure_code: str) -> None:
        await self._execute(
            """
            update public.knowledge_document_versions
            set status = 'failed', metadata = metadata || jsonb_build_object(
                'failure_code', cast(:failure_code as text)
            ) where id = :version_id and status not in ('active', 'superseded', 'revoked')
            """,
            {"version_id": version_id, "failure_code": failure_code},
        )

    async def reopen_failed(
        self, version_id: UUID, *, provider_content_sha256: str, retry_mode: str
    ) -> None:
        await self._execute(
            """
            update public.knowledge_document_versions
            set status = 'reviewed', metadata = metadata || jsonb_build_object(
                'provider_retry_mode', cast(:retry_mode as text),
                'provider_content_sha256', cast(:provider_hash as text)
            ) where id = :version_id and status = 'failed'
            """,
            {
                "version_id": version_id,
                "provider_hash": provider_content_sha256,
                "retry_mode": retry_mode,
            },
        )

    async def _one(self, sql: str, params: dict[str, Any]):
        try:
            result = await self._session.execute(text(sql), params)
            return result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise KnowledgeRepositoryError from exc

    async def _execute(self, sql: str, params: dict[str, Any]) -> None:
        try:
            if self._session.in_transaction():
                await self._session.commit()
            async with self._session.begin():
                await self._session.execute(text(sql), params)
        except SQLAlchemyError as exc:
            raise KnowledgeRepositoryError from exc


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, UUID)):
        return str(value)
    raise TypeError


__all__ = [
    "KnowledgeBaseRecord",
    "KnowledgeRepository",
    "KnowledgeRepositoryError",
    "KnowledgeVersionRecord",
    "SqlAlchemyKnowledgeRepository",
]
