import hashlib
import json
import logging
from collections.abc import Callable
from datetime import date
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi import status
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ai.schemas import DocumentParseResult
from app.core.errors import AppError
from app.domain.contracts.signature_fields import (
    SignatureFieldPositionError,
    select_signature_field,
    signature_field_candidates,
)
from app.domain.pricing.service import PriceCalculator
from app.integrations.auth import AuthenticatedUser
from app.integrations.modusign import (
    ModusignClient,
    ModusignParticipant,
    ModusignParticipantField,
    ModusignRequestError,
    ModusignUnavailableError,
)
from app.integrations.storage import (
    StorageObjectNotFoundError,
    StorageProvider,
    StorageProviderError,
)
from app.repositories.contracts import (
    ContractCreatedRecord,
    ContractRecord,
    ContractRepository,
    ContractRepositoryUnavailableError,
    ContractRequestSourceRecord,
    ContractStateConflictError,
    ContractVersionApprovalAccessError,
    ContractVersionApprovalContextRecord,
    ContractVersionApprovalRecord,
    ContractVersionClauseRecord,
    ContractVersionConflictError,
    ContractVersionNotFoundError,
    ContractVersionRecord,
    IdempotencyConflictError,
    NewContractData,
)
from app.repositories.pricing import ListingPriceTermsRecord
from app.schemas.contracts import (
    BuyerContractListItem,
    ContractBucket,
    ContractCancelResponse,
    ContractClauseResponse,
    ContractDetail,
    ContractPartySummary,
    ContractRequestCreate,
    ContractRequestCreated,
    ContractSignatureRequestCreate,
    ContractSummary,
    ContractTermsResponse,
    ContractVersionApprovalsResponse,
    ContractVersionApproveResponse,
    ContractVersionCompareResponse,
    ContractVersionListItem,
    ContractVersionPartyApproval,
    ContractVersionResponse,
    ContractVersionRiskSummary,
    InitialRequestKind,
    ListingRequestCount,
    SellerContractListItem,
    SellerDashboard,
    SellerDashboardStats,
    SignatureRequestCreated,
    VersionClauseChange,
    VersionClauseChangeSummary,
    VersionClauseSnapshot,
    VersionPeriodChange,
    VersionPeriodSnapshot,
    VersionPriceChange,
    VersionPriceSnapshot,
    VersionRiskChange,
)
from app.schemas.pricing import PriceEstimateRequest

_CANCELLABLE_STATUSES = {"draft", "seller_review", "revision_requested"}
_STATUS_LABELS = {
    "draft": "보낸 요청",
    "seller_review": "셀러 검토 중",
    "revision_requested": "협상 중",
    "signing": "서명 대기",
    "signed": "체결 완료",
    "cancelled": "종료",
}
_REQUEST_KIND_LABELS = {"as_is": "조건 그대로", "revision": "수정 요청"}
logger = logging.getLogger(__name__)


class ContractService:
    def __init__(
        self,
        repository: ContractRepository,
        price_calculator: PriceCalculator,
        storage: StorageProvider | None = None,
        *,
        today: Callable[[], date] | None = None,
    ) -> None:
        self._repository = repository
        self._price_calculator = price_calculator
        self._storage = storage
        self._today = today or date.today

    async def create_request(
        self,
        listing_id: UUID,
        actor: AuthenticatedUser,
        payload: ContractRequestCreate,
        idempotency_key: str,
    ) -> ContractRequestCreated:
        request_hash = self._request_hash(
            {"listing_id": str(listing_id), **payload.model_dump(mode="json")}
        )

        async def build(source: ContractRequestSourceRecord | None) -> NewContractData:
            if source is None:
                self._raise(
                    status.HTTP_404_NOT_FOUND,
                    "LISTING_NOT_FOUND",
                    "Listing was not found.",
                )
            if source.listing_status == "expired":
                self._raise(
                    status.HTTP_410_GONE,
                    "LISTING_EXPIRED",
                    "The listing has expired.",
                )
            if source.listing_status != "published":
                self._raise(
                    status.HTTP_409_CONFLICT,
                    "INVALID_STATE_TRANSITION",
                    "Only published listings accept contract requests.",
                )
            if source.current_version_id is None:
                self._raise(
                    status.HTTP_409_CONFLICT,
                    "LISTING_VERSION_REQUIRED",
                    "The listing does not have a current contract version.",
                )
            if source.buyer_name is None:
                self._raise(
                    status.HTTP_404_NOT_FOUND,
                    "PROFILE_NOT_FOUND",
                    "Buyer profile was not found.",
                )
            try:
                is_listing_seller = await self._repository.is_seller_member(
                    actor.id, source.seller_organization_id
                )
            except ContractRepositoryUnavailableError as exc:
                self._database_unavailable(exc)
            if is_listing_seller:
                self._raise(
                    status.HTTP_403_FORBIDDEN,
                    "CONTRACT_PARTY_CONFLICT",
                    "A seller organization member cannot create a contract as the buyer.",
                )
            estimate = await self._price_calculator.calculate(
                ListingPriceTermsRecord(
                    listing_id=source.listing_id,
                    status=source.listing_status,
                    expires_at=source.listing_expires_at,
                    service_start_date=source.service_start_date,
                    service_end_date=source.service_end_date,
                    quantity_unit=source.quantity_unit,
                    base_price_amount_minor=source.base_price_amount_minor,
                    currency=source.currency,
                    price_unit=source.price_unit,
                ),
                PriceEstimateRequest(
                    people=payload.people,
                    quantity=payload.quantity,
                    quantity_unit=payload.quantity_unit,
                    nights=payload.nights,
                    start_date=payload.start_date,
                    end_date=payload.end_date,
                    currency=payload.currency,
                ),
            )
            target_status = (
                "seller_review"
                if payload.initial_request_kind == InitialRequestKind.AS_IS
                else "revision_requested"
            )
            snapshot = {
                "people": payload.people,
                "quantity": payload.quantity,
                "quantity_unit": payload.quantity_unit,
                "nights": payload.nights,
                "start_date": payload.start_date.isoformat(),
                "end_date": payload.end_date.isoformat(),
                "base_unit_price_amount_minor": estimate.base_unit_price_amount_minor,
                "base_currency": estimate.base_currency,
                "display_currency": estimate.display_currency,
                "exchange_rate": str(estimate.exchange_rate),
                "exchange_rate_as_of": estimate.exchange_rate_as_of.isoformat(),
                "formula": estimate.formula,
                "calculation_method": "deterministic",
            }
            return NewContractData(
                status=target_status,
                initial_request_kind=payload.initial_request_kind.value,
                request_message=payload.request_message,
                buyer_group_name=payload.group_name,
                signing_capacity=payload.signing_capacity.value,
                requested_people=payload.people,
                service_start_date=payload.start_date,
                service_end_date=payload.end_date,
                amount_minor=estimate.total_estimated_amount_minor,
                currency=estimate.display_currency,
                calculation_snapshot=snapshot,
            )

        try:
            created = await self._repository.create_contract_request(
                listing_id=listing_id,
                buyer_user_id=actor.id,
                buyer_email=actor.email,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                build=build,
            )
        except IdempotencyConflictError as exc:
            self._idempotency_conflict(exc)
        except ContractStateConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="VERSION_CONFLICT",
                message="The listing version changed while creating the contract.",
            ) from exc
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return self._created_response(created)

    async def get_contract(
        self,
        contract_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> ContractDetail:
        record = await self._get_record(contract_id)
        actor_role = await self._authorize_contract(record, actor, header_organization_id)
        if record.current_version_id is None:
            self._raise(
                status.HTTP_409_CONFLICT,
                "CONTRACT_VERSION_REQUIRED",
                "The contract does not have a current version.",
            )
        try:
            clauses = await self._repository.list_contract_clauses(record.current_version_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if record.version_no is None or record.version_title is None or record.version_body is None:
            self._raise(
                status.HTTP_409_CONFLICT,
                "CONTRACT_VERSION_REQUIRED",
                "The contract does not have a current version.",
            )
        unread = False
        if actor_role == "buyer":
            unread = contract_id in await self._unread_contract_ids(actor.id, [contract_id])
        return ContractDetail(
            **self._summary(record, has_unread_response=unread).model_dump(),
            parties=[
                ContractPartySummary(
                    role="buyer",
                    name=record.buyer_name,
                    country_code=record.buyer_country_code,
                    group_name=record.buyer_group_name_snapshot,
                    signing_capacity=record.buyer_signing_capacity,
                ),
                ContractPartySummary(role="seller", name=record.seller_name),
            ],
            terms=self._terms_response(record),
            current_version=ContractVersionResponse(
                id=record.current_version_id,
                version_no=record.version_no,
                title=record.version_title,
                body=record.version_body,
                clauses=[
                    ContractClauseResponse(
                        id=clause.id,
                        clause_order=clause.clause_order,
                        clause_key=clause.clause_key,
                        title=clause.title,
                        body=clause.body,
                    )
                    for clause in clauses
                ],
            ),
        )

    async def list_my_contracts(
        self, actor: AuthenticatedUser, bucket: ContractBucket | None
    ) -> list[BuyerContractListItem]:
        try:
            records = await self._repository.list_buyer_contracts(actor.id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        unread_ids = await self._unread_contract_ids(actor.id, [record.id for record in records])
        items = [
            BuyerContractListItem(
                **self._summary(record, has_unread_response=record.id in unread_ids).model_dump(),
                seller_name=record.seller_name,
            )
            for record in records
        ]
        return [item for item in items if bucket is None or item.bucket == bucket]

    async def list_contract_versions(
        self,
        contract_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> list[ContractVersionListItem]:
        record = await self._get_record(contract_id)
        await self._authorize_contract(record, actor, header_organization_id)
        versions = await self._versions(contract_id)
        return [self._version_item(version) for version in versions]

    async def compare_contract_versions(
        self,
        contract_id: UUID,
        from_version_no: int,
        to_version_no: int,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> ContractVersionCompareResponse:
        if from_version_no == to_version_no:
            self._raise(
                status.HTTP_400_BAD_REQUEST,
                "VERSION_COMPARE_INVALID",
                "from and to must identify different contract versions.",
            )
        record = await self._get_record(contract_id)
        await self._authorize_contract(record, actor, header_organization_id)
        versions = await self._versions(contract_id)
        by_number = {version.version_no: version for version in versions}
        before = by_number.get(from_version_no)
        after = by_number.get(to_version_no)
        if before is None or after is None:
            self._raise(
                status.HTTP_404_NOT_FOUND,
                "CONTRACT_VERSION_NOT_FOUND",
                "One or more requested contract versions were not found.",
            )
        changes = self._compare_clauses(before.clauses, after.clauses)
        return ContractVersionCompareResponse(
            contract_id=contract_id,
            from_version=self._version_item(before),
            to_version=self._version_item(after),
            clause_summary=VersionClauseChangeSummary(
                added=sum(change.change_type == "added" for change in changes),
                deleted=sum(change.change_type == "deleted" for change in changes),
                modified=sum(change.change_type == "modified" for change in changes),
            ),
            clause_changes=changes,
            price_change=self._price_change(before, after),
            period_change=self._period_change(before, after),
            risk_change=self._risk_change(before, after),
        )

    async def get_contract_version_approvals(
        self,
        contract_id: UUID,
        contract_version_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> ContractVersionApprovalsResponse:
        context = await self._approval_context(contract_id, contract_version_id)
        await self._authorize_approval_context(context, actor, header_organization_id)
        try:
            approvals = await self._repository.list_contract_version_approvals(contract_version_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return self._approval_response(context, approvals)

    async def approve_contract_version(
        self,
        contract_id: UUID,
        contract_version_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> ContractVersionApproveResponse:
        context = await self._approval_context(contract_id, contract_version_id)
        party_role = await self._authorize_approval_context(context, actor, header_organization_id)
        if context.current_version_id != contract_version_id:
            self._raise(
                status.HTTP_409_CONFLICT,
                "VERSION_CONFLICT",
                "Only the current contract version can be approved.",
            )
        if context.contract_status not in {"seller_review", "signing"}:
            self._raise(
                status.HTTP_409_CONFLICT,
                "INVALID_STATE_TRANSITION",
                "The contract cannot be approved in its current state.",
            )
        try:
            mutation = await self._repository.approve_contract_version(
                contract_id=contract_id,
                contract_version_id=contract_version_id,
                actor_user_id=actor.id,
                party_role=party_role,
            )
        except ContractVersionConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="VERSION_CONFLICT",
                message="The current contract version changed before approval.",
            ) from exc
        except ContractStateConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="INVALID_STATE_TRANSITION",
                message="The contract cannot be approved in its current state.",
            ) from exc
        except ContractVersionApprovalAccessError as exc:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CONTRACT_ACCESS_DENIED",
                message="You do not have access to approve this contract version.",
            ) from exc
        except ContractVersionNotFoundError as exc:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CONTRACT_VERSION_NOT_FOUND",
                message="Contract version was not found.",
            ) from exc
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        response = self._approval_response(mutation.context, mutation.approvals)
        return ContractVersionApproveResponse(
            **response.model_dump(),
            approved_role=mutation.approved_role,
            already_approved=mutation.already_approved,
            contract_status=mutation.contract_status,
        )

    async def create_signature_request(
        self,
        contract_id: UUID,
        contract_version_id: UUID,
        payload: ContractSignatureRequestCreate,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
        idempotency_key: str,
        client: ModusignClient,
        template_id: str | None,
        source_pdf: bytes | None = None,
        source_page_count: int | None = None,
        source_field_candidates: list[dict[str, Any]] | None = None,
        source_page_texts: list[str] | None = None,
        source_fields: list[ModusignParticipantField] | None = None,
    ) -> SignatureRequestCreated:
        if source_pdf is None and not template_id:
            self._raise(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "MODUSIGN_TEMPLATE_NOT_CONFIGURED",
                "The signature template is not configured on the server.",
            )
        context = await self._approval_context(contract_id, contract_version_id)
        await self._authorize_approval_context(context, actor, header_organization_id)
        if context.current_version_id != contract_version_id:
            self._raise(
                status.HTTP_409_CONFLICT,
                "VERSION_CONFLICT",
                "Only the current contract version can be sent for signature.",
            )
        resolved_source_fields = source_fields
        if source_pdf is not None and resolved_source_fields is None:
            try:
                resolved_source_fields = self._source_pdf_fields(
                    source_field_candidates,
                    source_page_count,
                    source_page_texts,
                )
            except SignatureFieldPositionError:
                self._raise(
                    status.HTTP_409_CONFLICT,
                    "SIGNATURE_FIELD_POSITION_REQUIRED",
                    (
                        "The final PDF has no trustworthy buyer signature position. "
                        "Add a unique buyer signature label or save a manual coordinate."
                    ),
                )
        try:
            signature_request = await self._repository.begin_signature_request(
                contract_id=contract_id,
                contract_version_id=contract_version_id,
                requested_by=actor.id,
                idempotency_key=idempotency_key,
                provider_template_id=template_id or "source-pdf",
                buyer_name=payload.buyer.name,
                buyer_email=payload.buyer.email,
                seller_name=payload.seller.name,
                seller_email=payload.seller.email,
            )
        except IdempotencyConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_KEY_REUSED",
                message="This idempotency key was already used for a different contract version.",
            ) from exc
        except ContractVersionConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="VERSION_CONFLICT",
                message=(
                    "The current contract version changed before the signature request was created."
                ),
            ) from exc
        except ContractStateConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="SIGNATURE_NOT_READY",
                message="Both parties must approve the current contract version before signing.",
            ) from exc
        except ContractVersionNotFoundError as exc:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CONTRACT_VERSION_NOT_FOUND",
                message="Contract version was not found.",
            ) from exc
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)

        if signature_request.reused:
            return self._signature_response(signature_request, reused=True)
        try:
            if source_pdf is not None:
                provider_document = await client.create_signature_request_from_pdf(
                    title=payload.title,
                    pdf_bytes=source_pdf,
                    buyer=ModusignParticipant(
                        role="바이어", name=payload.buyer.name, email=payload.buyer.email
                    ),
                    buyer_fields=resolved_source_fields or [],
                )
            else:
                provider_document = await client.create_signature_request(
                    template_id=template_id or "",
                    title=payload.title,
                    participants=[
                        ModusignParticipant(
                            role="바이어", name=payload.buyer.name, email=payload.buyer.email
                        )
                    ],
                )
            provider_document_id = provider_document.get("id")
            if not isinstance(provider_document_id, str) or not provider_document_id:
                raise ModusignUnavailableError
            signature_request = await self._repository.mark_signature_request_dispatched(
                signature_request.id,
                provider_document_id,
                str(provider_document.get("status", "ON_PROCESSING")),
            )
        except (ModusignRequestError, ModusignUnavailableError) as exc:
            await self._mark_signature_failed(signature_request.id)
            if isinstance(exc, ModusignRequestError):
                logger.warning(
                    "Modusign signature request rejected: status=%s detail=%s",
                    exc.status_code,
                    exc.detail[:1000],
                )
                self._raise(
                    status.HTTP_502_BAD_GATEWAY,
                    "MODUSIGN_REQUEST_REJECTED",
                    "Modusign rejected the signature request. Check the template and participants.",
                )
            self._raise(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "MODUSIGN_UNAVAILABLE",
                "Could not reach Modusign. Please try again shortly.",
            )
        except (ContractStateConflictError, ContractRepositoryUnavailableError) as exc:
            self._database_unavailable(exc)
        return self._signature_response(signature_request)

    @staticmethod
    def _source_pdf_fields(
        candidates: list[dict[str, Any]] | None,
        page_count: int | None,
        page_texts: list[str] | None = None,
    ) -> list[ModusignParticipantField]:
        selected = select_signature_field(
            page_texts=page_texts or [],
            candidates=candidates,
            page_count=page_count or 1,
        )
        return [
            ModusignParticipantField(
                field_type="SIGNATURE",
                data_label="buyer_signature",
                position=selected["position"],
                size=selected["size"],
                required=True,
                signature_types=["SIGN"],
            )
        ]

    async def dispatch_signature_request_from_snapshots(
        self,
        contract_id: UUID,
        contract_version_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
        idempotency_key: str,
        client: ModusignClient,
        template_id: str | None,
        storage: StorageProvider,
        manual_fields: list[dict[str, Any]] | None = None,
    ) -> SignatureRequestCreated:
        try:
            contacts = await self._repository.get_signature_contacts(
                contract_id, contract_version_id
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if contacts is None:
            self._raise(
                status.HTTP_404_NOT_FOUND,
                "CONTRACT_VERSION_NOT_FOUND",
                "Contract version was not found.",
            )
        if not contacts.buyer_email or not contacts.seller_email:
            self._raise(
                status.HTTP_409_CONFLICT,
                "SIGNING_EMAIL_MISSING",
                "A buyer or seller signing email is missing from the contract snapshot.",
            )
        record = await self._get_record(contract_id)
        try:
            source = await self._repository.get_signature_source_document(
                contract_id, contract_version_id
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if source is None:
            self._raise(
                status.HTTP_409_CONFLICT,
                "FINAL_CONTRACT_PDF_MISSING",
                "The approved contract version does not have a final PDF for signing.",
            )
        try:
            source_pdf = b"".join(
                [
                    chunk
                    async for chunk in storage.iter_object(
                        source.storage_bucket, source.storage_object_path
                    )
                ]
            )
        except (StorageObjectNotFoundError, StorageProviderError):
            logger.exception("final contract PDF could not be read for signature dispatch")
            self._raise(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "FINAL_CONTRACT_PDF_UNAVAILABLE",
                "The final PDF could not be prepared for signing.",
            )
        logger.info(
            "dispatching signature source PDF sha256=%s size_bytes=%s",
            hashlib.sha256(source_pdf).hexdigest(),
            len(source_pdf),
        )
        stored_candidates = source.extracted_data.get("signature_field_candidates")
        manual_source_fields: list[ModusignParticipantField] | None = None
        if manual_fields:
            # The placement UI stores normalized coordinates. Keep every field
            # the seller placed and send it directly to Modusign; the old
            # signature-candidate selector only supported one OCR signature.
            manual_source_fields = []
            for field in manual_fields:
                field_type = str(field.get("field_type", "")).upper()
                # Preserve the actual Modusign field type. In particular,
                # SIGNING_DATE is filled automatically by Modusign, whereas a
                # TEXT field forces the buyer to enter an arbitrary date.
                if field_type not in {
                    "TEXT",
                    "SIGNATURE",
                    "CHECKBOX",
                    "SIGNING_DATE",
                    "DATE",
                    "IMAGE",
                    "DROPDOWN",
                    "NAME",
                    "COMPANY_NAME",
                    "ADDRESS",
                }:
                    continue
                position = field.get("position")
                if not isinstance(position, dict):
                    continue
                size = field.get("size")
                manual_source_fields.append(
                    ModusignParticipantField(
                        field_type=field_type,
                        data_label=str(field.get("data_label") or "buyer_field"),
                        position=position,
                        size=size if isinstance(size, dict) else None,
                        required=bool(field.get("required", True)),
                        signature_types=["SIGN"] if field_type == "SIGNATURE" else None,
                        # Modusign validates displayFormat for both DATE and
                        # SIGNING_DATE fields. Use one explicit Korean format
                        # for every page rather than a per-page convention.
                        display_format=(
                            "YYYY년 MM월 DD일" if field_type in {"DATE", "SIGNING_DATE"} else None
                        ),
                        text_style=(
                            {
                                "size": min(
                                    (
                                        4,
                                        5,
                                        6,
                                        7,
                                        8,
                                        9,
                                        10,
                                        11,
                                        12,
                                        13,
                                        14,
                                        15,
                                        16,
                                        17,
                                        18,
                                        24,
                                        30,
                                        36,
                                        48,
                                        60,
                                    ),
                                    key=lambda value: abs(value - int(field.get("font_size", 12))),
                                ),
                                "font": "NOTO_SANS",
                                "align": str(field.get("text_align", "LEFT")).upper(),
                            }
                            if field_type
                            in {
                                "TEXT",
                                "SIGNING_DATE",
                                "DATE",
                                "DROPDOWN",
                                "NAME",
                                "COMPANY_NAME",
                                "ADDRESS",
                            }
                            else None
                        ),
                        options=(
                            [
                                {"value": str(option["value"])}
                                for option in field.get("options", [])
                                if isinstance(option, dict) and option.get("value")
                            ]
                            if field_type == "DROPDOWN" and isinstance(field.get("options"), list)
                            else None
                        ),
                    )
                )
        candidates = manual_fields or [
            candidate
            for candidate in stored_candidates or []
            if isinstance(candidate, dict)
            and candidate.get("placement_strategy") in {"manual_coordinate", "ocr_marker_bbox"}
        ]
        if source.parsed_storage_bucket and source.parsed_storage_object_path:
            try:
                parsed_bytes = b"".join(
                    [
                        chunk
                        async for chunk in storage.iter_object(
                            source.parsed_storage_bucket, source.parsed_storage_object_path
                        )
                    ]
                )
                manual_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.get("placement_strategy") == "manual_coordinate"
                ]
                candidates = manual_candidates + self._signature_field_candidates(
                    DocumentParseResult.model_validate_json(parsed_bytes)
                )
            except (StorageProviderError, ValueError):
                pass
        source_page_texts: list[str] = []
        try:
            pdf_reader = PdfReader(BytesIO(source_pdf), strict=False)
            source_page_count = len(pdf_reader.pages)
            source_page_texts = [page.extract_text() or "" for page in pdf_reader.pages]
            logger.info(
                "signature PDF page geometry sha256=%s pages=%s geometry=%s",
                hashlib.sha256(source_pdf).hexdigest(),
                source_page_count,
                [
                    {
                        "page": index + 1,
                        "media_box": list(page.mediabox),
                        "crop_box": list(page.cropbox),
                        "rotation": page.rotation,
                        "width": float(page.cropbox.width),
                        "height": float(page.cropbox.height),
                    }
                    for index, page in enumerate(pdf_reader.pages)
                ],
            )
        except (KeyError, PdfReadError, TypeError, ValueError):
            source_page_count = 1
        return await self.create_signature_request(
            contract_id,
            contract_version_id,
            ContractSignatureRequestCreate(
                title=record.version_title or record.listing_title,
                buyer={"name": contacts.buyer_name, "email": contacts.buyer_email},
                seller={"name": contacts.seller_name, "email": contacts.seller_email},
            ),
            actor,
            header_organization_id,
            idempotency_key,
            client,
            template_id,
            source_pdf,
            source_page_count,
            candidates if isinstance(candidates, list) else [],
            source_page_texts,
            manual_source_fields,
        )

    async def get_signature_source_pdf(
        self,
        contract_id: UUID,
        contract_version_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
        storage: StorageProvider,
    ) -> tuple[bytes, dict[str, object]]:
        context = await self._approval_context(contract_id, contract_version_id)
        await self._authorize_approval_context(context, actor, header_organization_id)
        if context.current_version_id != contract_version_id:
            self._raise(
                status.HTTP_409_CONFLICT,
                "VERSION_CONFLICT",
                "Only the current version can be previewed.",
            )
        source = await self._repository.get_signature_source_document(
            contract_id, contract_version_id
        )
        if source is None:
            self._raise(
                status.HTTP_409_CONFLICT,
                "FINAL_CONTRACT_PDF_MISSING",
                "The approved contract version does not have a final PDF for signing.",
            )
        try:
            pdf_bytes = b"".join(
                [
                    chunk
                    async for chunk in storage.iter_object(
                        source.storage_bucket, source.storage_object_path
                    )
                ]
            )
            reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        except (
            StorageObjectNotFoundError,
            StorageProviderError,
            PdfReadError,
            ValueError,
            KeyError,
        ):
            self._raise(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "FINAL_CONTRACT_PDF_UNAVAILABLE",
                "The final PDF could not be prepared for preview.",
            )
        return pdf_bytes, {
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "size_bytes": len(pdf_bytes),
            "page_count": len(reader.pages),
        }

    @staticmethod
    def _signature_field_candidates(parsed: DocumentParseResult) -> list[dict[str, Any]]:
        return signature_field_candidates(parsed)

    async def _mark_signature_failed(self, signature_request_id: UUID) -> None:
        try:
            await self._repository.mark_signature_request_failed(signature_request_id)
        except ContractRepositoryUnavailableError:
            # Preserve the provider-facing error; the request remains safely idempotent in DB.
            return

    async def get_signature_request(
        self,
        signature_request_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SignatureRequestCreated:
        try:
            record = await self._repository.get_signature_request(signature_request_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if record is None:
            self._raise(
                status.HTTP_404_NOT_FOUND,
                "SIGNATURE_REQUEST_NOT_FOUND",
                "Signature request was not found.",
            )
        context = await self._approval_context(record.contract_id, record.contract_version_id)
        await self._authorize_approval_context(context, actor, header_organization_id)
        return self._signature_response(record)

    async def sync_signature_request(
        self,
        signature_request_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
        client: ModusignClient,
        storage: StorageProvider,
    ) -> SignatureRequestCreated:
        record = await self.get_signature_request(
            signature_request_id, actor, header_organization_id
        )
        return await self._sync_signature_record(record, client, storage)

    async def sync_signature_request_from_provider_document(
        self, provider_document_id: str, client: ModusignClient, storage: StorageProvider
    ) -> SignatureRequestCreated:
        try:
            record = await self._repository.get_signature_request_by_provider_document_id(
                provider_document_id
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if record is None:
            self._raise(
                status.HTTP_404_NOT_FOUND,
                "SIGNATURE_REQUEST_NOT_FOUND",
                "Unknown provider document.",
            )
        return await self._sync_signature_record(record, client, storage)

    async def _sync_signature_record(
        self, record: Any, client: ModusignClient, storage: StorageProvider
    ) -> SignatureRequestCreated:
        if not record.provider_document_id:
            return record
        if record.status == "completed":
            return record
        try:
            provider_document = await client.get_document(record.provider_document_id)
            provider_status = str(provider_document.get("status", "UNKNOWN"))
            updated = await self._repository.update_signature_request_status(
                record.id,
                provider_status=provider_status,
                current_signing_order=provider_document.get("currentSigningOrder"),
            )
            if provider_status != "COMPLETED":
                return self._signature_response(updated)
            signed_url = (provider_document.get("file") or {}).get("downloadUrl")
            audit_url = (provider_document.get("auditTrail") or {}).get("downloadUrl")
            if not isinstance(signed_url, str) or not isinstance(audit_url, str):
                self._raise(
                    status.HTTP_409_CONFLICT,
                    "MODUSIGN_FILE_NOT_AVAILABLE",
                    "Completed signature files are not available yet.",
                )
            signed_bytes, signed_type = await client.fetch_file(signed_url)
            audit_bytes, audit_type = await client.fetch_file(audit_url)
            if signed_type != "application/pdf" or audit_type != "application/pdf":
                self._raise(
                    status.HTTP_502_BAD_GATEWAY,
                    "MODUSIGN_INVALID_FILE",
                    "Modusign returned an unexpected completion file type.",
                )
            base_path = f"contracts/{updated.contract_id}/signatures/{updated.id}"
            await storage.put_object(
                "contract-documents", f"{base_path}/signed.pdf", signed_bytes, signed_type
            )
            await storage.put_object(
                "contract-documents", f"{base_path}/audit-trail.pdf", audit_bytes, audit_type
            )
            updated = await self._repository.complete_signature_request(
                record.id,
                signed_size_bytes=len(signed_bytes),
                signed_sha256=hashlib.sha256(signed_bytes).hexdigest(),
                audit_size_bytes=len(audit_bytes),
                audit_sha256=hashlib.sha256(audit_bytes).hexdigest(),
            )
        except ModusignUnavailableError:
            self._raise(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "MODUSIGN_UNAVAILABLE",
                "Could not reach Modusign. Please try again shortly.",
            )
        except ModusignRequestError:
            self._raise(
                status.HTTP_502_BAD_GATEWAY,
                "MODUSIGN_REQUEST_REJECTED",
                "Modusign rejected the status request.",
            )
        except StorageProviderError:
            self._raise(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_PROVIDER_UNAVAILABLE",
                "Could not store the completed signature files. Please try again shortly.",
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return self._signature_response(updated)

    @staticmethod
    def _signature_response(record: Any, *, reused: bool = False) -> SignatureRequestCreated:
        return SignatureRequestCreated(
            id=record.id,
            contract_id=record.contract_id,
            contract_version_id=record.contract_version_id,
            status=record.status,
            provider=record.provider,
            provider_document_id=record.provider_document_id,
            provider_status=record.provider_status,
            current_signing_order=record.current_signing_order,
            completed_at=record.completed_at,
            signed_document_id=record.signed_document_id,
            audit_trail_document_id=record.audit_trail_document_id,
            reused=reused,
        )

    async def list_received_contracts(
        self,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> list[SellerContractListItem]:
        organization_id = await self._authorize_seller_header(actor, header_organization_id)
        try:
            records = await self._repository.list_seller_contracts(organization_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return [self._seller_item(record) for record in records]

    async def get_seller_dashboard(
        self,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerDashboard:
        organization_id = await self._authorize_seller_header(actor, header_organization_id)
        try:
            records = await self._repository.list_seller_contracts(organization_id)
            listing_counts = await self._repository.list_seller_listing_request_counts(
                organization_id
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        status_counts = {
            contract_status: sum(record.status == contract_status for record in records)
            for contract_status in (
                "seller_review",
                "revision_requested",
                "signing",
                "signed",
                "cancelled",
            )
        }
        return SellerDashboard(
            stats=SellerDashboardStats(
                published_listings=sum(
                    listing.listing_status == "published" for listing in listing_counts
                ),
                received_requests=len(records),
                **status_counts,
            ),
            recent_requests=[self._seller_item(record) for record in records[:5]],
            listing_request_counts=[
                ListingRequestCount(
                    listing_id=listing.listing_id,
                    listing_title=listing.listing_title,
                    listing_status=listing.listing_status,
                    request_count=listing.request_count,
                )
                for listing in listing_counts
            ],
        )

    async def cancel_contract(
        self,
        contract_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
        idempotency_key: str,
    ) -> ContractCancelResponse:
        record = await self._get_record(contract_id)
        actor_role = await self._authorize_contract(record, actor, header_organization_id)
        if record.status not in _CANCELLABLE_STATUSES and record.status != "cancelled":
            self._raise(
                status.HTTP_409_CONFLICT,
                "INVALID_STATE_TRANSITION",
                "The contract cannot be cancelled from its current state.",
            )
        request_hash = self._request_hash({"contract_id": str(contract_id), "operation": "cancel"})
        try:
            cancelled_at, _ = await self._repository.cancel_contract(
                contract_id=contract_id,
                actor_user_id=actor.id,
                actor_role=actor_role,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        except IdempotencyConflictError as exc:
            self._idempotency_conflict(exc)
        except ContractStateConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="INVALID_STATE_TRANSITION",
                message="The contract cannot be cancelled from its current state.",
            ) from exc
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return ContractCancelResponse(
            contract_id=contract_id,
            status="cancelled",
            cancelled_at=cancelled_at,
        )

    async def _get_record(self, contract_id: UUID) -> ContractRecord:
        try:
            record = await self._repository.get_contract(contract_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if record is None:
            self._raise(
                status.HTTP_404_NOT_FOUND,
                "CONTRACT_NOT_FOUND",
                "Contract was not found.",
            )
        return record

    async def _authorize_contract(
        self,
        record: ContractRecord,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> str:
        if record.buyer_user_id == actor.id:
            return "buyer"
        organization_id = self._parse_organization_header(header_organization_id)
        if organization_id != record.seller_organization_id:
            self._access_denied()
        try:
            member = await self._repository.is_seller_member(actor.id, organization_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if not member:
            self._access_denied()
        return "seller"

    async def _authorize_seller_header(
        self, actor: AuthenticatedUser, header_organization_id: str | None
    ) -> UUID:
        organization_id = self._parse_organization_header(header_organization_id)
        try:
            member = await self._repository.is_seller_member(actor.id, organization_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if not member:
            self._access_denied()
        return organization_id

    @staticmethod
    def _parse_organization_header(header: str | None) -> UUID:
        if header is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required for seller organization APIs.",
            )
        try:
            return UUID(header)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="X-Organization-Id must be a UUID.",
            ) from exc

    def _summary(
        self, record: ContractRecord, *, has_unread_response: bool = False
    ) -> ContractSummary:
        bucket = self._bucket(record)
        return ContractSummary(
            id=record.id,
            listing_id=record.listing_id,
            listing_title=record.listing_title,
            status=record.status,
            bucket=bucket,
            status_label=(
                "종료" if bucket == ContractBucket.FINISHED else _STATUS_LABELS[record.status]
            ),
            has_unread_response=has_unread_response,
            initial_request_kind=record.initial_request_kind,
            request_message=record.request_message,
            requested_people=record.requested_people,
            buyer_group_name=record.buyer_group_name,
            signing_capacity=record.signing_capacity,
            amount_minor=record.amount_minor,
            currency=record.currency,
            service_start_date=record.service_start_date,
            service_end_date=record.service_end_date,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @classmethod
    def _seller_item(cls, record: ContractRecord) -> SellerContractListItem:
        return SellerContractListItem(
            contract_id=record.id,
            listing_id=record.listing_id,
            listing_title=record.listing_title,
            buyer_name=record.buyer_name,
            buyer_group_name=record.buyer_group_name,
            requested_people=record.requested_people,
            service_start_date=record.service_start_date,
            service_end_date=record.service_end_date,
            amount_minor=record.amount_minor,
            currency=record.currency,
            initial_request_kind=record.initial_request_kind,
            request_kind_label=_REQUEST_KIND_LABELS[record.initial_request_kind],
            status=record.status,
            status_label=_STATUS_LABELS[record.status],
            requested_at=record.created_at,
        )

    def _bucket(self, record: ContractRecord) -> ContractBucket:
        if record.status == "signed" and record.service_end_date < self._today():
            return ContractBucket.FINISHED
        return ContractBucket(record.status)

    async def _unread_contract_ids(
        self, buyer_user_id: UUID, contract_ids: list[UUID]
    ) -> set[UUID]:
        try:
            return await self._repository.list_unread_response_contract_ids(
                buyer_user_id, contract_ids
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)

    async def _versions(self, contract_id: UUID) -> list[ContractVersionRecord]:
        try:
            return await self._repository.list_contract_versions(contract_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)

    async def _approval_context(
        self, contract_id: UUID, contract_version_id: UUID
    ) -> ContractVersionApprovalContextRecord:
        try:
            context = await self._repository.get_contract_version_approval_context(
                contract_id, contract_version_id
            )
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if context is None:
            self._raise(
                status.HTTP_404_NOT_FOUND,
                "CONTRACT_VERSION_NOT_FOUND",
                "Contract version was not found.",
            )
        return context

    async def _authorize_approval_context(
        self,
        context: ContractVersionApprovalContextRecord,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> str:
        if context.buyer_user_id == actor.id:
            return "buyer"
        organization_id = self._parse_organization_header(header_organization_id)
        if organization_id != context.seller_organization_id:
            self._access_denied()
        try:
            member = await self._repository.is_seller_member(actor.id, organization_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if not member:
            self._access_denied()
        return "seller"

    @staticmethod
    def _approval_response(
        context: ContractVersionApprovalContextRecord,
        approvals: list[ContractVersionApprovalRecord],
    ) -> ContractVersionApprovalsResponse:
        by_role = {approval.party_role: approval for approval in approvals}

        def party(role: str) -> ContractVersionPartyApproval:
            approval = by_role.get(role)
            return ContractVersionPartyApproval(
                party_role=role,
                approved=approval is not None,
                approved_by_user_id=(approval.approved_by_user_id if approval else None),
                approved_at=(approval.approved_at if approval else None),
            )

        buyer = party("buyer")
        seller = party("seller")
        return ContractVersionApprovalsResponse(
            contract_id=context.contract_id,
            contract_version_id=context.contract_version_id,
            version_no=context.version_no,
            is_current_version=context.current_version_id == context.contract_version_id,
            buyer=buyer,
            seller=seller,
            all_approved=buyer.approved and seller.approved,
        )

    @staticmethod
    def _version_item(version: ContractVersionRecord) -> ContractVersionListItem:
        return ContractVersionListItem(
            id=version.id,
            version_no=version.version_no,
            version_label=f"V{version.version_no}",
            title=version.title,
            created_by_role=version.created_by_role,
            creation_reason=version.creation_reason,
            created_from_revision_request_id=version.created_from_revision_request_id,
            created_at=version.created_at,
            clause_count=len(version.clauses),
            risk=ContractVersionRiskSummary(
                score=version.risk_score,
                finding_count=version.risk_finding_count,
            ),
        )

    @classmethod
    def _compare_clauses(
        cls,
        before: list[ContractVersionClauseRecord],
        after: list[ContractVersionClauseRecord],
    ) -> list[VersionClauseChange]:
        unmatched_before = set(range(len(before)))
        unmatched_after = set(range(len(after)))
        matches: list[tuple[int, int]] = []

        def match_by(key_builder) -> None:
            after_keys: dict[object, list[int]] = {}
            for after_index in sorted(unmatched_after):
                key = key_builder(after[after_index])
                if key is not None:
                    after_keys.setdefault(key, []).append(after_index)
            for before_index in sorted(tuple(unmatched_before)):
                key = key_builder(before[before_index])
                candidates = after_keys.get(key) if key is not None else None
                if not candidates:
                    continue
                after_index = candidates.pop(0)
                unmatched_before.remove(before_index)
                unmatched_after.remove(after_index)
                matches.append((before_index, after_index))

        match_by(cls._clause_identity)
        match_by(lambda clause: (clause.title.strip(), clause.body.strip()))
        match_by(lambda clause: clause.title.strip())

        changes = []
        for before_index, after_index in sorted(matches):
            old = before[before_index]
            new = after[after_index]
            if (old.clause_key, old.title, old.body) != (new.clause_key, new.title, new.body):
                changes.append(
                    VersionClauseChange(
                        change_type="modified",
                        before=cls._clause_snapshot(old),
                        after=cls._clause_snapshot(new),
                    )
                )
        changes.extend(
            VersionClauseChange(
                change_type="deleted",
                before=cls._clause_snapshot(before[index]),
                after=None,
            )
            for index in sorted(unmatched_before)
        )
        changes.extend(
            VersionClauseChange(
                change_type="added",
                before=None,
                after=cls._clause_snapshot(after[index]),
            )
            for index in sorted(unmatched_after)
        )
        return changes

    @staticmethod
    def _clause_identity(clause: ContractVersionClauseRecord) -> tuple[str, str] | None:
        if clause.source_listing_clause_id is not None:
            return ("source", str(clause.source_listing_clause_id))
        if clause.clause_key:
            return ("key", clause.clause_key)
        return None

    @staticmethod
    def _clause_snapshot(clause: ContractVersionClauseRecord) -> VersionClauseSnapshot:
        return VersionClauseSnapshot(
            id=clause.id,
            clause_order=clause.clause_order,
            clause_key=clause.clause_key,
            title=clause.title,
            body=clause.body,
        )

    @classmethod
    def _price_change(
        cls, before: ContractVersionRecord, after: ContractVersionRecord
    ) -> VersionPriceChange:
        before_terms = cls._terms_snapshot(before)
        after_terms = cls._terms_snapshot(after)
        before_amount = cls._optional_int(before_terms.get("amount_minor"))
        after_amount = cls._optional_int(after_terms.get("amount_minor"))
        before_currency = cls._optional_str(before_terms.get("currency"))
        after_currency = cls._optional_str(after_terms.get("currency"))
        delta = None
        direction = "unknown"
        if (
            before_amount is not None
            and after_amount is not None
            and before_currency is not None
            and before_currency == after_currency
        ):
            delta = after_amount - before_amount
            direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
        return VersionPriceChange(
            direction=direction,
            before=VersionPriceSnapshot(amount_minor=before_amount, currency=before_currency),
            after=VersionPriceSnapshot(amount_minor=after_amount, currency=after_currency),
            delta_amount_minor=delta,
        )

    @classmethod
    def _period_change(
        cls, before: ContractVersionRecord, after: ContractVersionRecord
    ) -> VersionPeriodChange:
        before_terms = cls._terms_snapshot(before)
        after_terms = cls._terms_snapshot(after)
        before_period = VersionPeriodSnapshot(
            start_date=cls._optional_date(before_terms.get("service_start_date")),
            end_date=cls._optional_date(before_terms.get("service_end_date")),
        )
        after_period = VersionPeriodSnapshot(
            start_date=cls._optional_date(after_terms.get("service_start_date")),
            end_date=cls._optional_date(after_terms.get("service_end_date")),
        )
        values = (
            before_period.start_date,
            before_period.end_date,
            after_period.start_date,
            after_period.end_date,
        )
        changed = None if any(value is None for value in values) else before_period != after_period
        return VersionPeriodChange(changed=changed, before=before_period, after=after_period)

    @staticmethod
    def _risk_change(
        before: ContractVersionRecord, after: ContractVersionRecord
    ) -> VersionRiskChange:
        direction = "unknown"
        if before.risk_score is not None and after.risk_score is not None:
            difference = after.risk_score - before.risk_score
            direction = (
                "increased" if difference > 0 else "decreased" if difference < 0 else "unchanged"
            )
        return VersionRiskChange(
            direction=direction,
            before_score=before.risk_score,
            after_score=after.risk_score,
            before_finding_count=before.risk_finding_count,
            after_finding_count=after.risk_finding_count,
        )

    @staticmethod
    def _terms_snapshot(version: ContractVersionRecord) -> dict[str, Any]:
        value = version.structured_data.get("contract_terms")
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _optional_date(value: object) -> date | None:
        if not isinstance(value, str):
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _terms_response(record: ContractRecord) -> ContractTermsResponse:
        snapshot = record.calculation_snapshot
        try:
            quantity = int(snapshot["quantity"])
            quantity_unit = str(snapshot["quantity_unit"])
            nights = int(snapshot["nights"])
            formula = str(snapshot["formula"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="CONTRACT_PRICE_SNAPSHOT_INVALID",
                message="The contract price snapshot is incomplete.",
            ) from exc
        return ContractTermsResponse(
            people=record.requested_people,
            quantity=quantity,
            quantity_unit=quantity_unit,
            nights=nights,
            start_date=record.service_start_date,
            end_date=record.service_end_date,
            amount_minor=record.amount_minor,
            currency=record.currency,
            formula=formula,
        )

    @staticmethod
    def _created_response(record: ContractCreatedRecord) -> ContractRequestCreated:
        return ContractRequestCreated(
            contract_id=record.contract_id,
            status=record.status,
            version_no=record.version_no,
        )

    @staticmethod
    def _request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _idempotency_conflict(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_CONFLICT",
            message="The Idempotency-Key was already used for a different request.",
        ) from exc

    @staticmethod
    def _access_denied() -> None:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CONTRACT_ACCESS_DENIED",
            message="You do not have access to this contract.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc

    @staticmethod
    def _raise(status_code: int, code: str, message: str) -> None:
        raise AppError(status_code=status_code, code=code, message=message)
