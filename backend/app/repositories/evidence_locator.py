from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EvidencePdfRecord:
    storage_object_path: str


class EvidenceLocatorRepositoryError(Exception):
    pass


class EvidenceLocatorRepository(Protocol):
    async def get_pdf(self, upstage_file_id: str) -> EvidencePdfRecord | None: ...


class SqlAlchemyEvidenceLocatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pdf(self, upstage_file_id: str) -> EvidencePdfRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select storage_object_path
                    from public.knowledge_document_versions
                    where upstage_file_id = :file_id and status = 'active'
                    """
                ),
                {"file_id": upstage_file_id},
            )
            row = result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise EvidenceLocatorRepositoryError from exc
        return EvidencePdfRecord(**dict(row)) if row else None


__all__ = [
    "EvidenceLocatorRepository",
    "EvidenceLocatorRepositoryError",
    "EvidencePdfRecord",
    "SqlAlchemyEvidenceLocatorRepository",
]
