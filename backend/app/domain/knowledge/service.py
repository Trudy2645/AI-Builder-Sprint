from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from pypdf import PdfReader, PdfWriter

from app.ai.providers.base import KnowledgeBaseProvider
from app.integrations.storage import StorageProvider
from app.rag.manifests import KnowledgeManifestEntry
from app.repositories.knowledge import KnowledgeRepository

_CORPUS_CONFIG = {
    "official_evidence": (
        "official_contract_knowledge",
        "Official contract knowledge",
        "official",
    ),
    "approved_templates": ("busan_link_templates", "BusanLink approved templates", "template"),
    "case_reference": ("case_reference", "Approved court case references", "case_reference"),
}


@dataclass(frozen=True, slots=True)
class KnowledgeIngestionResult:
    source_key: str
    version_id: UUID
    status: str
    cached: bool


class KnowledgeIngestionError(RuntimeError):
    pass


class KnowledgeIngestionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        storage: StorageProvider,
        provider: KnowledgeBaseProvider,
        *,
        storage_bucket: str = "rag-knowledge",
        poll_interval_seconds: float = 0,
        max_poll_attempts: int = 30,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._provider = provider
        self._bucket = storage_bucket
        self._poll_interval = poll_interval_seconds
        self._max_poll_attempts = max_poll_attempts

    async def ingest(
        self,
        entry: KnowledgeManifestEntry,
        source_root: Path,
        approved_by: UUID,
        *,
        retry_failed: bool = False,
        normalize_provider_pdf: bool = False,
        provider_text_derivative: bool = False,
    ) -> KnowledgeIngestionResult:
        content = entry.verified_content(source_root)
        existing = await self._repository.get_version_by_hash(entry.content_sha256)
        retrying = existing is not None and existing.status == "failed" and retry_failed
        if existing is not None and existing.status != "reviewed" and not retrying:
            return KnowledgeIngestionResult(
                entry.source_key, existing.id, existing.status, cached=True
            )
        code, name, corpus_type = _CORPUS_CONFIG[entry.corpus]
        base = await self._repository.get_or_create_base(
            code=code, name=name, corpus_type=corpus_type
        )
        store_id = base.vector_store_id or await self._ensure_vector_store(name)
        if base.vector_store_id is None:
            await self._repository.set_vector_store(base.id, store_id)

        version_id = existing.id if existing is not None else uuid4()
        category = entry.contract_categories[0]
        object_prefix = f"{entry.corpus}/{category}/{entry.source_key}/{version_id}"
        original_path = f"{object_prefix}/original.pdf"
        attributes = entry.provider_attributes(str(version_id))
        if normalize_provider_pdf and provider_text_derivative:
            raise KnowledgeIngestionError("choose only one provider derivative mode")
        retry_mode = "original_pdf"
        provider_filename = f"{entry.source_key}__{entry.version_label}.pdf"
        provider_mime_type = "application/pdf"
        provider_content = content
        if normalize_provider_pdf:
            retry_mode = "normalized_pdf"
            provider_content = _normalized_pdf(content)
        elif provider_text_derivative:
            retry_mode = "page_marked_text"
            provider_filename = f"{entry.source_key}__{entry.version_label}.txt"
            provider_mime_type = "text/plain"
            provider_content = _page_marked_text(content)
        if retrying:
            await self._repository.reopen_failed(
                version_id,
                provider_content_sha256=hashlib.sha256(provider_content).hexdigest(),
                retry_mode=retry_mode,
            )
        if existing is None:
            await self._repository.register_reviewed_version(
                version_id=version_id,
                base_id=base.id,
                entry=entry,
                approved_by=approved_by,
                storage_object_path=original_path,
                metadata={
                    "file_format": "pdf",
                    "original_page_count": entry.page_count,
                    "provider_attributes": attributes,
                },
            )
        try:
            if not retrying:
                await self._storage.ensure_private_bucket(self._bucket)
                await self._storage.put_object(
                    self._bucket, original_path, content, "application/pdf"
                )
                snapshot = entry.model_dump(mode="json")
                snapshot.pop("local_path", None)
                await self._storage.put_object(
                    self._bucket,
                    f"{object_prefix}/manifest.json",
                    json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode(),
                    "application/json",
                )
            uploaded = await self._provider.upload_knowledge_file(
                provider_filename,
                provider_content,
                provider_mime_type,
            )
            attached = await self._provider.attach_vector_store_file(
                store_id, uploaded.id, attributes
            )
            attached = await self._wait_until_indexed(store_id, uploaded.id, attached)
            if attached.status != "completed":
                raise KnowledgeIngestionError(attached.last_error or "vector indexing failed")
            await self._repository.mark_uploaded(
                version_id,
                upstage_file_id=uploaded.id,
                vector_store_file_id=attached.id,
            )
            await self._repository.mark_active(version_id)
        except Exception as exc:
            await self._repository.mark_failed(version_id, type(exc).__name__)
            raise
        return KnowledgeIngestionResult(entry.source_key, version_id, "active", cached=False)

    async def _ensure_vector_store(self, name: str) -> str:
        stores = await self._provider.list_vector_stores()
        matches = [store for store in stores if store.name == name]
        if len(matches) > 1:
            raise KnowledgeIngestionError(f"duplicate vector stores named {name}")
        if matches:
            return matches[0].id
        return (await self._provider.create_vector_store(name)).id

    async def _wait_until_indexed(self, store_id: str, file_id: str, attached):
        current = attached
        for _ in range(self._max_poll_attempts):
            if current.status != "in_progress":
                return current
            if self._poll_interval:
                await asyncio.sleep(self._poll_interval)
            current = await self._provider.get_vector_store_file(store_id, file_id)
        raise KnowledgeIngestionError("vector indexing timed out")


def _normalized_pdf(content: bytes) -> bytes:
    source = PdfReader(BytesIO(content), strict=True)
    writer = PdfWriter()
    writer.append_pages_from_reader(source)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _page_marked_text(content: bytes) -> bytes:
    source = PdfReader(BytesIO(content), strict=True)
    pages = [
        f"[PAGE {index}]\n{page.extract_text() or ''}" for index, page in enumerate(source.pages, 1)
    ]
    return "\n\n".join(pages).encode()


__all__ = [
    "KnowledgeIngestionError",
    "KnowledgeIngestionResult",
    "KnowledgeIngestionService",
]
