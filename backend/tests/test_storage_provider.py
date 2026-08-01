from datetime import UTC, datetime

import pytest

from app.integrations.storage import SupabaseStorageProvider


class StubResponse:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

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
