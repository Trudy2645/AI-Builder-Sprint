from __future__ import annotations

import asyncio
import base64
import json
import re
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
    InformationExtractionResult,
    KnowledgeFileRecord,
    LanguageModelRequest,
    ParsedBlock,
    ParsedPage,
    VectorStoreFileRecord,
    VectorStoreRecord,
)

Sleep = Callable[[float], Awaitable[None]]
RequestFactory = Callable[[], Awaitable[httpx.Response]]

_EXTRACTION_FIELDS: dict[str, tuple[str, str, str, str]] = {
    "price_amount_minor": (
        "price",
        "amount_minor",
        "integer",
        "The price amount as an integer without separators. Omit when absent.",
    ),
    "price_currency": (
        "price",
        "currency",
        "string",
        "ISO 4217 currency code explicitly stated or unambiguously denoted. Omit when absent.",
    ),
    "price_unit": (
        "price",
        "price_unit",
        "string",
        "The billing unit such as per room, per person, or per vehicle. Omit when absent.",
    ),
    "service_start_date": (
        "service_period",
        "start_date",
        "string",
        "Service start date in YYYY-MM-DD only when the full date is stated. Omit when absent.",
    ),
    "service_end_date": (
        "service_period",
        "end_date",
        "string",
        "Service end date in YYYY-MM-DD only when the full date is stated. Omit when absent.",
    ),
    "cancellation_policy": (
        "cancellation",
        "policy",
        "string",
        "Cancellation deadlines, fees, and conditions exactly grounded in the document. "
        "Omit when absent.",
    ),
    "refund_policy": (
        "refund",
        "policy",
        "string",
        "Refund timing, amount, and conditions exactly grounded in the document. Omit when absent.",
    ),
    "safety_terms": (
        "safety",
        "terms",
        "string",
        "Safety obligations and incident procedures exactly grounded in the document. "
        "Omit when absent.",
    ),
    "compensation_terms": (
        "compensation",
        "terms",
        "string",
        "Compensation, penalty, or damages terms exactly grounded in the document. "
        "Omit when absent.",
    ),
    "liability_terms": (
        "liability",
        "terms",
        "string",
        "Liability allocation, limits, and exclusions exactly grounded in the document. "
        "Omit when absent.",
    ),
    "termination_terms": (
        "termination",
        "terms",
        "string",
        "Contract termination, cure period, and dispute resolution terms exactly grounded "
        "in the document. Omit when absent.",
    ),
}


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

    async def request_information_extraction(
        self, document: DocumentInput
    ) -> InformationExtractionResult:
        # Universal Extraction is mapped only here; the domain task remains
        # `information_extract` regardless of the provider product name.
        encoded_document = base64.b64encode(document.content).decode("ascii")
        properties = {
            provider_field: {"type": field_type, "description": description}
            for provider_field, (_, _, field_type, description) in _EXTRACTION_FIELDS.items()
        }
        response = await self._post(
            f"{self._document_base_url}/information-extraction",
            json_body={
                "model": "information-extract",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        f"data:application/octet-stream;base64,{encoded_document}"
                                    )
                                },
                            }
                        ],
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "busan_link_contract_terms",
                        "schema": {"type": "object", "properties": properties},
                    },
                },
                "mode": "enhanced",
                "location": True,
                "location_granularity": "element",
                "split": False,
                "confidence": True,
            },
        )
        payload = self._json(response)
        try:
            message = payload["choices"][0]["message"]
            values = self._json_value(message["content"])
            additional_values = self._additional_values(message)
            return InformationExtractionResult(
                values=values,
                additional_values=additional_values,
                provider_request_id=response.headers.get("x-request-id"),
            )
        except (KeyError, IndexError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc

    def map_information_extraction(
        self, result: InformationExtractionResult, parsed: DocumentParseResult
    ) -> ContractExtraction:
        try:
            return self._map_contract_extraction(
                result.values,
                result.additional_values,
                parsed,
                result.provider_request_id,
            )
        except ValidationError as exc:
            raise AIProviderInvalidResponseError from exc

    async def extract_information(
        self, document: DocumentInput, parsed: DocumentParseResult
    ) -> ContractExtraction:
        result = await self.request_information_extraction(document)
        return self.map_information_extraction(result, parsed)

    @staticmethod
    def _json_value(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise AIProviderInvalidResponseError from exc
        if not isinstance(value, dict):
            raise AIProviderInvalidResponseError
        return value

    @classmethod
    def _additional_values(cls, message: dict[str, Any]) -> dict[str, Any]:
        tool_calls = message.get("tool_calls") or []
        for tool_call in tool_calls:
            function = tool_call.get("function") if isinstance(tool_call, dict) else None
            if not isinstance(function, dict) or function.get("name") != "additional_values":
                continue
            arguments = cls._json_value(function.get("arguments", {}))
            nested = arguments.get("additional_values")
            return nested if isinstance(nested, dict) else arguments
        return {}

    @classmethod
    def _map_contract_extraction(
        cls,
        values: dict[str, Any],
        additional_values: dict[str, Any],
        parsed: DocumentParseResult,
        provider_request_id: str | None,
    ) -> ContractExtraction:
        sections: dict[str, dict[str, Any]] = {
            name: {"fields": {}, "missing": True}
            for name in (
                "price",
                "service_period",
                "cancellation",
                "refund",
                "safety",
                "compensation",
                "liability",
                "termination",
            )
        }
        for provider_field, (section_name, field_name, _, _) in _EXTRACTION_FIELDS.items():
            value = values.get(provider_field)
            if value is None or value == "":
                continue
            metadata = additional_values.get(provider_field)
            metadata = metadata if isinstance(metadata, dict) else {}
            source_page = cls._source_page(metadata)
            bbox = cls._bounding_box(metadata)
            sections[section_name]["missing"] = False
            sections[section_name]["fields"][field_name] = {
                "value": value,
                "confidence": cls._confidence(metadata.get("confidence")),
                "source_page": source_page,
                "source_quote": cls._source_quote(parsed, source_page, value),
                "bbox": bbox,
                "missing": False,
            }
        return ContractExtraction.model_validate(
            {
                **sections,
                "provider_request_id": provider_request_id,
                "model_name": "information-extract",
            }
        )

    @staticmethod
    def _confidence(value: Any) -> float | None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return min(1.0, max(0.0, float(value)))
        if isinstance(value, str):
            normalized = value.lower()
            if normalized == "high":
                return 1.0
            if normalized == "low":
                return 0.0
        return None

    @staticmethod
    def _source_page(metadata: dict[str, Any]) -> int | None:
        location = metadata.get("location")
        location = location if isinstance(location, dict) else metadata
        value = location.get("page") or location.get("page_number")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _bounding_box(cls, metadata: dict[str, Any]) -> dict[str, float] | None:
        location = metadata.get("location")
        location = location if isinstance(location, dict) else metadata
        coordinates = location.get("coordinates") or location.get("bounding_box")
        if isinstance(coordinates, dict):
            if all(key in coordinates for key in ("x", "y", "width", "height")):
                return {key: float(coordinates[key]) for key in ("x", "y", "width", "height")}
            coordinates = coordinates.get("vertices") or coordinates.get("points")
        if not isinstance(coordinates, list):
            return None
        points: list[tuple[float, float]] = []
        for point in coordinates:
            if isinstance(point, dict) and "x" in point and "y" in point:
                points.append((float(point["x"]), float(point["y"])))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
        if not points:
            return None
        xs, ys = zip(*points, strict=True)
        return {
            "x": min(xs),
            "y": min(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

    @staticmethod
    def _source_quote(
        parsed: DocumentParseResult, source_page: int | None, value: Any
    ) -> str | None:
        if source_page is None:
            return None
        pages = [page for page in parsed.pages if page.page_number == source_page]
        if not pages:
            return None
        needle = re.sub(r"[\s,]", "", str(value)).lower()
        blocks = pages[0].blocks
        for block in blocks:
            haystack = re.sub(r"[\s,]", "", block.content).lower()
            if needle and needle in haystack:
                return block.content[:500]
        return blocks[0].content[:500] if blocks else None

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
                    locations = [part for part in content if isinstance(part, dict)]
                    content = "\n".join(
                        str(part.get("text", "")) if isinstance(part, dict) else str(part)
                        for part in content
                    )
                else:
                    locations = []
                metadata = dict(item.get("attributes") or item.get("metadata") or {})
                location = locations[0] if locations else item
                for source_key, target_key in (
                    ("page_number", "page_start"),
                    ("page", "page_start"),
                    ("page_start", "page_start"),
                    ("page_end", "page_end"),
                    ("section", "section_path"),
                    ("section_path", "section_path"),
                    ("bbox", "bbox"),
                ):
                    if source_key in location and target_key not in metadata:
                        metadata[target_key] = location[source_key]
                if "page_start" in metadata and "page_end" not in metadata:
                    metadata["page_end"] = metadata["page_start"]
                hits.append(
                    FileSearchHit(
                        file_id=item.get("file_id") or item["id"],
                        chunk_id=item.get("chunk_id"),
                        score=item.get("score"),
                        excerpt=content,
                        metadata=metadata,
                    )
                )
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc
        return FileSearchResult(
            hits=hits,
            provider_request_id=response.headers.get("x-request-id"),
        )

    async def list_vector_stores(self) -> list[VectorStoreRecord]:
        response = await self._get(f"{self._agent_base_url}/vector_stores")
        payload = self._json(response)
        try:
            return [
                VectorStoreRecord(
                    id=item["id"],
                    name=item["name"],
                    status=item.get("status"),
                )
                for item in payload.get("data", [])
            ]
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc

    async def create_vector_store(self, name: str) -> VectorStoreRecord:
        response = await self._post(
            f"{self._agent_base_url}/vector_stores", json_body={"name": name}
        )
        payload = self._json(response)
        try:
            return VectorStoreRecord(
                id=payload["id"], name=payload["name"], status=payload.get("status")
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc

    async def upload_knowledge_file(
        self, filename: str, content: bytes, mime_type: str
    ) -> KnowledgeFileRecord:
        response = await self._post(
            f"{self._agent_base_url}/files",
            files={"file": (filename, content, mime_type)},
            data={"purpose": "user_data"},
        )
        payload = self._json(response)
        try:
            return KnowledgeFileRecord(
                id=payload["id"], filename=payload.get("filename") or filename
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc

    async def attach_vector_store_file(
        self, vector_store_id: str, file_id: str, attributes: dict[str, str | int | bool]
    ) -> VectorStoreFileRecord:
        response = await self._post(
            f"{self._agent_base_url}/vector_stores/{vector_store_id}/files",
            json_body={"file_id": file_id, "attributes": attributes},
        )
        return self._vector_store_file(response)

    async def get_vector_store_file(
        self, vector_store_id: str, file_id: str
    ) -> VectorStoreFileRecord:
        response = await self._get(
            f"{self._agent_base_url}/vector_stores/{vector_store_id}/files/{file_id}"
        )
        return self._vector_store_file(response)

    def _vector_store_file(self, response: httpx.Response) -> VectorStoreFileRecord:
        payload = self._json(response)
        error = payload.get("last_error")
        if isinstance(error, dict):
            error = error.get("message") or error.get("code")
        try:
            return VectorStoreFileRecord(
                id=payload["id"], status=payload["status"], last_error=error
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise AIProviderInvalidResponseError from exc

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

    async def _get(self, url: str) -> httpx.Response:
        async def send() -> httpx.Response:
            if self._client is not None:
                return await self._client.get(url, headers=self._headers, timeout=self._timeout)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                return await client.get(url, headers=self._headers)

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
                coordinates = UpstageAIProvider._bounding_box(element)
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
