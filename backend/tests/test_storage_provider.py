from datetime import UTC, datetime

import pytest

from app.integrations.storage import SupabaseStorageProvider


class StubResponse:
    def __init__(self, payload: dict[str, str], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return self._payload


class StubAsyncClient:
    calls: list[tuple[str, dict[str, object]]] = []
    responses: list[StubResponse] = []

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self) -> "StubAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, **kwargs: object) -> StubResponse:
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    async def get(self, url: str, **kwargs: object) -> StubResponse:
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


@pytest.fixture
def storage_provider(monkeypatch: pytest.MonkeyPatch) -> SupabaseStorageProvider:
    StubAsyncClient.calls = []
    StubAsyncClient.responses = []
    monkeypatch.setattr("app.integrations.storage.httpx.AsyncClient", StubAsyncClient)
    return SupabaseStorageProvider(
        supabase_url="https://project.supabase.co",
        service_role_key="test-service-key",
        timeout_seconds=5,
    )


@pytest.mark.asyncio
async def test_supabase_signed_upload_url_uses_storage_api_url_response(
    storage_provider: SupabaseStorageProvider,
) -> None:
    StubAsyncClient.responses.append(
        StubResponse({"url": "/object/upload/sign/private/file.pdf?token=signed"})
    )
    before = datetime.now(UTC)

    url, expires_at = await storage_provider.create_signed_upload_url("private", "folder/file.pdf")

    assert url == (
        "https://project.supabase.co/storage/v1/object/upload/sign/private/file.pdf?token=signed"
    )
    assert 7199 <= (expires_at - before).total_seconds() <= 7201
    assert StubAsyncClient.calls[0][0].endswith(
        "/storage/v1/object/upload/sign/private/folder/file.pdf"
    )


@pytest.mark.asyncio
async def test_supabase_signed_download_url_has_requested_expiry(
    storage_provider: SupabaseStorageProvider,
) -> None:
    StubAsyncClient.responses.append(
        StubResponse({"signedURL": "/object/sign/private/file.pdf?token=signed"})
    )
    before = datetime.now(UTC)

    url, expires_at = await storage_provider.create_signed_download_url(
        "private", "folder/file.pdf", 300
    )

    assert url.endswith("?token=signed&download=")
    assert 299 <= (expires_at - before).total_seconds() <= 301
    assert StubAsyncClient.calls[0][1]["json"] == {"expiresIn": 300}


@pytest.mark.asyncio
async def test_supabase_put_object_uses_private_storage_object_endpoint(
    storage_provider: SupabaseStorageProvider,
) -> None:
    StubAsyncClient.responses.append(StubResponse({}))

    await storage_provider.put_object(
        "ai-artifacts", "documents/id/parsed/result.json", b'{"pages":[]}', "application/json"
    )

    url, kwargs = StubAsyncClient.calls[0]
    assert url.endswith("/storage/v1/object/ai-artifacts/documents/id/parsed/result.json")
    assert kwargs["content"] == b'{"pages":[]}'
    assert kwargs["headers"]["Content-Type"] == "application/json"  # type: ignore[index]
    assert kwargs["headers"]["x-upsert"] == "false"  # type: ignore[index]


@pytest.mark.asyncio
async def test_supabase_private_bucket_handles_nosuchbucket_400(
    storage_provider: SupabaseStorageProvider,
) -> None:
    StubAsyncClient.responses.extend(
        [
            StubResponse(
                {"statusCode": "404", "error": "Bucket not found", "code": "NoSuchBucket"},
                status_code=400,
            ),
            StubResponse({"name": "rag-knowledge"}),
        ]
    )

    await storage_provider.ensure_private_bucket("rag-knowledge")

    assert StubAsyncClient.calls[0][0].endswith("/storage/v1/bucket/rag-knowledge")
    assert StubAsyncClient.calls[1][1]["json"] == {
        "id": "rag-knowledge",
        "name": "rag-knowledge",
        "public": False,
    }


@pytest.mark.asyncio
async def test_supabase_storage_maps_unicode_key_segments_deterministically(
    storage_provider: SupabaseStorageProvider,
) -> None:
    StubAsyncClient.responses.append(StubResponse({}))

    await storage_provider.put_object(
        "rag-knowledge", "case_reference/case_2002다27620/original.pdf", b"pdf", "application/pdf"
    )

    url = StubAsyncClient.calls[0][0]
    assert "case_2002다27620" not in url
    assert "/case_reference/unicode-" in url
    assert url.endswith("/original.pdf")
