import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.domain.pricing.units import (
    PRICE_UNIT_RULES,
    SUPPORTED_QUANTITY_UNITS,
    canonical_price_unit,
)
from app.integrations.auth import AuthenticatedUser
from app.repositories.seller_listings import (
    NewSellerListingClause,
    SellerListingDocumentAccessError,
    SellerListingHasContractsError,
    SellerListingIdempotencyConflictError,
    SellerListingMembershipRecord,
    SellerListingNotFoundError,
    SellerListingRecord,
    SellerListingRepository,
    SellerListingRepositoryError,
    SellerListingStateConflictError,
    SellerListingVersionConflictError,
)
from app.schemas.listings import (
    Money,
    SellerListingClause,
    SellerListingCreate,
    SellerListingCreated,
    SellerListingDetail,
    SellerListingMutationResponse,
    SellerListingPresentationPatch,
    SellerListingSummary,
    SellerListingTerms,
    SellerListingTermsPatch,
    SellerListingVersion,
)

_TERM_FIELDS = (
    "service_start_date",
    "service_end_date",
    "supply_quantity",
    "supply_quantity_description",
    "quantity_unit",
    "minimum_quantity",
    "maximum_quantity",
    "people_per_unit",
    "base_price_amount_minor",
    "currency",
    "price_unit",
    "minimum_people",
    "maximum_people",
    "cancellation_policy",
    "no_show_policy",
    "refund_policy",
    "settlement_policy",
    "safety_policy",
    "compensation_policy",
    "liability_policy",
    "termination_policy",
    "special_terms",
    "price_display_basis",
    "contract_availability_note",
)
_REQUIRED_TERMS = (
    "base_price_amount_minor",
    "currency",
    "price_unit",
    "cancellation_policy",
    "no_show_policy",
    "settlement_policy",
)
_CLAUSE_FIELDS = (
    ("cancellation_policy", "취소 조건"),
    ("no_show_policy", "노쇼 조건"),
    ("refund_policy", "환불 조건"),
    ("settlement_policy", "정산 조건"),
    ("safety_policy", "안전 조건"),
    ("compensation_policy", "보상 조건"),
    ("liability_policy", "책임 및 면책 조건"),
    ("termination_policy", "계약 해지 조건"),
    ("special_terms", "특약 사항"),
)


class SellerListingService:
    def __init__(self, repository: SellerListingRepository) -> None:
        self._repository = repository

    async def list_listings(
        self, actor: AuthenticatedUser, header_organization_id: str | None
    ) -> list[SellerListingSummary]:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        try:
            records = await self._repository.list_seller_listings(organization_id)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        return [self._summary(record) for record in records]

    async def get_listing(
        self,
        listing_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingDetail:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        record = await self._get_owned_listing(listing_id, organization_id)
        clauses = await self._clauses(record.current_version_id)
        return self._detail(record, clauses)

    async def create_listing(
        self,
        payload: SellerListingCreate,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
        idempotency_key: str,
    ) -> SellerListingCreated:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        request_hash = self._request_hash(
            {"organization_id": str(organization_id), **payload.model_dump(mode="json")}
        )
        try:
            created = await self._repository.create_listing(
                organization_id=organization_id,
                actor_user_id=actor.id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                creation_method=payload.creation_method.value,
                title=payload.title,
                category=payload.category.value,
                district=payload.district,
                language=payload.language.value,
            )
        except SellerListingIdempotencyConflictError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IDEMPOTENCY_CONFLICT",
                message="The Idempotency-Key was already used with a different request.",
            ) from exc
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        return SellerListingCreated(
            listing_id=created.listing_id,
            status=created.status,
            version_no=created.version_no,
        )

    async def update_terms(
        self,
        listing_id: UUID,
        payload: SellerListingTermsPatch,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingDetail:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        record = await self._get_owned_listing(listing_id, organization_id)
        if record.current_version_no != payload.base_version_no:
            self._version_conflict()
        changes = payload.terms.model_dump(exclude_unset=True)
        if not changes:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="At least one listing term must be provided.",
            )
        merged = {**self._term_values(record), **changes}
        self._validate_term_ranges(merged)
        self._validate_term_units(merged)
        clauses = self._build_clauses(merged)
        if record.status in {"published", "paused"}:
            missing = self._missing_fields(record, len(clauses), merged)
            if missing:
                self._not_publishable(missing)
        body = "\n\n".join(f"{clause.title}\n{clause.body}" for clause in clauses)
        try:
            updated = await self._repository.update_listing_terms(
                listing_id=listing_id,
                organization_id=organization_id,
                actor_user_id=actor.id,
                base_version_no=payload.base_version_no,
                changes=changes,
                structured_data=merged,
                body=body,
                clauses=clauses,
            )
        except SellerListingVersionConflictError as exc:
            self._version_conflict(exc)
        except SellerListingHasContractsError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="LISTING_HAS_CONTRACTS",
                message="Contract terms cannot change after a contract request exists.",
            ) from exc
        except SellerListingStateConflictError as exc:
            self._invalid_transition(exc)
        except SellerListingNotFoundError as exc:
            self._not_found(exc)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        updated_clauses = await self._clauses(updated.current_version_id)
        return self._detail(updated, updated_clauses)

    async def update_presentation(
        self,
        listing_id: UUID,
        payload: SellerListingPresentationPatch,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingDetail:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        await self._get_owned_listing(listing_id, organization_id)
        changes = payload.model_dump(exclude_unset=True)
        listing_changes = {
            key: value
            for key, value in changes.items()
            if key
            in {
                "display_company_name",
                "display_title",
                "hero_document_id",
                "seller_description",
                "public_headline",
            }
        }
        term_changes = {
            key: value
            for key, value in changes.items()
            if key in {"price_display_basis", "contract_availability_note"}
        }
        try:
            updated = await self._repository.update_listing_presentation(
                listing_id=listing_id,
                organization_id=organization_id,
                actor_user_id=actor.id,
                listing_changes=listing_changes,
                term_changes=term_changes,
            )
        except SellerListingDocumentAccessError as exc:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="DOCUMENT_ACCESS_DENIED",
                message="The hero document is not a ready document owned by this listing.",
            ) from exc
        except SellerListingStateConflictError as exc:
            self._invalid_transition(exc)
        except SellerListingNotFoundError as exc:
            self._not_found(exc)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        clauses = await self._clauses(updated.current_version_id)
        return self._detail(updated, clauses)

    async def complete_listing(
        self,
        listing_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingMutationResponse:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        record = await self._get_owned_listing(listing_id, organization_id)
        self._validate_term_units(self._term_values(record))
        clauses = await self._clauses(record.current_version_id)
        missing = self._missing_fields(record, len(clauses))
        if missing:
            self._not_publishable(missing)
        try:
            updated = await self._repository.complete_listing(
                listing_id=listing_id,
                organization_id=organization_id,
                actor_user_id=actor.id,
                expected_version_id=record.current_version_id,
            )
        except SellerListingVersionConflictError as exc:
            self._version_conflict(exc)
        except SellerListingStateConflictError as exc:
            self._invalid_transition(exc)
        except SellerListingNotFoundError as exc:
            self._not_found(exc)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        return self._mutation(updated, [])

    async def publish_listing(
        self,
        listing_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingMutationResponse:
        organization_id, membership = await self._authorize_organization(
            actor, header_organization_id
        )
        if membership.verification_status != "verified":
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="SELLER_NOT_VERIFIED",
                message="Only a verified seller organization can publish listings.",
            )
        record = await self._get_owned_listing(listing_id, organization_id)
        self._validate_term_units(self._term_values(record))
        clauses = await self._clauses(record.current_version_id)
        missing = self._missing_fields(record, len(clauses))
        if missing:
            self._not_publishable(missing)
        return await self._transition(record, organization_id, actor, "published")

    async def pause_listing(
        self,
        listing_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingMutationResponse:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        record = await self._get_owned_listing(listing_id, organization_id)
        return await self._transition(record, organization_id, actor, "paused")

    async def archive_listing(
        self,
        listing_id: UUID,
        actor: AuthenticatedUser,
        header_organization_id: str | None,
    ) -> SellerListingMutationResponse:
        organization_id, _ = await self._authorize_organization(actor, header_organization_id)
        record = await self._get_owned_listing(listing_id, organization_id)
        return await self._transition(record, organization_id, actor, "archived")

    async def _transition(
        self,
        record: SellerListingRecord,
        organization_id: UUID,
        actor: AuthenticatedUser,
        target_status: str,
    ) -> SellerListingMutationResponse:
        try:
            updated = await self._repository.transition_listing(
                listing_id=record.id,
                organization_id=organization_id,
                actor_user_id=actor.id,
                target_status=target_status,
            )
        except SellerListingStateConflictError as exc:
            if str(exc) == "seller_not_verified":
                raise AppError(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="SELLER_NOT_VERIFIED",
                    message="Only a verified seller organization can publish listings.",
                ) from exc
            self._invalid_transition(exc)
        except SellerListingNotFoundError as exc:
            self._not_found(exc)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        return self._mutation(updated, self._missing_fields(updated))

    async def _authorize_organization(
        self, actor: AuthenticatedUser, header: str | None
    ) -> tuple[UUID, SellerListingMembershipRecord]:
        if header is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required for seller organization APIs.",
            )
        try:
            organization_id = UUID(header)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="X-Organization-Id must be a UUID.",
            ) from exc
        try:
            membership = await self._repository.get_membership(actor.id, organization_id)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        if membership is None or membership.organization_type != "seller":
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ORG_ACCESS_DENIED",
                message="You do not have access to this seller organization.",
            )
        return organization_id, membership

    async def _get_owned_listing(
        self, listing_id: UUID, organization_id: UUID
    ) -> SellerListingRecord:
        try:
            record = await self._repository.get_seller_listing(listing_id)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)
        if record is None or record.seller_organization_id != organization_id:
            self._not_found()
        return record

    async def _clauses(self, version_id: UUID):
        try:
            return await self._repository.list_listing_clauses(version_id)
        except SellerListingRepositoryError as exc:
            self._database_unavailable(exc)

    @staticmethod
    def _term_values(record: SellerListingRecord) -> dict[str, Any]:
        return {field: getattr(record, field) for field in _TERM_FIELDS}

    @staticmethod
    def _validate_term_ranges(terms: dict[str, Any]) -> None:
        start = terms["service_start_date"]
        end = terms["service_end_date"]
        if start is not None and end is not None and start > end:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="service_start_date must be on or before service_end_date.",
            )
        minimum = terms["minimum_people"]
        maximum = terms["maximum_people"]
        if minimum is not None and maximum is not None and minimum > maximum:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="minimum_people must be less than or equal to maximum_people.",
            )
        minimum_quantity = terms["minimum_quantity"]
        maximum_quantity = terms["maximum_quantity"]
        if (
            minimum_quantity is not None
            and maximum_quantity is not None
            and minimum_quantity > maximum_quantity
        ):
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message=("minimum_quantity must be less than or equal to maximum_quantity."),
            )

    @staticmethod
    def _validate_term_units(terms: dict[str, Any]) -> None:
        quantity_unit = terms["quantity_unit"]
        price_unit = canonical_price_unit(terms["price_unit"])
        if quantity_unit is not None and quantity_unit not in SUPPORTED_QUANTITY_UNITS:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="UNSUPPORTED_QUANTITY_UNIT",
                message="The listing quantity unit is not supported.",
            )
        if price_unit is not None and price_unit not in PRICE_UNIT_RULES:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="UNSUPPORTED_PRICE_UNIT",
                message="The listing price unit is not supported.",
            )
        if quantity_unit is not None and price_unit is not None:
            expected_quantity_unit = PRICE_UNIT_RULES[price_unit].quantity_unit
            if quantity_unit != expected_quantity_unit:
                raise AppError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="UNSUPPORTED_QUANTITY_UNIT",
                    message="The listing quantity unit does not match its price unit.",
                )

    @staticmethod
    def _build_clauses(terms: dict[str, Any]) -> list[NewSellerListingClause]:
        return [
            NewSellerListingClause(clause_key=field, title=title, body=value)
            for field, title in _CLAUSE_FIELDS
            if isinstance((value := terms[field]), str) and value
        ]

    @staticmethod
    def _missing_fields(
        record: SellerListingRecord,
        clause_count: int | None = None,
        terms: dict[str, Any] | None = None,
    ) -> list[str]:
        values = terms or SellerListingService._term_values(record)
        missing = [
            field
            for field in _REQUIRED_TERMS
            if values[field] is None
            or (isinstance(values[field], str) and not values[field].strip())
        ]
        if not values["supply_quantity_description"] and values["supply_quantity"] is None:
            missing.append("supply_quantity_description")
        if not record.title.strip():
            missing.insert(0, "title")
        if not record.district.strip():
            missing.insert(0, "district")
        if not record.organization_name.strip():
            missing.insert(0, "seller")
        if record.current_version_id is None:
            missing.append("current_version")
        effective_clause_count = (
            clause_count if clause_count is not None else int(bool(record.current_version_body))
        )
        if effective_clause_count == 0:
            missing.append("clauses")
        return missing

    @classmethod
    def _summary(cls, record: SellerListingRecord) -> SellerListingSummary:
        base_price = None
        if record.base_price_amount_minor is not None and record.currency is not None:
            base_price = Money(
                amount_minor=record.base_price_amount_minor,
                currency=record.currency,
                unit=record.price_unit,
            )
        return SellerListingSummary(
            id=record.id,
            title=record.title,
            display_title=record.display_title,
            category=record.category,
            district=record.district,
            status=record.status,
            creation_method=record.creation_method,
            public_headline=record.public_headline,
            service_start_date=record.service_start_date,
            service_end_date=record.service_end_date,
            supply_quantity_description=record.supply_quantity_description,
            base_price=base_price,
            contract_available=record.status == "published",
            attention_required_count=record.attention_required_count,
            current_version_no=record.current_version_no,
            contract_request_count=record.contract_request_count,
            missing_fields=cls._missing_fields(record),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @classmethod
    def _detail(cls, record: SellerListingRecord, clauses) -> SellerListingDetail:
        summary = cls._summary(record)
        return SellerListingDetail(
            **summary.model_dump(exclude={"missing_fields"}),
            missing_fields=cls._missing_fields(record, len(clauses)),
            language=record.language,
            display_company_name=record.display_company_name,
            seller_description=record.seller_description,
            ai_summary=record.ai_summary,
            hero_document_id=record.hero_document_id,
            terms=SellerListingTerms(**cls._term_values(record)),
            current_version=SellerListingVersion(
                id=record.current_version_id,
                version_no=record.current_version_no,
                title=record.current_version_title,
                body=record.current_version_body,
                created_at=record.current_version_created_at,
                clauses=[
                    SellerListingClause(
                        id=clause.id,
                        clause_order=clause.clause_order,
                        clause_key=clause.clause_key,
                        title=clause.title,
                        body=clause.body,
                    )
                    for clause in clauses
                ],
            ),
            processing_job=None,
            published_at=record.published_at,
            paused_at=record.paused_at,
        )

    @staticmethod
    def _mutation(
        record: SellerListingRecord, missing_fields: list[str]
    ) -> SellerListingMutationResponse:
        return SellerListingMutationResponse(
            listing_id=record.id,
            status=record.status,
            version_no=record.current_version_no,
            missing_fields=missing_fields,
        )

    @staticmethod
    def _request_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _not_publishable(missing_fields: list[str]) -> None:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="LISTING_NOT_PUBLISHABLE",
            message="Required listing information is missing.",
            details={"missing_fields": missing_fields},
        )

    @staticmethod
    def _not_found(exc: Exception | None = None) -> None:
        error = AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="LISTING_NOT_FOUND",
            message="Seller listing was not found.",
        )
        if exc is None:
            raise error
        raise error from exc

    @staticmethod
    def _version_conflict(exc: Exception | None = None) -> None:
        error = AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="VERSION_CONFLICT",
            message="The listing version changed before the update was applied.",
        )
        if exc is None:
            raise error
        raise error from exc

    @staticmethod
    def _invalid_transition(exc: Exception | None = None) -> None:
        error = AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="INVALID_STATE_TRANSITION",
            message="The listing cannot be changed from its current state.",
        )
        if exc is None:
            raise error
        raise error from exc

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
