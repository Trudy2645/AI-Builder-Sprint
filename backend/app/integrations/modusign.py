from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


class ModusignError(Exception):
    """Base class for all Modusign integration failures."""


class ModusignUnavailableError(ModusignError):
    """Modusign could not be reached (network error, timeout, malformed response)."""


class ModusignNotFoundError(ModusignError):
    """The requested Modusign document does not exist."""


class ModusignRequestError(ModusignError):
    """Modusign rejected the request (bad template id, invalid participants, etc.)."""

    def __init__(self, *, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ModusignParticipant:
    role: str
    name: str
    email: str


@dataclass(frozen=True, slots=True)
class ModusignParticipantField:
    """A signer-controlled field placed on an already-final PDF."""

    field_type: str
    data_label: str
    position: dict[str, Any]
    size: dict[str, float] | None = None
    required: bool = True
    signature_types: list[str] | None = None

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.field_type,
            "dataLabel": self.data_label,
            "required": self.required,
            "position": self.position,
        }
        if self.size is not None:
            payload["size"] = self.size
        if self.signature_types is not None:
            payload["signatureTypes"] = self.signature_types
        return payload


def build_accommodation_template_payload(
    *,
    title: str,
    pdf_bytes: bytes,
    buyer_role: str = "바이어",
) -> dict[str, Any]:
    """Build the one-buyer accommodation template from BusanLink's final PDF.

    The PDF is the canonical contract artifact. Only the buyer signature is
    interactive in Modusign, so the text displayed in Modusign stays identical
    to the server-rendered PDF. Coordinates are normalized to the A4 page and
    target the signature line printed on page two of the accommodation sample.
    """
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("The accommodation template source must be a PDF.")
    return {
        "title": title,
        "file": {
            "base64": base64.b64encode(pdf_bytes).decode("ascii"),
            "extension": "pdf",
        },
        "participants": [
            {
                "type": "SIGNER",
                "role": buyer_role,
                "signingOrder": 1,
                "fields": [
                    {
                        "type": "SIGNATURE",
                        "required": True,
                        "dataLabel": "buyer_signature",
                        "position": {"page": 2, "x": 0.56, "y": 0.72},
                        "size": {"width": 0.30, "height": 0.06},
                    }
                ],
            }
        ],
        "requesterEditable": False,
        "metadatas": [
            {"key": "busanlink_category", "value": "accommodation"},
            {"key": "busanlink_template_version", "value": "v1"},
        ],
    }


class ModusignClient:
    """Thin async wrapper around the Modusign e-signature REST API.

    This client only proxies requests/responses; it does not persist any
    state. Callers are expected to hold on to the returned document id.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        auth_email: str,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 3,
        retry_base_seconds: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (auth_email, api_key)
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds

    async def create_accommodation_template(
        self,
        *,
        title: str,
        pdf_bytes: bytes,
    ) -> dict[str, Any]:
        """Create the reusable one-buyer accommodation template in Modusign."""
        return await self._request(
            "POST",
            "/templates",
            json=build_accommodation_template_payload(title=title, pdf_bytes=pdf_bytes),
        )

    async def create_signature_request_from_pdf(
        self,
        *,
        title: str,
        pdf_bytes: bytes,
        buyer: ModusignParticipant,
        buyer_fields: list[ModusignParticipantField],
    ) -> dict[str, Any]:
        """Request one buyer signature on the immutable contract source PDF.

        This is used for an ``as_is`` contract: the uploaded source PDF is
        preserved and only signer-controlled fields are overlaid by Modusign.
        """
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("The signature source must be a PDF.")
        return await self._request(
            "POST",
            "/documents",
            json={
                "title": title,
                "file": {
                    "base64": base64.b64encode(pdf_bytes).decode("ascii"),
                    "extension": "pdf",
                },
                "participants": [
                    {
                        "type": "SIGNER",
                        "role": buyer.role,
                        "name": buyer.name,
                        "signingOrder": 1,
                        "signingMethod": {"type": "EMAIL", "value": buyer.email},
                        "fields": [field.as_payload() for field in buyer_fields],
                    }
                ],
                "metadatas": [
                    {"key": "busanlink_flow", "value": "as_is_source_pdf"},
                ],
            },
        )

    async def create_signature_request(
        self,
        *,
        template_id: str,
        title: str,
        participants: list[ModusignParticipant],
    ) -> dict[str, Any]:
        payload = {
            "templateId": template_id,
            "document": {
                "title": title,
                "participantMappings": [
                    {
                        "role": participant.role,
                        "name": participant.name,
                        "signingMethod": {"type": "EMAIL", "value": participant.email},
                    }
                    for participant in participants
                ],
            },
        }
        response = await self._request(
            "POST",
            "/documents/request-with-template",
            json=payload,
        )
        return response

    async def get_document(self, document_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/documents/{document_id}")

    async def fetch_file(self, download_url: str) -> tuple[bytes, str]:
        """Stream a Modusign-hosted file (signed PDF / audit trail) through our
        own backend so the frontend never needs Modusign credentials."""
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds, transport=self._transport
                ) as client:
                    response = await client.get(download_url, auth=self._auth)
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise ModusignUnavailableError from exc
                await asyncio.sleep(self._retry_delay(attempt, None))
                continue
            if (
                response.status_code not in {429, 500, 502, 503, 504}
                or attempt == self._max_retries
            ):
                break
            await asyncio.sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))

        if response is None:
            raise ModusignUnavailableError

        if response.status_code == 404:
            raise ModusignNotFoundError
        if response.status_code >= 400:
            raise ModusignRequestError(status_code=response.status_code, detail=response.text)

        content_type = response.headers.get("content-type", "application/pdf")
        return response.content, content_type

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds, transport=self._transport
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        auth=self._auth,
                        headers={"Accept": "application/json"},
                        **kwargs,
                    )
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise ModusignUnavailableError from exc
                await asyncio.sleep(self._retry_delay(attempt, None))
                continue
            if (
                response.status_code not in {429, 500, 502, 503, 504}
                or attempt == self._max_retries
            ):
                break
            await asyncio.sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))

        if response is None:
            raise ModusignUnavailableError

        if response.status_code == 404:
            raise ModusignNotFoundError
        if response.status_code >= 400:
            raise ModusignRequestError(status_code=response.status_code, detail=response.text)

        try:
            return response.json()
        except ValueError as exc:
            raise ModusignUnavailableError from exc

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after).astimezone(UTC)
                    return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
                except (TypeError, ValueError):
                    pass
        return self._retry_base_seconds * (2**attempt)
