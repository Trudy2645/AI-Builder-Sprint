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

    def __init__(self, *, enable_default_outputs: bool = False) -> None:
        self._enable_default_outputs = enable_default_outputs
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
            if not self._enable_default_outputs:
                raise RuntimeError(f"No fake output configured for {request.task_type}.")
            output = self._default_structured_output(request)
        else:
            output = queue.popleft()
        if isinstance(output, response_model):
            return output
        raw = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
        return response_model.model_validate(raw)

    @staticmethod
    def _default_structured_output(request: LanguageModelRequest) -> dict[str, Any]:
        """Return deterministic local-dev output while preserving explicit test queues."""
        if request.task_type == "contract_generate":
            terms = request.input_data.get("terms", {})
            if not isinstance(terms, dict):
                terms = {}
            labels = {
                "service_start_date": "공급 시작일",
                "service_end_date": "공급 종료일",
                "supply_quantity": "공급 수량",
                "supply_quantity_description": "공급 수량 설명",
                "quantity_unit": "수량 단위",
                "minimum_quantity": "최소 수량",
                "maximum_quantity": "최대 수량",
                "people_per_unit": "단위당 인원",
                "base_price_amount_minor": "기준 단가",
                "currency": "통화",
                "price_unit": "가격 단위",
                "minimum_people": "최소 인원",
                "maximum_people": "최대 인원",
                "cancellation_policy": "취소 조건",
                "no_show_policy": "노쇼 조건",
                "refund_policy": "환불 조건",
                "settlement_policy": "정산 조건",
                "safety_policy": "안전 조건",
                "compensation_policy": "보상 조건",
                "liability_policy": "책임 조건",
                "termination_policy": "계약 해지 조건",
                "special_terms": "특약",
            }
            clauses = [
                {
                    "clause_key": key,
                    "title": labels.get(key, key.replace("_", " ")),
                    "body": f"{labels.get(key, key)}: {value}",
                }
                for key, value in terms.items()
                if value is not None and (not isinstance(value, str) or value.strip())
            ]
            return {"clauses": clauses}
        if request.task_type == "contract_review":
            raw_findings = request.input_data.get("rule_findings", [])
            findings = []
            if isinstance(raw_findings, list):
                for item in raw_findings:
                    if not isinstance(item, dict):
                        continue
                    findings.append(
                        {
                            "clause_id": item.get("clause_id"),
                            "category": item.get("category", "contract_terms"),
                            "severity": item.get("severity", "medium"),
                            "importance": item.get("importance", "medium"),
                            "title": item.get("title", "계약 조건 확인이 필요합니다"),
                            "explanation": item.get(
                                "explanation", "당사자가 계약 조건을 확인해야 합니다."
                            ),
                            "suggested_text": item.get("suggested_text"),
                            "grounding_status": "insufficient_evidence",
                            "confidence": None,
                            "source_location": item.get("source_location", {}),
                            "evidence_ids": [],
                            "disclaimer": "법률 자문이 아닌 계약 검토 보조 의견입니다.",
                            "is_public": False,
                        }
                    )
            return {"tool_calls": [{"name": "submit_review", "arguments": {"findings": findings}}]}
        if request.task_type == "localize_explain":
            source = request.input_data.get("source", {})
            target_locale = request.input_data.get("target_locale", "ko-KR")
            if not isinstance(source, dict):
                source = {}
            return {
                "locale": target_locale,
                "title": source.get("title") or "계약 안내",
                "public_headline": source.get("public_headline"),
                "summary": source.get("summary") or "계약 조건을 확인해 주세요.",
                "easy_explanation": source.get("easy_explanation")
                or "계약의 주요 조건을 확인해 주세요.",
                "terms": source.get("terms", {}),
                "clauses": [
                    {
                        "clause_id": item["clause_id"],
                        "clause_no": item["clause_no"],
                        "title": item["title"],
                        "body": item["body"],
                        "easy_explanation": item["body"],
                    }
                    for item in source.get("clauses", [])
                ],
                "findings": [
                    {
                        "finding_id": item["finding_id"],
                        "clause_id": item.get("clause_id"),
                        "severity": item["severity"],
                        "explanation": item["explanation"],
                        "suggested_text": item.get("suggested_text"),
                        "disclaimer": item["disclaimer"],
                        "evidence_numbers": item.get("evidence_numbers", []),
                    }
                    for item in source.get("findings", [])
                ],
                "preserved_facts": source.get("preserved_facts", {}),
                "preserved_names": source.get("preserved_names", []),
                "disclaimer": source.get("disclaimer")
                or "법률 자문이 아닌 계약 검토 보조 의견입니다.",
            }
        raise RuntimeError(f"No fake output configured for {request.task_type}.")

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
