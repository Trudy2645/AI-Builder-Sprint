from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: UUID
    finding_id: UUID
    document_version_id: UUID
    document_title: str
    authority: str | None
    official_source_url: str | None
    effective_from: date | None
    retrieved_at: datetime
    storage_object_path: str
    corpus_type: str
    page_start: int
    page_end: int
    section_path: str | None
    excerpt: str
    bbox: dict[str, Any] | None
    viewer_role: str
    is_public: bool
    listing_status: str | None
    seller_organization_id: UUID
    buyer_user_id: UUID | None


class EvidenceRepositoryError(Exception):
    pass


class EvidenceRepository(Protocol):
    async def get_evidence(self, finding_id: UUID, evidence_id: UUID) -> EvidenceRecord | None: ...

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_evidence(self, finding_id: UUID, evidence_id: UUID) -> EvidenceRecord | None:
        row = await self._one(
            """
            select re.id as evidence_id, re.finding_id, re.document_version_id,
                   kd.title as document_title, kd.authority,
                   kd.source_url as official_source_url,
                   kv.effective_from, kv.retrieved_at, kv.storage_object_path,
                   kb.corpus_type::text, re.page_start, re.page_end,
                   re.section_path, re.excerpt, re.bbox,
                   ar.viewer_role::text, af.is_public, l.status::text as listing_status,
                   coalesce(l.seller_organization_id, c.seller_organization_id)
                       as seller_organization_id,
                   c.buyer_user_id
            from public.rag_evidence re
            join public.ai_findings af on af.id = re.finding_id
            join public.ai_analysis_runs ar on ar.id = af.analysis_run_id
            join public.knowledge_document_versions kv on kv.id = re.document_version_id
            join public.knowledge_documents kd on kd.id = kv.document_id
            join public.knowledge_bases kb on kb.id = kd.knowledge_base_id
            left join public.listing_versions lv on lv.id = ar.listing_version_id
            left join public.listings l on l.id = lv.listing_id
            left join public.contract_versions cv on cv.id = ar.contract_version_id
            left join public.contracts c on c.id = cv.contract_id
            where re.id = :evidence_id and re.finding_id = :finding_id
            """,
            {"finding_id": finding_id, "evidence_id": evidence_id},
        )
        return EvidenceRecord(**dict(row)) if row else None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        row = await self._one(
            """
            select 1 from public.organization_members
            where user_id = :user_id and organization_id = :organization_id
            """,
            {"user_id": user_id, "organization_id": organization_id},
        )
        return row is not None

    async def _one(self, sql: str, params: dict[str, Any]):
        try:
            result = await self._session.execute(text(sql), params)
            return result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise EvidenceRepositoryError from exc


__all__ = [
    "EvidenceRecord",
    "EvidenceRepository",
    "EvidenceRepositoryError",
    "SqlAlchemyEvidenceRepository",
]
