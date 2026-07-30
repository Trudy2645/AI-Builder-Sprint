import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.domain.pricing.service import PriceCalculator
from app.integrations.auth import AuthenticatedUser
from app.repositories.contracts import (
    ContractCreatedRecord,
    ContractRecord,
    ContractRepository,
    ContractRepositoryUnavailableError,
    ContractRequestSourceRecord,
    ContractStateConflictError,
    IdempotencyConflictError,
    NewContractData,
)
from app.repositories.pricing import ListingPriceTermsRecord
from app.schemas.contracts import (
    ContractCancelResponse,
    ContractClauseResponse,
    ContractDetail,
    ContractPartySummary,
    ContractRequestCreate,
    ContractRequestCreated,
    ContractSummary,
    ContractTermsResponse,
    ContractVersionResponse,
    InitialRequestKind,
)
from app.schemas.pricing import PriceEstimateRequest

_CANCELLABLE_STATUSES = {"draft", "seller_review", "revision_requested"}


class ContractService:
    def __init__(
        self,
        repository: ContractRepository,
        price_calculator: PriceCalculator,
    ) -> None:
        self._repository = repository
        self._price_calculator = price_calculator

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
        await self._authorize_contract(record, actor, header_organization_id)
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
        return ContractDetail(
            **self._summary(record).model_dump(),
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

    async def list_my_contracts(self, actor: AuthenticatedUser) -> list[ContractSummary]:
        try:
            records = await self._repository.list_buyer_contracts(actor.id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return [self._summary(record) for record in records]

    async def list_received_contracts(
        self,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> list[ContractSummary]:
        organization_id = await self._authorize_seller_header(actor, header_organization_id)
        try:
            records = await self._repository.list_seller_contracts(organization_id)
        except ContractRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return [self._summary(record) for record in records]

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

    @staticmethod
    def _summary(record: ContractRecord) -> ContractSummary:
        return ContractSummary(
            id=record.id,
            listing_id=record.listing_id,
            listing_title=record.listing_title,
            status=record.status,
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
