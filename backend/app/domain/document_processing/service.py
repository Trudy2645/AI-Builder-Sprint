from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, NoReturn
from uuid import UUID, uuid4

from fastapi import status
from pydantic import ValidationError

from app.ai.jobs import AIJobIdentity
from app.ai.providers.base import (
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderPermanentError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderTimeoutError,
    DocumentParseProvider,
    InformationExtractProvider,
)
from app.ai.schemas import (
    ContractExtraction,
    DocumentInput,
    DocumentParseResult,
    ExtractedSection,
    InformationExtractionResult,
    LanguageModelRequest,
    ListingMapping,
)
from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.integrations.storage import (
    StorageObjectNotFoundError,
    StorageProvider,
    StorageProviderError,
)
from app.repositories.document_processing import (
    DocumentProcessingRepository,
    DocumentProcessingRepositoryError,
    ProcessingDocumentRecord,
    ProcessingJobRecord,
)
from app.schemas.document_processing import DocumentProcessAccepted, DocumentProcessingResult

_PARSE_MODEL = "document-parse"
_EXTRACT_MODEL = "information-extract"
_ARTIFACT_BUCKET = "ai-artifacts"
_EXTRACT_CHECKPOINT_SCHEMA = "information-extraction-result-v1"
_PROCESSABLE_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
}
_CLAUSE_TITLE = re.compile(r"^(제\s*\d+\s*조|article\s+\d+)", re.IGNORECASE)
_SECTIONS = (
    "price",
    "service_period",
    "cancellation",
    "refund",
    "safety",
    "compensation",
    "liability",
    "termination",
)


@dataclass(frozen=True, slots=True)
class StartedDocumentProcessing:
    response: DocumentProcessAccepted
    should_schedule: bool


class DocumentProcessingService:
    def __init__(
        self,
        repository: DocumentProcessingRepository,
        storage: StorageProvider,
        parse_provider: DocumentParseProvider,
        extract_provider: InformationExtractProvider,
        *,
        provider_name: str,
        prompt_version: str,
        max_document_size_bytes: int,
        low_confidence_threshold: float = 0.7,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parse_provider = parse_provider
        self._extract_provider = extract_provider
        self._provider_name = provider_name
        self._prompt_version = prompt_version
        self._max_document_size_bytes = max_document_size_bytes
        self._low_confidence_threshold = low_confidence_threshold

    async def start(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
        idempotency_key: str,
    ) -> StartedDocumentProcessing:
        if not idempotency_key.strip():
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="Idempotency-Key cannot be blank.",
            )
        document = await self._get_authorized(document_id, actor, organization_header)
        self._validate_processable(document)
        parse_job = await self._ensure_job(document_id, "document_parse", _PARSE_MODEL, None)
        active_job = parse_job
        if parse_job.status == "succeeded":
            active_job = await self._ensure_job(
                document_id,
                "information_extract",
                _EXTRACT_MODEL,
                self._prompt_version,
            )
        should_schedule = active_job.status == "queued"
        if should_schedule:
            try:
                await self._repository.mark_document_processing(document_id)
            except DocumentProcessingRepositoryError as exc:
                self._database_unavailable(exc)
        return StartedDocumentProcessing(
            response=DocumentProcessAccepted(
                document_id=document_id,
                job_id=active_job.id,
                task_type=active_job.job_type,  # type: ignore[arg-type]
                status=active_job.status,  # type: ignore[arg-type]
            ),
            should_schedule=should_schedule,
        )

    async def run(self, document_id: UUID, job_id: UUID, task_type: str) -> None:
        try:
            document = await self._repository.get_document(document_id)
            if document is None:
                return
            if task_type == "document_parse":
                await self._run_parse(document, job_id)
            elif task_type == "information_extract":
                await self._run_extract(document, job_id)
        except DocumentProcessingRepositoryError:
            return

    async def get_result(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> DocumentProcessingResult:
        document = await self._get_authorized(document_id, actor, organization_header)
        if document.status not in {"processing", "ready", "failed"}:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DOCUMENT_NOT_PROCESSED",
                message="The document has not been processed.",
            )
        data = document.extracted_data or {}
        artifact_id = data.get("parsed_artifact_document_id")
        return DocumentProcessingResult(
            document_id=document.id,
            status=document.status,  # type: ignore[arg-type]
            schema_version=data.get("schema_version"),
            extraction=data.get("extraction"),
            confirmation_required=data.get("confirmation_required", []),
            validation_warnings=data.get("validation_warnings", []),
            listing_candidate=data.get("listing_candidate"),
            parsed_artifact_document_id=UUID(artifact_id) if artifact_id else None,
            failure_code=document.failure_code,
        )

    async def _run_parse(self, document: ProcessingDocumentRecord, job_id: UUID) -> None:
        extract_job: ProcessingJobRecord | None = None
        try:
            await self._repository.mark_job_processing(job_id)
            source = await self._read_source(document)
            if document.mime_type == "application/pdf" and b"/Encrypt" in source:
                raise DocumentEncryptedError
            document_input = DocumentInput(
                filename=document.original_filename or f"{document.id}.bin",
                mime_type=document.mime_type or "application/octet-stream",
                content=source,
            )
            extract_job = await self._ensure_job(
                document.id,
                "information_extract",
                _EXTRACT_MODEL,
                self._prompt_version,
            )
            await self._repository.mark_job_processing(extract_job.id)
            try:
                extraction_result = await self._load_extraction_checkpoint(document.id, extract_job)
            except Exception as exc:
                extraction_result = exc
            if extraction_result is None:
                parsed_result, extraction_result = await asyncio.gather(
                    self._parse_provider.parse_document(document_input),
                    self._extract_provider.request_information_extraction(document_input),
                    return_exceptions=True,
                )
                if not isinstance(extraction_result, BaseException):
                    try:
                        await self._save_extraction_checkpoint(
                            document.id,
                            extract_job.id,
                            extraction_result,
                        )
                    except Exception as exc:
                        extraction_result = exc
            else:
                (parsed_result,) = await asyncio.gather(
                    self._parse_provider.parse_document(document_input),
                    return_exceptions=True,
                )
            if isinstance(parsed_result, BaseException):
                if isinstance(extraction_result, BaseException):
                    await self._safe_fail(
                        document.id,
                        extract_job.id,
                        self._failure_code(extraction_result),
                    )
                raise parsed_result
            parsed = parsed_result
            artifact_id = uuid4()
            artifact_bytes = parsed.model_dump_json().encode()
            artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
            artifact_path = f"documents/{document.id}/parsed/{artifact_id}.json"
            await self._storage.put_object(
                _ARTIFACT_BUCKET, artifact_path, artifact_bytes, "application/json"
            )
            await self._repository.create_parse_artifact(
                artifact_id=artifact_id,
                source=document,
                storage_bucket=_ARTIFACT_BUCKET,
                storage_object_path=artifact_path,
                size_bytes=len(artifact_bytes),
                content_sha256=artifact_hash,
            )
            await self._repository.mark_job_succeeded(
                job_id,
                {
                    "progress": 100,
                    "result_resource_type": "document",
                    "result_resource_id": str(artifact_id),
                    "provider_request_id": parsed.provider_request_id,
                    "page_count": len(parsed.pages),
                },
            )
            if extract_job.status in {"queued", "processing"}:
                await self._run_extract(
                    document,
                    extract_job.id,
                    parsed,
                    source,
                    artifact_id,
                    extraction_result,
                )
        except DocumentEncryptedError:
            await self._safe_fail(document.id, job_id, "DOCUMENT_ENCRYPTED")
        except Exception as exc:  # provider/storage failures are normalized below
            await self._safe_fail(document.id, job_id, self._failure_code(exc))

    async def _run_extract(
        self,
        document: ProcessingDocumentRecord,
        job_id: UUID,
        parsed: DocumentParseResult | None = None,
        source: bytes | None = None,
        artifact_id: UUID | None = None,
        extraction_result: InformationExtractionResult | BaseException | None = None,
    ) -> None:
        try:
            await self._repository.mark_job_processing(job_id)
            extract_job = await self._ensure_job(
                document.id,
                "information_extract",
                _EXTRACT_MODEL,
                self._prompt_version,
            )
            if extract_job.id != job_id:
                raise AIProviderInvalidResponseError
            parse_job = await self._ensure_job(document.id, "document_parse", _PARSE_MODEL, None)
            if parse_job.status != "succeeded":
                raise AIProviderInvalidResponseError
            if artifact_id is None:
                raw_artifact_id = parse_job.result_metadata.get("result_resource_id")
                if not raw_artifact_id:
                    raise AIProviderInvalidResponseError
                artifact_id = UUID(raw_artifact_id)
            if parsed is None:
                artifact = await self._repository.get_document(artifact_id)
                if artifact is None or artifact.purpose != "parsed_artifact":
                    raise AIProviderInvalidResponseError
                artifact_bytes = await self._read_source(artifact)
                parsed = DocumentParseResult.model_validate_json(artifact_bytes)
            if extraction_result is None:
                extraction_result = await self._load_extraction_checkpoint(document.id, extract_job)
            if extraction_result is None:
                if source is None:
                    source = await self._read_source(document)
                extraction_result = await self._extract_provider.request_information_extraction(
                    DocumentInput(
                        filename=document.original_filename or f"{document.id}.bin",
                        mime_type=document.mime_type or "application/octet-stream",
                        content=source,
                    )
                )
                await self._save_extraction_checkpoint(
                    document.id,
                    job_id,
                    extraction_result,
                )
            elif isinstance(extraction_result, BaseException):
                raise extraction_result
            extraction = self._extract_provider.map_information_extraction(
                extraction_result,
                parsed,
            )
            confirmation_required, warnings = self._validate_extraction(extraction, parsed)
            mapping = await self._map_listing_with_solar(extraction, parsed)
            candidate = self._build_listing_candidate(document, extraction, parsed, mapping)
            extracted_data = {
                "schema_version": "ai-document-processing-v1",
                "extraction": extraction.model_dump(mode="json"),
                "confirmation_required": confirmation_required,
                "validation_warnings": warnings,
                "listing_candidate": candidate,
                "parsed_artifact_document_id": str(artifact_id),
            }
            await self._repository.save_extraction(
                document_id=document.id,
                job_id=job_id,
                extracted_data=extracted_data,
                result_metadata={
                    "progress": 100,
                    "result_resource_type": "document",
                    "result_resource_id": str(document.id),
                    "provider_request_id": extraction.provider_request_id,
                    "confirmation_required_count": len(confirmation_required),
                },
            )
        except Exception as exc:  # provider/storage/schema failures are normalized below
            await self._safe_fail(document.id, job_id, self._failure_code(exc))

    async def _save_extraction_checkpoint(
        self,
        document_id: UUID,
        job_id: UUID,
        extraction_result: InformationExtractionResult,
    ) -> None:
        checkpoint_id = uuid4()
        checkpoint_bytes = extraction_result.model_dump_json().encode()
        if len(checkpoint_bytes) > self._max_document_size_bytes:
            raise AIProviderInvalidResponseError
        checkpoint_hash = hashlib.sha256(checkpoint_bytes).hexdigest()
        checkpoint_path = f"documents/{document_id}/extractions/{checkpoint_id}.json"
        await self._storage.put_object(
            _ARTIFACT_BUCKET,
            checkpoint_path,
            checkpoint_bytes,
            "application/json",
        )
        await self._repository.update_job_result_metadata(
            job_id,
            {
                "checkpoint_schema_version": _EXTRACT_CHECKPOINT_SCHEMA,
                "checkpoint_storage_bucket": _ARTIFACT_BUCKET,
                "checkpoint_storage_object_path": checkpoint_path,
                "checkpoint_content_sha256": checkpoint_hash,
                "checkpoint_size_bytes": len(checkpoint_bytes),
                "provider_request_id": extraction_result.provider_request_id,
            },
        )

    async def _load_extraction_checkpoint(
        self,
        document_id: UUID,
        job: ProcessingJobRecord,
    ) -> InformationExtractionResult | None:
        metadata = job.result_metadata
        checkpoint_path = metadata.get("checkpoint_storage_object_path")
        if checkpoint_path is None:
            return None
        checkpoint_bucket = metadata.get("checkpoint_storage_bucket")
        checkpoint_hash = metadata.get("checkpoint_content_sha256")
        checkpoint_schema = metadata.get("checkpoint_schema_version")
        expected_prefix = f"documents/{document_id}/extractions/"
        if (
            checkpoint_bucket != _ARTIFACT_BUCKET
            or not isinstance(checkpoint_path, str)
            or not checkpoint_path.startswith(expected_prefix)
            or not isinstance(checkpoint_hash, str)
            or checkpoint_schema != _EXTRACT_CHECKPOINT_SCHEMA
        ):
            raise AIProviderInvalidResponseError
        checkpoint_bytes = await self._read_object(checkpoint_bucket, checkpoint_path)
        if hashlib.sha256(checkpoint_bytes).hexdigest() != checkpoint_hash:
            raise AIProviderInvalidResponseError
        return InformationExtractionResult.model_validate_json(checkpoint_bytes)

    async def _read_source(self, document: ProcessingDocumentRecord) -> bytes:
        return await self._read_object(
            document.storage_bucket,
            document.storage_object_path,
        )

    async def _read_object(self, storage_bucket: str, storage_object_path: str) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in self._storage.iter_object(storage_bucket, storage_object_path):
            size += len(chunk)
            if size > self._max_document_size_bytes:
                raise DocumentTooLargeError
            chunks.append(chunk)
        if not chunks:
            raise StorageObjectNotFoundError
        return b"".join(chunks)

    async def _ensure_job(
        self, document_id: UUID, task_type: str, model_name: str, prompt_version: str | None
    ) -> ProcessingJobRecord:
        identity = AIJobIdentity(
            task_type=task_type,
            document_id=document_id,
            model_name=model_name,
            prompt_version=prompt_version,
        )
        try:
            return await self._repository.ensure_job(
                document_id=document_id,
                job_type=task_type,
                idempotency_base=identity.idempotency_key(),
                provider=self._provider_name,
                model_name=model_name,
                prompt_version=prompt_version,
            )
        except DocumentProcessingRepositoryError as exc:
            self._database_unavailable(exc)

    async def _get_authorized(
        self,
        document_id: UUID,
        actor: AuthenticatedUser,
        organization_header: str | None,
    ) -> ProcessingDocumentRecord:
        try:
            document = await self._repository.get_document(document_id)
            if document is None:
                raise AppError(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="DOCUMENT_NOT_FOUND",
                    message="Document not found.",
                )
            organization_id = document.seller_organization_id
            if organization_id is None:
                self._access_denied()
            if organization_header is None:
                self._access_denied("X-Organization-Id is required for document processing.")
            try:
                header_id = UUID(organization_header)
            except (ValueError, AttributeError):
                self._access_denied("X-Organization-Id must be a valid UUID.")
            if header_id != organization_id:
                self._access_denied()
            membership = await self._repository.get_membership(actor.id, organization_id)
            if membership is None or membership.organization_type != "seller":
                self._access_denied()
            return document
        except DocumentProcessingRepositoryError as exc:
            self._database_unavailable(exc)

    @staticmethod
    def _validate_processable(document: ProcessingDocumentRecord) -> None:
        if document.purpose != "source_contract" or document.listing_id is None:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DOCUMENT_PROCESSING_UNSUPPORTED",
                message="Only listing source contract documents can be processed.",
            )
        if document.status == "pending_upload":
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DOCUMENT_NOT_UPLOADED",
                message="Complete upload verification before processing the document.",
            )
        if document.content_sha256 is None or document.mime_type is None:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DOCUMENT_NOT_VERIFIED",
                message="The document has not passed upload verification.",
            )
        if document.mime_type not in _PROCESSABLE_MIME_TYPES:
            raise AppError(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                code="UNSUPPORTED_FILE_TYPE",
                message="Only verified PDF, DOCX, JPG, JPEG, and PNG files can be processed.",
            )

    def _validate_extraction(
        self, extraction: ContractExtraction, parsed: DocumentParseResult
    ) -> tuple[list[str], list[str]]:
        page_numbers = {page.page_number for page in parsed.pages}
        confirmations: list[str] = []
        warnings: list[str] = []
        for section_name in _SECTIONS:
            section: ExtractedSection = getattr(extraction, section_name)
            if section.missing:
                confirmations.append(section_name)
            for field_name, extracted in section.fields.items():
                path = f"{section_name}.{field_name}"
                if extracted.missing:
                    confirmations.append(path)
                    continue
                if extracted.confidence is None or (
                    extracted.confidence < self._low_confidence_threshold
                ):
                    confirmations.append(path)
                    warnings.append(f"low_confidence:{path}")
                if extracted.source_page is not None and extracted.source_page not in page_numbers:
                    raise AIProviderInvalidResponseError
                self._validate_scalar(field_name, extracted.value)
        start = self._value(extraction.service_period, "start_date", "service_start_date")
        end = self._value(extraction.service_period, "end_date", "service_end_date")
        if start is not None and end is not None:
            try:
                if date.fromisoformat(str(start)) > date.fromisoformat(str(end)):
                    raise AIProviderInvalidResponseError
            except ValueError as exc:
                raise AIProviderInvalidResponseError from exc
        return list(dict.fromkeys(confirmations)), warnings

    @staticmethod
    def _validate_scalar(field_name: str, value: Any) -> None:
        if value is None:
            return
        lowered = field_name.lower()
        if "date" in lowered:
            try:
                date.fromisoformat(str(value))
            except ValueError as exc:
                raise AIProviderInvalidResponseError from exc
        if isinstance(value, (int, float)) and any(
            token in lowered
            for token in ("amount", "price", "quantity", "people", "days", "nights")
        ):
            if value < 0:
                raise AIProviderInvalidResponseError
        if isinstance(value, (int, float)) and any(
            token in lowered for token in ("rate", "percent", "percentage")
        ):
            if value < 0 or value > 100:
                raise AIProviderInvalidResponseError

    def _build_listing_candidate(
        self,
        document: ProcessingDocumentRecord,
        extraction: ContractExtraction,
        parsed: DocumentParseResult,
        mapping: ListingMapping | None = None,
    ) -> dict[str, Any]:
        clauses = self._clause_candidates(parsed)
        body = parsed.markdown or "\n\n".join(clause["body"] for clause in clauses)
        terms = {
            "service_start_date": self._value(
                extraction.service_period, "start_date", "service_start_date"
            ),
            "service_end_date": self._value(
                extraction.service_period, "end_date", "service_end_date"
            ),
            "base_price_amount_minor": self._value(
                extraction.price, "amount_minor", "unit_price", "base_price"
            ),
            "currency": self._value(extraction.price, "currency"),
            "price_unit": self._value(extraction.price, "price_unit", "unit"),
            "cancellation_policy": self._section_text(extraction.cancellation),
            "refund_policy": self._section_text(extraction.refund),
            "safety_policy": self._section_text(extraction.safety),
            "compensation_policy": self._section_text(extraction.compensation),
            "liability_policy": self._section_text(extraction.liability),
            "termination_policy": self._section_text(extraction.termination),
        }
        if mapping is not None:
            terms.update(
                {
                    "price_unit": mapping.price_unit or terms["price_unit"],
                    "cancellation_policy": mapping.cancellation_policy
                    or terms["cancellation_policy"],
                    "refund_policy": mapping.refund_policy or terms["refund_policy"],
                    "quantity": mapping.quantity,
                    "settlement_terms": mapping.settlement_terms,
                }
            )
        return {
            "listing_id": str(document.listing_id),
            "title": mapping.title if mapping and mapping.title else document.listing_title,
            "category": document.listing_category,
            "language": document.listing_language,
            "terms": terms,
            "version": {
                "title": document.listing_title,
                "body": body,
                "source_document_id": str(document.id),
                "structured_data": extraction.model_dump(mode="json"),
            },
            "clauses": clauses,
            "confirmation_status": "seller_confirmation_required",
        }

    async def _map_listing_with_solar(
        self, extraction: ContractExtraction, parsed: DocumentParseResult
    ) -> ListingMapping | None:
        if self._provider_name != "upstage" or not hasattr(
            self._extract_provider, "generate_structured"
        ):
            return None
        try:
            return await self._extract_provider.generate_structured(  # type: ignore[attr-defined]
                LanguageModelRequest(
                    task_type="listing_mapping",
                    system_prompt=(
                        "You normalize an accommodation contract into seller listing fields. "
                        "Use only supplied extracted values and source text; never invent values. "
                        "Keep prices and dates unchanged. Separate cancellation from refund only "
                        "when the source clearly distinguishes them. Return null when absent."
                    ),
                    input_data={
                        "extracted": extraction.model_dump(mode="json"),
                        "source_text": parsed.markdown or "",
                    },
                    prompt_version="listing-mapping-v1",
                    reasoning_effort="low",
                ),
                ListingMapping,
            )
        except AIProviderError:
            return None

    @staticmethod
    def _clause_candidates(parsed: DocumentParseResult) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for page in parsed.pages:
            for block in page.blocks:
                content = block.content.strip()
                if not content:
                    continue
                lines = content.splitlines()
                first_line = lines[0].strip()
                is_clause = bool(_CLAUSE_TITLE.match(first_line))
                title = first_line if is_clause else f"원문 블록 {len(candidates) + 1}"
                body = "\n".join(lines[1:]).strip() if is_clause else content
                candidates.append(
                    {
                        "clause_order": len(candidates) + 1,
                        "clause_key": None,
                        "title": title,
                        "body": body or content,
                        "source_page": page.page_number,
                        "source_bbox": block.bbox.model_dump() if block.bbox else None,
                        "block_type": block.block_type,
                    }
                )
        return candidates

    @staticmethod
    def _value(section: ExtractedSection, *names: str) -> Any:
        for name in names:
            item = section.fields.get(name)
            if item is not None and not item.missing:
                return item.value
        return None

    @staticmethod
    def _section_text(section: ExtractedSection) -> str | None:
        for name in ("policy", "raw_text", "text", "terms"):
            item = section.fields.get(name)
            if item is not None and not item.missing and item.value is not None:
                return str(item.value)
        return None

    async def _safe_fail(self, document_id: UUID, job_id: UUID, failure_code: str) -> None:
        try:
            await self._repository.mark_failed(document_id, job_id, failure_code)
        except DocumentProcessingRepositoryError:
            return

    @staticmethod
    def _failure_code(exc: Exception) -> str:
        if isinstance(exc, AIProviderTimeoutError):
            return "AI_PROVIDER_TIMEOUT"
        if isinstance(exc, AIProviderRateLimitError):
            return "AI_PROVIDER_RATE_LIMITED"
        if isinstance(exc, AIProviderTemporaryError):
            return "AI_PROVIDER_TEMPORARY_FAILURE"
        if isinstance(exc, AIProviderPermanentError):
            return "AI_PROVIDER_REJECTED_DOCUMENT"
        if isinstance(exc, (AIProviderInvalidResponseError, ValidationError, ValueError)):
            return "AI_SCHEMA_INVALID"
        if isinstance(exc, DocumentTooLargeError):
            return "DOCUMENT_TOO_LARGE"
        if isinstance(exc, StorageObjectNotFoundError):
            return "STORAGE_OBJECT_NOT_FOUND"
        if isinstance(exc, StorageProviderError):
            return "STORAGE_PROVIDER_UNAVAILABLE"
        return "AI_PROCESSING_FAILED"

    @staticmethod
    def _access_denied(message: str = "You cannot process this document.") -> NoReturn:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="DOCUMENT_PROCESSING_ACCESS_DENIED",
            message=message,
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> NoReturn:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="The database is temporarily unavailable.",
        ) from exc


class DocumentEncryptedError(Exception):
    pass


class DocumentTooLargeError(Exception):
    pass
