from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.ai.schemas import (
    ContractExtraction,
    DocumentInput,
    DocumentParseResult,
    FileSearchRequest,
    FileSearchResult,
    LanguageModelRequest,
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
    async def extract_information(
        self, document: DocumentInput, parsed: DocumentParseResult
    ) -> ContractExtraction: ...


class LanguageModelProvider(Protocol):
    async def generate_structured(
        self,
        request: LanguageModelRequest,
        response_model: type[StructuredOutputT],
    ) -> StructuredOutputT: ...


class FileSearchProvider(Protocol):
    async def search_files(self, request: FileSearchRequest) -> FileSearchResult: ...
