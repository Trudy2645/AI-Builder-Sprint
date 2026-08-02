from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_modusign_client
from app.core.auth import get_auth_provider
from app.core.config import Settings, get_settings
from app.integrations.auth import AuthenticatedUser, FakeAuthProvider
from app.integrations.modusign import (
    ModusignNotFoundError,
    ModusignParticipant,
    ModusignRequestError,
    ModusignUnavailableError,
)

USER = AuthenticatedUser(UUID("00000000-0000-0000-0000-000000000001"), "buyer@example.jp")

VALID_PAYLOAD = {
    "title": "Ocean Stay Contract",
    "buyer": {"role": "바이어", "name": "Aiko Tanaka", "email": "aiko@example.jp"},
    "seller": {"role": "셀러", "name": "Ocean Stay", "email": "seller@example.kr"},
}


class FakeModusignClient:
    def __init__(
        self,
        *,
        create_response: dict[str, Any] | None = None,
        create_error: Exception | None = None,
        document: dict[str, Any] | None = None,
        document_error: Exception | None = None,
        file_response: tuple[bytes, str] | None = None,
        file_error: Exception | None = None,
    ) -> None:
        self._create_response = create_response
        self._create_error = create_error
        self._document = document
        self._document_error = document_error
        self._file_response = file_response
        self._file_error = file_error
        self.create_calls: list[dict[str, Any]] = []
        self.fetched_urls: list[str] = []

    async def create_signature_request(
        self,
        *,
        template_id: str,
        title: str,
        participants: list[ModusignParticipant],
    ) -> dict[str, Any]:
        self.create_calls.append(
            {"template_id": template_id, "title": title, "participants": participants}
        )
        if self._create_error is not None:
            raise self._create_error
        assert self._create_response is not None
        return self._create_response

    async def get_document(self, document_id: str) -> dict[str, Any]:
        if self._document_error is not None:
            raise self._document_error
        assert self._document is not None
        return self._document

    async def fetch_file(self, download_url: str) -> tuple[bytes, str]:
        self.fetched_urls.append(download_url)
        if self._file_error is not None:
            raise self._file_error
        assert self._file_response is not None
        return self._file_response


def bearer(token: str = "user-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_provider() -> FakeAuthProvider:
    return FakeAuthProvider({"user-token": USER})


def build_client(
    app: FastAPI,
    auth_provider: FakeAuthProvider,
    modusign_client: FakeModusignClient,
    *,
    settings: Settings | None = None,
) -> TestClient:
    app.dependency_overrides[get_auth_provider] = lambda: auth_provider
    app.dependency_overrides[get_modusign_client] = lambda: modusign_client
    app.dependency_overrides[get_settings] = lambda: (
        settings or Settings(modusign_template_id="tmpl-607668d0")
    )
    return TestClient(app)


def test_create_signature_request_success(app: FastAPI, auth_provider: FakeAuthProvider) -> None:
    fake_client = FakeModusignClient(
        create_response={"id": "doc-1", "title": "Ocean Stay Contract", "status": "ON_PROCESSING"}
    )
    with build_client(app, auth_provider, fake_client) as client:
        response = client.post("/api/v1/modusign/requests", headers=bearer(), json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["data"] == {
        "document_id": "doc-1",
        "title": "Ocean Stay Contract",
        "status": "ON_PROCESSING",
    }
    assert fake_client.create_calls[0]["template_id"] == "tmpl-607668d0"
    assert fake_client.create_calls[0]["participants"] == [
        ModusignParticipant(role="바이어", name="Aiko Tanaka", email="aiko@example.jp")
    ]


def test_create_signature_request_requires_auth(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(create_response={})
    with build_client(app, auth_provider, fake_client) as client:
        response = client.post("/api/v1/modusign/requests", json=VALID_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_create_signature_request_rejects_invalid_role(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(create_response={})
    payload = {**VALID_PAYLOAD, "buyer": {**VALID_PAYLOAD["buyer"], "role": "관리자"}}
    with build_client(app, auth_provider, fake_client) as client:
        response = client.post("/api/v1/modusign/requests", headers=bearer(), json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_signature_request_template_not_configured(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(create_response={})
    with build_client(
        app, auth_provider, fake_client, settings=Settings(modusign_template_id=None)
    ) as client:
        response = client.post("/api/v1/modusign/requests", headers=bearer(), json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODUSIGN_TEMPLATE_NOT_CONFIGURED"


def test_create_signature_request_rejected_by_modusign(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(
        create_error=ModusignRequestError(status_code=422, detail="invalid templateId")
    )
    with build_client(app, auth_provider, fake_client) as client:
        response = client.post("/api/v1/modusign/requests", headers=bearer(), json=VALID_PAYLOAD)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MODUSIGN_REQUEST_REJECTED"
    assert response.json()["error"]["details"]["modusign_status_code"] == 422


def test_create_signature_request_modusign_unavailable(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(create_error=ModusignUnavailableError())
    with build_client(app, auth_provider, fake_client) as client:
        response = client.post("/api/v1/modusign/requests", headers=bearer(), json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODUSIGN_UNAVAILABLE"


def test_get_document_status_success(app: FastAPI, auth_provider: FakeAuthProvider) -> None:
    fake_client = FakeModusignClient(
        document={
            "id": "doc-1",
            "status": "ON_GOING",
            "currentSigningOrder": 2,
            "file": {},
            "auditTrail": {},
        }
    )
    with build_client(app, auth_provider, fake_client) as client:
        response = client.get("/api/v1/modusign/documents/doc-1", headers=bearer())

    assert response.status_code == 200
    assert response.json()["data"] == {
        "document_id": "doc-1",
        "status": "ON_GOING",
        "current_signing_order": 2,
        "file": {"download_url": None},
        "audit_trail": {"download_url": None},
    }


def test_get_document_status_not_found(app: FastAPI, auth_provider: FakeAuthProvider) -> None:
    fake_client = FakeModusignClient(document_error=ModusignNotFoundError())
    with build_client(app, auth_provider, fake_client) as client:
        response = client.get("/api/v1/modusign/documents/missing", headers=bearer())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MODUSIGN_DOCUMENT_NOT_FOUND"


def test_download_signed_document_success(app: FastAPI, auth_provider: FakeAuthProvider) -> None:
    fake_client = FakeModusignClient(
        document={
            "id": "doc-1",
            "status": "COMPLETED",
            "file": {"downloadUrl": "https://modusign.example/files/doc-1"},
            "auditTrail": {"downloadUrl": "https://modusign.example/audit/doc-1"},
        },
        file_response=(b"%PDF-1.4 fake", "application/pdf"),
    )
    with build_client(app, auth_provider, fake_client) as client:
        response = client.get("/api/v1/modusign/documents/doc-1/download", headers=bearer())

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake"
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="doc-1-signed.pdf"' in response.headers["content-disposition"]
    assert fake_client.fetched_urls == ["https://modusign.example/files/doc-1"]


def test_download_signed_document_not_completed(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(document={"id": "doc-1", "status": "ON_GOING"})
    with build_client(app, auth_provider, fake_client) as client:
        response = client.get("/api/v1/modusign/documents/doc-1/download", headers=bearer())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MODUSIGN_DOCUMENT_NOT_COMPLETED"


def test_download_signed_document_missing_url(
    app: FastAPI, auth_provider: FakeAuthProvider
) -> None:
    fake_client = FakeModusignClient(document={"id": "doc-1", "status": "COMPLETED", "file": {}})
    with build_client(app, auth_provider, fake_client) as client:
        response = client.get("/api/v1/modusign/documents/doc-1/download", headers=bearer())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MODUSIGN_FILE_NOT_AVAILABLE"


def test_download_audit_trail_success(app: FastAPI, auth_provider: FakeAuthProvider) -> None:
    fake_client = FakeModusignClient(
        document={
            "id": "doc-1",
            "status": "COMPLETED",
            "file": {"downloadUrl": "https://modusign.example/files/doc-1"},
            "auditTrail": {"downloadUrl": "https://modusign.example/audit/doc-1"},
        },
        file_response=(b"audit-bytes", "application/pdf"),
    )
    with build_client(app, auth_provider, fake_client) as client:
        response = client.get("/api/v1/modusign/documents/doc-1/audit-trail", headers=bearer())

    assert response.status_code == 200
    assert response.content == b"audit-bytes"
    assert 'filename="doc-1-audit-trail.pdf"' in response.headers["content-disposition"]
    assert fake_client.fetched_urls == ["https://modusign.example/audit/doc-1"]
