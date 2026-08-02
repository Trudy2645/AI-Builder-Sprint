from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Protocol

from pypdf import PdfReader

from app.integrations.storage import StorageProvider
from app.repositories.evidence_locator import EvidenceLocatorRepository


class EvidenceLocator(Protocol):
    async def locate(self, file_id: str, excerpt: str) -> dict[str, int] | None: ...


class StoredPdfEvidenceLocator:
    def __init__(
        self,
        repository: EvidenceLocatorRepository,
        storage: StorageProvider,
        *,
        storage_bucket: str,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._bucket = storage_bucket
        self._page_cache: dict[str, list[str]] = {}

    async def locate(self, file_id: str, excerpt: str) -> dict[str, int] | None:
        pages = self._page_cache.get(file_id)
        if pages is None:
            record = await self._repository.get_pdf(file_id)
            if record is None:
                return None
            content = await _consume(
                self._storage.iter_object(self._bucket, record.storage_object_path)
            )
            pages = await asyncio.to_thread(_extract_pages, content)
            self._page_cache[file_id] = pages
        page = _best_page(excerpt, pages)
        return {"page_start": page, "page_end": page} if page else None


async def _consume(chunks: AsyncIterator[bytes]) -> bytes:
    values = bytearray()
    async for chunk in chunks:
        values.extend(chunk)
    return bytes(values)


def _extract_pages(content: bytes) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(BytesIO(content), strict=True).pages]


def _best_page(excerpt: str, pages: list[str]) -> int | None:
    target = set(_tokens(excerpt))
    if not target:
        return None
    scores = [len(target.intersection(_tokens(page))) / len(target) for page in pages]
    best = max(range(len(scores)), key=scores.__getitem__, default=-1)
    return best + 1 if best >= 0 and scores[best] >= 0.2 else None


def _tokens(value: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣]{2,}", value.lower())


__all__ = ["EvidenceLocator", "StoredPdfEvidenceLocator"]
