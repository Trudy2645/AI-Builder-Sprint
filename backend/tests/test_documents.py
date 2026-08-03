from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_document_service
from app.core.auth import get_current_user
from app.domain.documents.service import DocumentService
from app.integrations.auth import AuthenticatedUser
from app.integrations.storage import FakeStorageProvider
from app.repositories.documents import (
    ContractDocumentAccessRecord,
    DocumentIdempotencyConflictError,
    DocumentMembershipRecord,
    DocumentRecord,
)

SELLER_ID = UUID("d1000000-0000-0000-0000-000000000001")
OTHER_SELLER_ID = UUID("d1000000-0000-0000-0000-000000000002")
BUYER_ID = UUID("d1000000-0000-0000-0000-000000000003")
OTHER_BUYER_ID = UUID("d1000000-0000-0000-0000-000000000004")
ORGANIZATION_ID = UUID("d2000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID("d2000000-0000-0000-0000-000000000002")
LISTING_ID = UUID("d3000000-0000-0000-0000-000000000001")
OTHER_LISTING_ID = UUID("d3000000-0000-0000-0000-000000000002")
CONTRACT_ID = UUID("d4000000-0000-0000-0000-000000000001")
OTHER_CONTRACT_ID = UUID("d4000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 8, 1, 12, tzinfo=UTC)
PDF = b"%PDF-1.7\n" + "찍어보소 test contract\n".encode() + b"%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"image-data"


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.memberships = {
            (SELLER_ID, ORGANIZATION_ID): DocumentMembershipRecord(
                ORGANIZATION_ID, "seller", "owner"
            ),
            (OTHER_SELLER_ID, OTHER_ORGANIZATION_ID): DocumentMembershipRecord(
                OTHER_ORGANIZATION_ID, "seller", "owner"
            ),
        }
        self.listings = {
            LISTING_ID: ORGANIZATION_ID,
            OTHER_LISTING_ID: OTHER_ORGANIZATION_ID,
        }
        self.contracts = {
            CONTRACT_ID: ContractDocumentAccessRecord(BUYER_ID, ORGANIZATION_ID),
            OTHER_CONTRACT_ID: ContractDocumentAccessRecord(OTHER_BUYER_ID, OTHER_ORGANIZATION_ID),
        }
        self.documents: dict[UUID, DocumentRecord] = {}
        self.idempotency: dict[tuple[UUID, str], tuple[str, UUID]] = {}

    async def get_membership(self, user_id: UUID, organization_id: UUID):
        return self.memberships.get((user_id, organization_id))

    async def get_listing_organization_id(self, listing_id: UUID):
        return self.listings.get(listing_id)

    async def get_contract_access(self, contract_id: UUID):
        return self.contracts.get(contract_id)

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
        key = (actor_user_id, idempotency_key)
        existing = self.idempotency.get(key)
        if existing is not None:
            if existing[0] != request_hash:
                raise DocumentIdempotencyConflictError
            return self.documents[existing[1]]
        record = DocumentRecord(
            id=document_id,
            organization_id=organization_id,
            listing_id=listing_id,
            contract_id=contract_id,
            purpose=purpose,
            status="pending_upload",
            storage_bucket=storage_bucket,
            storage_object_path=storage_object_path,
            original_filename=original_filename,
            mime_type=None,
            size_bytes=None,
            content_sha256=None,
            expected_mime_type=expected_mime_type,
            expected_size_bytes=expected_size_bytes,
            expected_content_sha256=expected_content_sha256,
            failure_code=None,
            created_at=NOW,
            updated_at=NOW,
        )
        self.documents[document_id] = record
        self.idempotency[key] = (request_hash, document_id)
        return record

    async def get_document(self, document_id: UUID):
        return self.documents.get(document_id)

    async def mark_uploaded(
        self,
        document_id: UUID,
        *,
        mime_type: str,
        size_bytes: int,
        content_sha256: str,
    ) -> DocumentRecord:
        record = self.documents[document_id]
        if record.status == "pending_upload":
            record = replace(
                record,
                status="uploaded",
                mime_type=mime_type,
                size_bytes=size_bytes,
                content_sha256=content_sha256,
                failure_code=None,
            )
            self.documents[document_id] = record
        return record

    async def mark_failed(self, document_id: UUID, failure_code: str) -> None:
        record = self.documents[document_id]
        self.documents[document_id] = replace(record, status="failed", failure_code=failure_code)


@pytest.fixture
def document_context(app: FastAPI):
    repository = FakeDocumentRepository()
    storage = FakeStorageProvider()
    service = DocumentService(
        repository,
        storage,
        max_size_bytes=1024,
        download_url_expires_seconds=300,
    )
    app.dependency_overrides[get_document_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        SELLER_ID, "seller@example.test"
    )
    return repository, storage


@pytest.fixture
def document_client(app: FastAPI, client: TestClient, document_context):
    return client


def headers(
    *, organization_id: UUID = ORGANIZATION_ID, idempotency_key: str = "document-key-1"
) -> dict[str, str]:
    return {
        "X-Organization-Id": str(organization_id),
        "Idempotency-Key": idempotency_key,
    }


def upload_payload(
    data: bytes = PDF,
    *,
    listing_id: UUID = LISTING_ID,
    filename: str = "contract.pdf",
    mime_type: str = "application/pdf",
    content_hash: str | None = None,
    size_bytes: int | None = None,
) -> dict[str, object]:
    return {
        "listing_id": str(listing_id),
        "purpose": "source_contract",
        "original_filename": filename,
        "mime_type": mime_type,
        "size_bytes": len(data) if size_bytes is None else size_bytes,
        "content_sha256": content_hash or sha256(data).hexdigest(),
    }


def create_upload(
    client: TestClient,
    context,
    *,
    data: bytes = PDF,
    payload: dict[str, object] | None = None,
    put_object: bool = True,
    request_headers: dict[str, str] | None = None,
):
    repository, storage = context
    response = client.post(
        "/api/v1/documents/upload-url",
        headers=request_headers or headers(),
        json=payload or upload_payload(data),
    )
    if response.status_code == 201 and put_object:
        document_id = UUID(response.json()["data"]["document"]["id"])
        record = repository.documents[document_id]
        storage.put(record.storage_bucket, record.storage_object_path, data)
    return response


def test_document_upload_complete_get_and_download(
    document_client: TestClient, document_context
) -> None:
    created = create_upload(document_client, document_context)
    document_id = created.json()["data"]["document"]["id"]

    completed = document_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers())
    fetched = document_client.get(f"/api/v1/documents/{document_id}", headers=headers())
    download = document_client.post(
        f"/api/v1/documents/{document_id}/download-url", headers=headers()
    )

    assert created.status_code == 201
    assert created.json()["data"]["method"] == "PUT"
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "uploaded"
    assert completed.json()["data"]["content_sha256"] == sha256(PDF).hexdigest()
    assert fetched.status_code == 200
    assert download.status_code == 200
    serialized = str(created.json()) + str(fetched.json()) + str(download.json())
    assert "storage_bucket" not in serialized
    assert "storage_object_path" not in serialized


def test_upload_requires_authentication(
    app: FastAPI, document_client: TestClient, document_context
) -> None:
    del app.dependency_overrides[get_current_user]
    response = document_client.post(
        "/api/v1/documents/upload-url", headers=headers(), json=upload_payload()
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_other_organization_cannot_access_document(
    app: FastAPI, document_client: TestClient, document_context
) -> None:
    created = create_upload(document_client, document_context)
    document_id = created.json()["data"]["document"]["id"]
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OTHER_SELLER_ID, "other@example.test"
    )
    response = document_client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers(organization_id=OTHER_ORGANIZATION_ID),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DOCUMENT_ACCESS_DENIED"


def test_other_contract_party_cannot_access_document(
    app: FastAPI, document_client: TestClient, document_context
) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        BUYER_ID, "buyer@example.test"
    )
    payload = upload_payload()
    payload.pop("listing_id")
    payload["contract_id"] = str(CONTRACT_ID)
    created = create_upload(
        document_client,
        document_context,
        payload=payload,
        request_headers={"Idempotency-Key": "buyer-contract-file"},
    )
    document_id = created.json()["data"]["document"]["id"]
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        OTHER_BUYER_ID, "other-buyer@example.test"
    )
    response = document_client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DOCUMENT_ACCESS_DENIED"


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [("contract.exe", "application/octet-stream"), ("contract.pdf", "image/png")],
)
def test_upload_rejects_unsupported_extension_or_declared_mime(
    document_client: TestClient, document_context, filename: str, mime_type: str
) -> None:
    response = create_upload(
        document_client,
        document_context,
        payload=upload_payload(filename=filename, mime_type=mime_type),
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_upload_rejects_declared_size_over_limit(
    document_client: TestClient, document_context
) -> None:
    response = create_upload(
        document_client,
        document_context,
        payload=upload_payload(size_bytes=1025),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_complete_rejects_mime_mismatch(document_client: TestClient, document_context) -> None:
    created = create_upload(
        document_client, document_context, data=PNG, payload=upload_payload(PDF)
    )
    document_id = created.json()["data"]["document"]["id"]
    response = document_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MIME_TYPE_MISMATCH"


def test_complete_rejects_hash_mismatch(document_client: TestClient, document_context) -> None:
    payload = upload_payload(content_hash="0" * 64)
    created = create_upload(document_client, document_context, payload=payload)
    document_id = created.json()["data"]["document"]["id"]
    response = document_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_HASH_MISMATCH"


def test_complete_requires_existing_storage_object(
    document_client: TestClient, document_context
) -> None:
    created = create_upload(document_client, document_context, put_object=False)
    document_id = created.json()["data"]["document"]["id"]
    response = document_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STORAGE_OBJECT_NOT_FOUND"


def test_complete_is_idempotent(document_client: TestClient, document_context) -> None:
    created = create_upload(document_client, document_context)
    document_id = created.json()["data"]["document"]["id"]
    first = document_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers())
    second = document_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers())
    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == second.json()["data"]


def test_upload_url_is_idempotent_and_has_bounded_expiry(
    document_client: TestClient, document_context
) -> None:
    first = create_upload(document_client, document_context, put_object=False)
    second = create_upload(document_client, document_context, put_object=False)
    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["document"]["id"] == second.json()["data"]["document"]["id"]
    expires_at = datetime.fromisoformat(first.json()["data"]["expires_at"])
    remaining_seconds = (expires_at - datetime.now(UTC)).total_seconds()
    assert 7100 <= remaining_seconds <= 7200


def test_storage_provider_failure_is_mapped_to_service_unavailable(
    document_client: TestClient, document_context
) -> None:
    _, storage = document_context
    storage.unavailable = True
    response = create_upload(document_client, document_context, put_object=False)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_PROVIDER_UNAVAILABLE"
