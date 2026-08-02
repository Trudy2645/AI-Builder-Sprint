from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.ai.schemas import (
    ContractExtraction,
    DocumentInput,
    DocumentParseResult,
    FileSearchRequest,
    FileSearchResult,
    InformationExtractionResult,
    KnowledgeFileRecord,
    LanguageModelRequest,
    VectorStoreFileRecord,
    VectorStoreRecord,
)

StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


class AIProviderError(Exception):
    """Base error safe for workflow-level classification."""


class AIProviderTimeoutError(AIProviderError):
    pass


class AIProviderRateLimitError(AIProviderError):
    pass


class AIProviderTemporaryError(AIProviderError):
    pass


class AIProviderPermanentError(AIProviderError):
    pass


class AIProviderInvalidResponseError(AIProviderError):
    pass


class DocumentParseProvider(Protocol):
    async def parse_document(self, document: DocumentInput) -> DocumentParseResult: ...


class InformationExtractProvider(Protocol):
    async def request_information_extraction(
        self, document: DocumentInput
    ) -> InformationExtractionResult: ...

    def map_information_extraction(
        self, result: InformationExtractionResult, parsed: DocumentParseResult
    ) -> ContractExtraction: ...


class LanguageModelProvider(Protocol):
    async def generate_structured(
        self,
        request: LanguageModelRequest,
        response_model: type[StructuredOutputT],
    ) -> StructuredOutputT: ...


class FileSearchProvider(Protocol):
    async def search_files(self, request: FileSearchRequest) -> FileSearchResult: ...


class KnowledgeBaseProvider(Protocol):
    async def list_vector_stores(self) -> list[VectorStoreRecord]: ...

    async def create_vector_store(self, name: str) -> VectorStoreRecord: ...

    async def upload_knowledge_file(
        self, filename: str, content: bytes, mime_type: str
    ) -> KnowledgeFileRecord: ...

    async def attach_vector_store_file(
        self, vector_store_id: str, file_id: str, attributes: dict[str, str | int | bool]
    ) -> VectorStoreFileRecord: ...

    async def get_vector_store_file(
        self, vector_store_id: str, file_id: str
    ) -> VectorStoreFileRecord: ...
