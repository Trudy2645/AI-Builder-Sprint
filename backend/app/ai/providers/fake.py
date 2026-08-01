from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel

from app.ai.providers.base import AIProviderError, StructuredOutputT
from app.ai.schemas import (
    ContractExtraction,
    DocumentInput,
    DocumentParseResult,
    ExtractedSection,
    FileSearchRequest,
    FileSearchResult,
    LanguageModelRequest,
    ParsedBlock,
    ParsedPage,
)


class FakeAIProvider:
    """Deterministic provider used by every AI workflow test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._failures: dict[str, deque[AIProviderError]] = defaultdict(deque)
        self._structured_outputs: dict[str, deque[dict[str, Any] | BaseModel]] = defaultdict(deque)
        self.parse_result: DocumentParseResult | None = None
        self.extraction_result: ContractExtraction | None = None
        self.search_result = FileSearchResult(hits=[])

    def queue_failure(self, operation: str, error: AIProviderError) -> None:
        self._failures[operation].append(error)

    def queue_structured_output(self, task_type: str, output: dict[str, Any] | BaseModel) -> None:
        self._structured_outputs[task_type].append(output)

    async def parse_document(self, document: DocumentInput) -> DocumentParseResult:
        self.calls.append(("document_parse", document.filename))
        self._raise_queued("document_parse")
        if self.parse_result is not None:
            return self.parse_result
        text = document.content.decode("utf-8", errors="replace")
        block = ParsedBlock(
            block_id="fake-page-1-block-1",
            block_type="paragraph",
            content=text,
            page_number=1,
        )
        return DocumentParseResult(
            pages=[ParsedPage(page_number=1, blocks=[block])],
            markdown=text,
            provider_request_id="fake-document-parse-request",
        )

    async def extract_information(
        self, document: DocumentInput, parsed: DocumentParseResult
    ) -> ContractExtraction:
        del parsed
        self.calls.append(("information_extract", document.filename))
        self._raise_queued("information_extract")
        if self.extraction_result is not None:
            return self.extraction_result
        missing = ExtractedSection(missing=True)
        return ContractExtraction(
            price=missing,
            service_period=missing,
            cancellation=missing,
            refund=missing,
            safety=missing,
            compensation=missing,
            liability=missing,
            provider_request_id="fake-information-extract-request",
        )

    async def generate_structured(
        self,
        request: LanguageModelRequest,
        response_model: type[StructuredOutputT],
    ) -> StructuredOutputT:
        self.calls.append(("language_model", request.task_type))
        self._raise_queued(request.task_type)
        queue = self._structured_outputs[request.task_type]
        if not queue:
            raise RuntimeError(f"No fake output configured for {request.task_type}.")
        output = queue.popleft()
        if isinstance(output, response_model):
            return output
        raw = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
        return response_model.model_validate(raw)

    async def search_files(self, request: FileSearchRequest) -> FileSearchResult:
        self.calls.append(("file_search", request.query))
        self._raise_queued("file_search")
        return self.search_result

    def _raise_queued(self, operation: str) -> None:
        queue = self._failures[operation]
        if queue:
            raise queue.popleft()
