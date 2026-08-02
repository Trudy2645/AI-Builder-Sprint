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
    KnowledgeFileRecord,
    LanguageModelRequest,
    ParsedBlock,
    ParsedPage,
    VectorStoreFileRecord,
    VectorStoreRecord,
)


class FakeAIProvider:
    """Deterministic provider used by every AI workflow test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._failures: dict[str, deque[AIProviderError]] = defaultdict(deque)
        self._structured_outputs: dict[str, deque[dict[str, Any] | BaseModel]] = defaultdict(deque)
        self.structured_requests: list[LanguageModelRequest] = []
        self.parse_result: DocumentParseResult | None = None
        self.extraction_result: ContractExtraction | None = None
        self.search_result = FileSearchResult(hits=[])
        self.search_requests: list[FileSearchRequest] = []
        self.vector_stores: dict[str, VectorStoreRecord] = {}
        self.knowledge_files: dict[str, bytes] = {}
        self.vector_store_files: dict[tuple[str, str], VectorStoreFileRecord] = {}
        self.vector_store_attributes: dict[tuple[str, str], dict[str, str | int | bool]] = {}

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
        self.structured_requests.append(request)
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
        self.search_requests.append(request)
        self._raise_queued("file_search")
        return self.search_result

    async def list_vector_stores(self) -> list[VectorStoreRecord]:
        self.calls.append(("vector_store_list", "all"))
        self._raise_queued("vector_store_list")
        return list(self.vector_stores.values())

    async def create_vector_store(self, name: str) -> VectorStoreRecord:
        self.calls.append(("vector_store_create", name))
        self._raise_queued("vector_store_create")
        record = VectorStoreRecord(id=f"vs-{len(self.vector_stores) + 1}", name=name)
        self.vector_stores[record.id] = record
        return record

    async def upload_knowledge_file(
        self, filename: str, content: bytes, mime_type: str
    ) -> KnowledgeFileRecord:
        del mime_type
        self.calls.append(("knowledge_file_upload", filename))
        self._raise_queued("knowledge_file_upload")
        file_id = f"file-{len(self.knowledge_files) + 1}"
        self.knowledge_files[file_id] = content
        return KnowledgeFileRecord(id=file_id, filename=filename)

    async def attach_vector_store_file(
        self, vector_store_id: str, file_id: str, attributes: dict[str, str | int | bool]
    ) -> VectorStoreFileRecord:
        self.calls.append(("vector_store_attach", file_id))
        self._raise_queued("vector_store_attach")
        record = VectorStoreFileRecord(id=file_id, status="completed")
        self.vector_store_files[(vector_store_id, file_id)] = record
        self.vector_store_attributes[(vector_store_id, file_id)] = attributes
        return record

    async def get_vector_store_file(
        self, vector_store_id: str, file_id: str
    ) -> VectorStoreFileRecord:
        self.calls.append(("vector_store_file_get", file_id))
        self._raise_queued("vector_store_file_get")
        return self.vector_store_files[(vector_store_id, file_id)]

    def _raise_queued(self, operation: str) -> None:
        queue = self._failures[operation]
        if queue:
            raise queue.popleft()
