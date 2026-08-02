from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.providers.base import AIProviderTemporaryError
from app.ai.providers.fake import FakeAIProvider
from app.ai.schemas import FileSearchHit, FileSearchResult
from app.api.dependencies import get_evidence_service
from app.core.auth import get_current_user
from app.domain.evidence.service import EvidenceService
from app.domain.knowledge.service import KnowledgeIngestionService
from app.integrations.auth import AuthenticatedUser
from app.integrations.storage import FakeStorageProvider
from app.rag.evaluation import evaluate_retrieval, load_golden_queries
from app.rag.filters import build_retrieval_filter, metadata_matches_scope
from app.rag.manifests import (
    KnowledgeManifestEntry,
    KnowledgeManifestError,
    load_knowledge_manifest,
)
from app.repositories.evidence import EvidenceRecord
from app.repositories.knowledge import (
    KnowledgeBaseRecord,
    KnowledgeVersionRecord,
)

REPO_RAG_ROOT = Path(__file__).parents[2] / "rag"
TEST_PDF = b"%PDF-1.7\nreviewed knowledge fixture\n%%EOF\n"
ACTOR_ID = UUID("a1000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("a1000000-0000-0000-0000-000000000002")
ORGANIZATION_ID = UUID("a2000000-0000-0000-0000-000000000001")
FINDING_ID = UUID("a3000000-0000-0000-0000-000000000001")
EVIDENCE_ID = UUID("a4000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("a5000000-0000-0000-0000-000000000001")


class FakeKnowledgeRepository:
    def __init__(self) -> None:
        self.base = KnowledgeBaseRecord(uuid4(), "busan_link_templates", None)
        self.versions: dict[str, KnowledgeVersionRecord] = {}
        self.entries: dict[UUID, KnowledgeManifestEntry] = {}
        self.failed: dict[UUID, str] = {}

    async def get_version_by_hash(self, content_sha256: str):
        return self.versions.get(content_sha256)

    async def get_or_create_base(self, **_: Any):
        return self.base

    async def set_vector_store(self, base_id: UUID, vector_store_id: str) -> None:
        assert base_id == self.base.id
        self.base = replace(self.base, vector_store_id=vector_store_id)

    async def register_reviewed_version(
        self, *, version_id: UUID, entry: KnowledgeManifestEntry, **_: Any
    ) -> None:
        self.entries[version_id] = entry
        self.versions[entry.content_sha256] = KnowledgeVersionRecord(version_id, "reviewed")

    async def mark_uploaded(
        self, version_id: UUID, *, upstage_file_id: str, vector_store_file_id: str
    ) -> None:
        del vector_store_file_id
        entry = self.entries[version_id]
        self.versions[entry.content_sha256] = KnowledgeVersionRecord(
            version_id, "indexed", upstage_file_id
        )

    async def mark_active(self, version_id: UUID) -> None:
        entry = self.entries[version_id]
        current = self.versions[entry.content_sha256]
        self.versions[entry.content_sha256] = replace(current, status="active")

    async def mark_failed(self, version_id: UUID, failure_code: str) -> None:
        self.failed[version_id] = failure_code
        for content_hash, version in self.versions.items():
            if version.id == version_id:
                self.versions[content_hash] = replace(version, status="failed")
                return

    async def reopen_failed(
        self, version_id: UUID, *, provider_content_sha256: str, retry_mode: str
    ) -> None:
        assert len(provider_content_sha256) == 64
        assert retry_mode in {"original_pdf", "normalized_pdf", "page_marked_text"}
        for content_hash, version in self.versions.items():
            if version.id == version_id:
                self.versions[content_hash] = replace(version, status="reviewed")
                return
        raise AssertionError("unknown version")


class FakeEvidenceRepository:
    def __init__(self, record: EvidenceRecord) -> None:
        self.record = record
        self.members = {(ACTOR_ID, ORGANIZATION_ID)}

    async def get_evidence(self, finding_id: UUID, evidence_id: UUID):
        if finding_id == self.record.finding_id and evidence_id == self.record.evidence_id:
            return self.record
        return None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        return (user_id, organization_id) in self.members


def _template_entry(tmp_path: Path) -> tuple[KnowledgeManifestEntry, Path]:
    source = tmp_path / "data/templates/vehicle_rental/raw/template.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(TEST_PDF)
    entry = load_knowledge_manifest(
        REPO_RAG_ROOT / "manifests/template_sources.json", "approved_templates"
    )[0].model_copy(
        update={
            "local_path": "data/templates/vehicle_rental/raw/template.pdf",
            "content_sha256": hashlib.sha256(TEST_PDF).hexdigest(),
            "file_size": len(TEST_PDF),
        }
    )
    return entry, tmp_path


def test_reviewed_manifests_have_expected_approved_entries() -> None:
    official = load_knowledge_manifest(
        REPO_RAG_ROOT / "manifests/downloaded_sources.json", "official_evidence"
    )
    templates = load_knowledge_manifest(
        REPO_RAG_ROOT / "manifests/template_sources.json", "approved_templates"
    )
    cases = load_knowledge_manifest(REPO_RAG_ROOT / "manifests/case_sources.json", "case_reference")

    assert len(official) == 10
    assert len(templates) == 4
    assert len(cases) == 8
    assert all(entry.approved_by for entry in [*official, *templates, *cases])


def test_unreviewed_official_source_cannot_be_activated() -> None:
    reviewed = load_knowledge_manifest(
        REPO_RAG_ROOT / "manifests/downloaded_sources.json", "official_evidence"
    )[0]
    data = reviewed.model_dump()
    data.update(status="downloaded", approved_by=None, approved_at=None)

    with pytest.raises(ValidationError):
        KnowledgeManifestEntry.model_validate(data)


def test_user_contract_path_cannot_enter_public_vector_store(tmp_path: Path) -> None:
    entry, _ = _template_entry(tmp_path)
    entry = entry.model_copy(update={"local_path": "rag/data/contracts/private-user-contract.pdf"})

    with pytest.raises(KnowledgeManifestError, match="isolated corpus"):
        entry.resolve_local_file(tmp_path)


@pytest.mark.asyncio
async def test_ingestion_verifies_hash_snapshots_and_caches_by_hash(tmp_path: Path) -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeStorageProvider()
    provider = FakeAIProvider()
    service = KnowledgeIngestionService(repository, storage, provider)
    entry, source_root = _template_entry(tmp_path)

    first = await service.ingest(entry, source_root, ACTOR_ID)
    repeated = await service.ingest(entry, source_root, ACTOR_ID)

    assert first.status == "active"
    assert repeated.cached is True
    assert storage.private_buckets == {"rag-knowledge"}
    assert len(storage.objects) == 2
    assert len(provider.knowledge_files) == 1
    attributes = next(iter(provider.vector_store_attributes.values()))
    assert attributes["corpus"] == "approved_templates"
    assert attributes["party_type"] == "B2C_individual"
    assert attributes["category_vehicle_rental"] is True
    assert next(iter(provider.knowledge_files.values())).startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_provider_failure_marks_only_registered_version_failed(tmp_path: Path) -> None:
    repository = FakeKnowledgeRepository()
    provider = FakeAIProvider()
    provider.queue_failure("knowledge_file_upload", AIProviderTemporaryError())
    service = KnowledgeIngestionService(repository, FakeStorageProvider(), provider)

    entry, source_root = _template_entry(tmp_path)
    with pytest.raises(AIProviderTemporaryError):
        await service.ingest(entry, source_root, ACTOR_ID)

    assert len(repository.failed) == 1
    assert provider.vector_store_files == {}


def test_retrieval_filter_enforces_active_date_party_category_and_subtype() -> None:
    filters = build_retrieval_filter(
        corpus="official_evidence",
        category="activity",
        effective_on=date(2026, 8, 1),
        activity_subtype="water",
    )
    metadata = {
        "corpus": "official_evidence",
        "status": "active",
        "party_type": "B2C_individual",
        "category_common": False,
        "category_activity": True,
        "activity_subtype": "water",
        "effective_from_epoch": 0,
        "effective_to_epoch": 253402300799,
    }

    assert filters["type"] == "and"
    assert metadata_matches_scope(
        metadata,
        corpus="official_evidence",
        category="activity",
        effective_on=date(2026, 8, 1),
        activity_subtype="water",
    )
    assert not metadata_matches_scope(
        {**metadata, "category_activity": False},
        corpus="official_evidence",
        category="activity",
        effective_on=date(2026, 8, 1),
        activity_subtype="water",
    )
    assert not metadata_matches_scope(
        {**metadata, "status": "superseded"},
        corpus="official_evidence",
        category="activity",
        effective_on=date(2026, 8, 1),
        activity_subtype="water",
    )
    assert metadata_matches_scope(
        {**metadata, "activity_subtype": "common"},
        corpus="official_evidence",
        category="activity",
        effective_on=date(2026, 8, 1),
        activity_subtype="water",
    )


@pytest.mark.asyncio
async def test_retrieval_evaluation_has_twenty_queries_and_detects_scope_leakage() -> None:
    queries = load_golden_queries(REPO_RAG_ROOT / "eval/golden_queries.json")
    provider = FakeAIProvider()
    provider.search_result = FileSearchResult(
        hits=[
            FileSearchHit(
                file_id="file-1",
                score=0.9,
                excerpt="렌터카 표준약관",
                metadata={
                    "source_key": "vehicle_rental_standard_terms",
                    "corpus": "official_evidence",
                    "status": "active",
                    "party_type": "B2C_individual",
                    "category_common": False,
                    "category_vehicle_rental": True,
                    "effective_from_epoch": 0,
                    "effective_to_epoch": 253402300799,
                },
            )
        ]
    )

    result = await evaluate_retrieval(
        provider,
        vector_store_id="official-store",
        corpus="official_evidence",
        queries=queries[:1],
        effective_on=date(2026, 8, 1),
    )

    assert len(queries) == 20
    assert result.recall_at_5 == 1
    assert result.cross_category_leakage_rate == 0


def _evidence_record(**changes: Any) -> EvidenceRecord:
    values = {
        "evidence_id": EVIDENCE_ID,
        "finding_id": FINDING_ID,
        "document_version_id": VERSION_ID,
        "document_title": "소비자분쟁해결기준",
        "authority": "Korea Fair Trade Commission",
        "official_source_url": "https://www.law.go.kr/example",
        "effective_from": date(2025, 12, 18),
        "retrieved_at": datetime(2026, 7, 28, tzinfo=UTC),
        "storage_object_path": "official/common/source/version/original.pdf",
        "corpus_type": "official",
        "page_start": 31,
        "page_end": 31,
        "section_path": "별표 2 > 숙박업",
        "excerpt": "취소 시점별 분쟁해결기준",
        "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1},
        "viewer_role": "buyer",
        "is_public": False,
        "listing_status": None,
        "seller_organization_id": ORGANIZATION_ID,
        "buyer_user_id": ACTOR_ID,
    }
    return EvidenceRecord(**{**values, **changes})


def _evidence_client(app: FastAPI, actor_id: UUID, record: EvidenceRecord) -> TestClient:
    repository = FakeEvidenceRepository(record)
    storage = FakeStorageProvider()
    storage.put("rag-knowledge", record.storage_object_path, b"%PDF evidence")
    service = EvidenceService(
        repository,
        storage,
        storage_bucket="rag-knowledge",
        viewer_url_prefix="/knowledge/versions",
        signed_url_expires_seconds=300,
    )
    app.dependency_overrides[get_evidence_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(actor_id, None)
    return TestClient(app)


def test_finding_party_can_open_signed_evidence_pdf(app: FastAPI) -> None:
    with _evidence_client(app, ACTOR_ID, _evidence_record()) as client:
        response = client.get(f"/api/v1/ai-findings/{FINDING_ID}/evidence/{EVIDENCE_ID}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["document_title"] == "소비자분쟁해결기준"
    assert data["page_start"] == 31
    assert data["section"] == "별표 2 > 숙박업"
    assert data["signed_pdf_url"].startswith("https://storage.test/download/")
    assert data["viewer_url"].endswith(f"page=31&evidence={EVIDENCE_ID}")


def test_other_user_cannot_read_private_finding_evidence(app: FastAPI) -> None:
    with _evidence_client(app, OTHER_ID, _evidence_record()) as client:
        response = client.get(f"/api/v1/ai-findings/{FINDING_ID}/evidence/{EVIDENCE_ID}")

    assert response.status_code == 403
    assert "signed_pdf_url" not in response.text


def test_evidence_endpoint_is_in_openapi(app: FastAPI) -> None:
    schema = app.openapi()
    path = "/api/v1/ai-findings/{finding_id}/evidence/{evidence_id}"
    assert "get" in schema["paths"][path]
