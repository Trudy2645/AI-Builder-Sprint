from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import quote

import httpx


class StorageProviderError(Exception):
    pass


class StorageObjectNotFoundError(StorageProviderError):
    pass


class StorageProvider(Protocol):
    async def ensure_private_bucket(self, bucket: str) -> None: ...

    async def create_signed_upload_url(
        self, bucket: str, object_path: str
    ) -> tuple[str, datetime]: ...

    async def create_signed_download_url(
        self, bucket: str, object_path: str, expires_in: int
    ) -> tuple[str, datetime]: ...

    def iter_object(self, bucket: str, object_path: str) -> AsyncIterator[bytes]: ...

    async def put_object(
        self, bucket: str, object_path: str, content: bytes, content_type: str
    ) -> None: ...


class SupabaseStorageProvider:
    """Small Storage REST adapter; file bodies are consumed as an async stream."""

    _SIGNED_UPLOAD_LIFETIME_SECONDS = 2 * 60 * 60

    async def ensure_private_bucket(self, bucket: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/bucket/{quote(bucket, safe='')}", headers=self._headers
                )
                payload = _json_object(response)
                bucket_missing = response.status_code == 404 or (
                    response.status_code == 400
                    and (
                        payload.get("code") == "NoSuchBucket"
                        or str(payload.get("statusCode")) == "404"
                    )
                )
                if bucket_missing:
                    response = await client.post(
                        f"{self._base_url}/bucket",
                        headers={**self._headers, "Content-Type": "application/json"},
                        json={"id": bucket, "name": bucket, "public": False},
                    )
                response.raise_for_status()
                payload = _json_object(response)
                if payload.get("public") is True:
                    raise StorageProviderError("RAG knowledge bucket must be private.")
            except StorageProviderError:
                raise
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise StorageProviderError from exc

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        timeout_seconds: float,
    ) -> None:
        self._project_url = supabase_url.rstrip("/")
        self._base_url = f"{self._project_url}/storage/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }
        self._timeout = httpx.Timeout(timeout_seconds)

    async def create_signed_upload_url(self, bucket: str, object_path: str) -> tuple[str, datetime]:
        encoded = self._encoded_path(bucket, object_path)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/object/upload/sign/{encoded}",
                    headers=self._headers,
                    json={"upsert": False},
                )
                response.raise_for_status()
                payload = response.json()
                signed_url = (
                    payload.get("url") or payload.get("signedURL") or payload.get("signedUrl")
                )
                if not signed_url:
                    raise StorageProviderError("Storage did not return a signed upload URL.")
                return self._absolute_url(signed_url), datetime.now(UTC) + timedelta(
                    seconds=self._SIGNED_UPLOAD_LIFETIME_SECONDS
                )
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise StorageProviderError from exc

    async def create_signed_download_url(
        self, bucket: str, object_path: str, expires_in: int
    ) -> tuple[str, datetime]:
        encoded = self._encoded_path(bucket, object_path)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/object/sign/{encoded}",
                    headers=self._headers,
                    json={"expiresIn": expires_in},
                )
                response.raise_for_status()
                payload = response.json()
                signed_url = payload.get("signedURL") or payload.get("signedUrl")
                if not signed_url:
                    raise StorageProviderError("Storage did not return a signed download URL.")
                absolute_url = self._absolute_url(signed_url)
                separator = "&" if "?" in absolute_url else "?"
                return (
                    f"{absolute_url}{separator}download=",
                    datetime.now(UTC) + timedelta(seconds=expires_in),
                )
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise StorageProviderError from exc

    async def iter_object(self, bucket: str, object_path: str) -> AsyncIterator[bytes]:
        encoded = self._encoded_path(bucket, object_path)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                async with client.stream(
                    "GET", f"{self._base_url}/object/{encoded}", headers=self._headers
                ) as response:
                    if response.status_code == 404:
                        raise StorageObjectNotFoundError
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except StorageObjectNotFoundError:
                raise
            except httpx.HTTPError as exc:
                raise StorageProviderError from exc

    async def put_object(
        self, bucket: str, object_path: str, content: bytes, content_type: str
    ) -> None:
        encoded = self._encoded_path(bucket, object_path)
        headers = {**self._headers, "Content-Type": content_type, "x-upsert": "false"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/object/{encoded}", headers=headers, content=content
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise StorageProviderError from exc

    @staticmethod
    def _encoded_path(bucket: str, object_path: str) -> str:
        safe_path = "/".join(_storage_safe_segment(part) for part in object_path.split("/"))
        return f"{quote(bucket, safe='')}/{quote(safe_path, safe='/')}"

    def _absolute_url(self, value: str) -> str:
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if value.startswith("/storage/v1/"):
            return f"{self._project_url}{value}"
        return f"{self._base_url}{value if value.startswith('/') else f'/{value}'}"


def _json_object(response: httpx.Response) -> dict[str, object]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("Storage response must be a JSON object.")
    return payload


def _storage_safe_segment(value: str) -> str:
    if value.isascii():
        return value
    digest = hashlib.sha256(value.encode()).hexdigest()[:24]
    return f"unicode-{digest}"


class FakeStorageProvider:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.unavailable = False
        self.upload_url_calls = 0
        self.download_url_calls = 0
        self.private_buckets: set[str] = set()

    async def ensure_private_bucket(self, bucket: str) -> None:
        self._check_available()
        self.private_buckets.add(bucket)

    async def create_signed_upload_url(self, bucket: str, object_path: str) -> tuple[str, datetime]:
        self._check_available()
        self.upload_url_calls += 1
        expires_at = datetime.now(UTC) + timedelta(hours=2)
        return f"https://storage.test/upload/{bucket}/{object_path}?token=fake", expires_at

    async def create_signed_download_url(
        self, bucket: str, object_path: str, expires_in: int
    ) -> tuple[str, datetime]:
        self._check_available()
        self.download_url_calls += 1
        if (bucket, object_path) not in self.objects:
            raise StorageObjectNotFoundError
        return (
            f"https://storage.test/download/{bucket}/{object_path}?token=fake",
            datetime.now(UTC) + timedelta(seconds=expires_in),
        )

    async def iter_object(self, bucket: str, object_path: str) -> AsyncIterator[bytes]:
        self._check_available()
        try:
            data = self.objects[(bucket, object_path)]
        except KeyError as exc:
            raise StorageObjectNotFoundError from exc
        for offset in range(0, len(data), 8192):
            yield data[offset : offset + 8192]

    def put(self, bucket: str, object_path: str, data: bytes) -> None:
        self.objects[(bucket, object_path)] = data

    async def put_object(
        self, bucket: str, object_path: str, content: bytes, content_type: str
    ) -> None:
        del content_type
        self._check_available()
        key = (bucket, object_path)
        if key in self.objects:
            raise StorageProviderError
        self.objects[key] = content

    def _check_available(self) -> None:
        if self.unavailable:
            raise StorageProviderError
