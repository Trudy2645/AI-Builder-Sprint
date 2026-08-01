from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError

from app.ai.providers.base import (
    AIProviderInvalidResponseError,
    AIProviderPermanentError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    StructuredOutputT,
)
from app.ai.schemas import (
    BoundingBox,
    ContractExtraction,
    DocumentInput,
    DocumentParseResult,
    FileSearchHit,
    FileSearchRequest,
    FileSearchResult,
    LanguageModelRequest,
    ParsedBlock,
    ParsedPage,
)

Sleep = Callable[[float], Awaitable[None]]
RequestFactory = Callable[[], Awaitable[httpx.Response]]


class UpstageAIProvider:
    """HTTP adapter for Upstage fixed-function APIs.

    It deliberately exposes no workflow or database operations. Provider response
    bodies are validated before they cross the adapter boundary.
    """

    def __init__(
        self,
        *,
        api_key: str,
        document_base_url: str,
        chat_base_url: str,
        agent_base_url: str,
        chat_model: str,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Upstage API key is required.")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._document_base_url = document_base_url.rstrip("/")
        self._chat_base_url = chat_base_url.rstrip("/")
        self._agent_base_url = agent_base_url.rstrip("/")
        self._chat_model = chat_model
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_retries = max_retries
        self._client = client
        self._sleep = sleep

    async def parse_document(self, document: DocumentInput) -> DocumentParseResult:
        response = await self._post(
            f"{self._document_base_url}/document-digitization",
            files={"document": (document.filename, document.content, document.mime_type)},
            data={
                "model": "document-parse",
                "ocr": "auto",
                "base64_encoding": "[]",
            },
        )
        payload = self._json(response)
        return self._parse_document_response(payload, response.headers.get("x-request-id"))

    async def extract_information(
        self, document: DocumentInput, parsed: DocumentParseResult
    ) -> ContractExtraction:
        # Universal Extraction is mapped only here; the domain task remains
        # `information_extract` regardless of the provider product name.
        response = await self._post(
            f"{self._document_base_url}/information-extraction",
            files={"document": (document.filename, document.content, document.mime_type)},
            data={
                "model": "information-extract",
                "schema": json.dumps(ContractExtraction.model_json_schema()),
                "parsed_document": parsed.model_dump_json(exclude={"provider_request_id"}),
            },
        )
        payload = self._json(response)
        candidate = payload.get("result", payload.get("data", payload))
        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise AIProviderInvalidResponseError from exc
        if isinstance(candidate, dict):
            candidate.setdefault("provider_request_id", response.headers.get("x-request-id"))
            candidate.setdefault("model_name", "information-extract")
        try:
            return ContractExtraction.model_validate(candidate)
        except ValidationError as exc:
            raise AIProviderInvalidResponseError from exc

    async def generate_structured(
        self,
        request: LanguageModelRequest,
        response_model: type[StructuredOutputT],
    ) -> StructuredOutputT:
        body: dict[str, Any] = {
            "model": self._chat_model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(request.input_data, ensure_ascii=False),
                },
            ],
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.task_type,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        }
        if request.reasoning_effort is not None:
            body["reasoning_effort"] = request.reasoning_effort
        response = await self._post(f"{self._chat_base_url}/chat/completions", json_body=body)
        payload = self._json(response)
        try:
            content = payload["choices"][0]["message"]["content"]
            candidate = json.loads(content) if isinstance(content, str) else content
            return response_model.model_validate(candidate)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc

    async def search_files(self, request: FileSearchRequest) -> FileSearchResult:
        response = await self._post(
            f"{self._agent_base_url}/vector_stores/{request.vector_store_id}/search",
            json_body={
                "query": request.query,
                "filters": request.filters,
                "max_num_results": request.top_k,
            },
        )
        payload = self._json(response)
        raw_hits = payload.get("data", payload.get("results", []))
        if not isinstance(raw_hits, list):
            raise AIProviderInvalidResponseError
        hits: list[FileSearchHit] = []
        try:
            for item in raw_hits:
                content = item.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(
                        str(part.get("text", "")) if isinstance(part, dict) else str(part)
                        for part in content
                    )
                hits.append(
                    FileSearchHit(
                        file_id=item.get("file_id") or item["id"],
                        chunk_id=item.get("chunk_id"),
                        score=item.get("score"),
                        excerpt=content,
                        metadata=item.get("attributes") or item.get("metadata") or {},
                    )
                )
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc
        return FileSearchResult(
            hits=hits,
            provider_request_id=response.headers.get("x-request-id"),
        )

    async def _post(
        self,
        url: str,
        *,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            if self._client is not None:
                return await self._client.post(
                    url,
                    headers=self._headers,
                    files=files,
                    data=data,
                    json=json_body,
                    timeout=self._timeout,
                )
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                return await client.post(
                    url,
                    headers=self._headers,
                    files=files,
                    data=data,
                    json=json_body,
                )

        return await self._request_with_retry(send)

    async def _request_with_retry(self, send: RequestFactory) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await send()
            except httpx.TimeoutException as exc:
                if attempt == self._max_retries:
                    raise AIProviderTimeoutError from exc
                await self._sleep(0.5 * (2**attempt))
                continue
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise AIProviderTemporaryError from exc
                await self._sleep(0.5 * (2**attempt))
                continue
            if response.status_code == 429:
                if attempt == self._max_retries:
                    raise AIProviderRateLimitError
                await self._sleep(0.5 * (2**attempt))
                continue
            if 500 <= response.status_code <= 599:
                if attempt == self._max_retries:
                    raise AIProviderTemporaryError
                await self._sleep(0.5 * (2**attempt))
                continue
            if response.is_error:
                raise AIProviderPermanentError
            return response
        raise AssertionError("Retry loop exited unexpectedly.")

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise AIProviderInvalidResponseError from exc
        if not isinstance(payload, dict):
            raise AIProviderInvalidResponseError
        return payload

    @staticmethod
    def _parse_document_response(
        payload: dict[str, Any], provider_request_id: str | None
    ) -> DocumentParseResult:
        content = payload.get("content") or {}
        markdown = content.get("markdown") if isinstance(content, dict) else None
        html = content.get("html") if isinstance(content, dict) else None
        elements = payload.get("elements") or []
        pages: dict[int, list[ParsedBlock]] = {}
        try:
            for index, element in enumerate(elements, start=1):
                page_number = int(element.get("page", element.get("page_number", 1)))
                coordinates = element.get("bounding_box") or element.get("bbox")
                bbox = BoundingBox.model_validate(coordinates) if coordinates else None
                block = ParsedBlock(
                    block_id=str(element.get("id", f"block-{index}")),
                    block_type=str(element.get("category", element.get("type", "paragraph"))),
                    content=str(element.get("content", element.get("text", ""))),
                    page_number=page_number,
                    bbox=bbox,
                )
                pages.setdefault(page_number, []).append(block)
            return DocumentParseResult(
                pages=[
                    ParsedPage(page_number=number, blocks=blocks)
                    for number, blocks in sorted(pages.items())
                ],
                markdown=markdown,
                html=html,
                provider_request_id=provider_request_id,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc
