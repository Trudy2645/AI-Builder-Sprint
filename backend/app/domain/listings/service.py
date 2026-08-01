from __future__ import annotations

import base64
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import status
from pydantic import ValidationError

from app.ai.schemas import LocalizedPublicContent
from app.ai.tasks.localize_explain import (
    build_public_localization_source,
    localization_source_hash,
)
from app.core.errors import AppError
from app.repositories.listings import (
    ListingCursor,
    ListingRepositoryUnavailableError,
    ListingSearchFilters,
    PublicClauseRecord,
    PublicFindingRecord,
    PublicListingRecord,
    PublicListingRepository,
)
from app.schemas.listings import (
    Availability,
    Money,
    PublicClause,
    PublicContractPreview,
    PublicFinding,
    PublicListingCard,
    PublicListingDetail,
    PublicListingQuery,
    PublicSeller,
    SupportedLocale,
)


class PublicListingService:
    def __init__(self, repository: PublicListingRepository) -> None:
        self._repository = repository

    async def list_listings(
        self, query: PublicListingQuery
    ) -> tuple[list[PublicListingCard], str | None, bool]:
        cursor = self._decode_cursor(query.cursor, query.sort.value) if query.cursor else None
        filters = ListingSearchFilters(
            q=query.q,
            contract_available_only=query.contract_available_only,
            districts=tuple(dict.fromkeys(query.district)),
            people=query.people,
            min_price=query.min_price,
            max_price=query.max_price,
            currency=query.currency,
            category=query.category,
            start_date=query.start_date,
            end_date=query.end_date,
            sort=query.sort,
        )
        try:
            records = await self._repository.search_public_listings(
                filters, cursor, query.limit + 1
            )
        except ListingRepositoryUnavailableError as exc:
            self._database_unavailable(exc)

        has_more = len(records) > query.limit
        page = records[: query.limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = self._encode_cursor(query.sort.value, last.sort_value, last.id)
        localized = await self._list_localized_cards(page, query.locale)
        return (
            [
                self._card(record, query.locale, localized.get(record.current_version_id))
                for record in page
            ],
            next_cursor,
            has_more,
        )

    async def get_listing(
        self, listing_id: UUID, requested_locale: SupportedLocale
    ) -> PublicListingDetail:
        try:
            listing = await self._repository.get_public_listing(listing_id)
            if listing is None or listing.current_version_id is None:
                self._not_found()
            clauses = await self._repository.list_public_clauses(listing.current_version_id)
            findings = await self._repository.list_public_findings(listing.current_version_id)
        except ListingRepositoryUnavailableError as exc:
            self._database_unavailable(exc)

        localized = await self._localized_content(listing, clauses, findings, requested_locale)
        return PublicListingDetail(
            **self._card(listing, requested_locale, localized).model_dump(),
            supply_quantity=listing.supply_quantity,
            supply_quantity_description=listing.supply_quantity_description,
            quantity_unit=listing.quantity_unit,
            minimum_quantity=listing.minimum_quantity,
            maximum_quantity=listing.maximum_quantity,
            people_per_unit=listing.people_per_unit,
            minimum_people=listing.minimum_people,
            maximum_people=listing.maximum_people,
            cancellation_policy=listing.cancellation_policy,
            no_show_policy=listing.no_show_policy,
            refund_policy=listing.refund_policy,
            settlement_policy=listing.settlement_policy,
            safety_policy=listing.safety_policy,
            compensation_policy=listing.compensation_policy,
            liability_policy=listing.liability_policy,
            termination_policy=listing.termination_policy,
            special_terms=listing.special_terms,
            price_display_basis=listing.price_display_basis,
            contract_availability_note=listing.contract_availability_note,
            clauses=self._clauses(clauses, findings),
            localized_content=localized,
        )

    async def get_contract_preview(
        self, listing_id: UUID, requested_locale: SupportedLocale
    ) -> PublicContractPreview:
        try:
            listing = await self._repository.get_public_listing(listing_id)
            if listing is None or listing.current_version_id is None:
                self._not_found()
            version = await self._repository.get_public_version(
                listing.id, listing.current_version_id
            )
            if version is None:
                self._not_found()
            clauses = await self._repository.list_public_clauses(version.id)
            findings = await self._repository.list_public_findings(version.id)
        except ListingRepositoryUnavailableError as exc:
            self._database_unavailable(exc)

        localized = await self._localized_content(listing, clauses, findings, requested_locale)
        content_locale, fallback_locale = self._locale_metadata(
            listing, requested_locale, localized is not None
        )
        return PublicContractPreview(
            listing_version_id=version.id,
            body=version.body,
            clauses=self._clauses(clauses, findings),
            findings=[
                PublicFinding(
                    clause_id=finding.clause_id,
                    severity=finding.severity,  # type: ignore[arg-type]
                    explanation=finding.explanation,
                    suggested_text=finding.suggested_text,
                    disclaimer=finding.disclaimer,
                )
                for finding in findings
            ],
            requested_locale=requested_locale,
            content_locale=content_locale,
            fallback_locale=fallback_locale,
            localized_content=localized,
        )

    @staticmethod
    def _card(
        record: PublicListingRecord,
        requested_locale: SupportedLocale = SupportedLocale.KO_KR,
        localized: LocalizedPublicContent | None = None,
    ) -> PublicListingCard:
        base_price = None
        if record.base_price_amount_minor is not None and record.currency is not None:
            base_price = Money(
                amount_minor=record.base_price_amount_minor,
                currency=record.currency,
                unit=record.price_unit,
            )
        return PublicListingCard(
            id=record.id,
            seller=PublicSeller(
                name=record.seller_name,
                rating=record.rating_average,
                rating_count=record.rating_count,
                verified=record.verification_status == "verified",
            ),
            title=localized.title if localized else record.title,
            district=record.district,
            category=record.category,  # type: ignore[arg-type]
            hero_image_url=None,
            public_headline=(localized.public_headline if localized else record.public_headline),
            ai_summary=localized.summary if localized else record.ai_summary,
            base_price=base_price,
            availability=Availability(
                start_date=record.service_start_date,
                end_date=record.service_end_date,
            ),
            status=record.status,  # type: ignore[arg-type]
            contract_available=record.status == "published",
            attention_required_count=record.attention_required_count,
            requested_locale=requested_locale,
            content_locale=(requested_locale if localized else SupportedLocale(record.language)),
            fallback_locale=(
                None
                if localized or requested_locale == SupportedLocale(record.language)
                else SupportedLocale(record.language)
            ),
        )

    @classmethod
    def _clauses(
        cls,
        clauses: list[PublicClauseRecord],
        findings: list[PublicFindingRecord],
    ) -> list[PublicClause]:
        finding_severity = {
            finding.clause_id: finding.severity
            for finding in reversed(findings)
            if finding.clause_id is not None
        }
        return [
            PublicClause(
                id=clause.id,
                clause_key=clause.clause_key,
                title=clause.title,
                body=clause.body,
                highlight=cls._highlight(finding_severity.get(clause.id)),
            )
            for clause in clauses
        ]

    @staticmethod
    def _highlight(severity: str | None) -> str | None:
        return {"high": "critical", "medium": "warning", "low": "info"}.get(severity)

    @staticmethod
    def _locale_metadata(
        listing: PublicListingRecord,
        requested_locale: SupportedLocale,
        localized: bool,
    ) -> tuple[SupportedLocale, SupportedLocale | None]:
        if localized:
            return requested_locale, None
        content_locale = SupportedLocale(listing.language)
        fallback = None if content_locale == requested_locale else content_locale
        return content_locale, fallback

    async def _localized_content(
        self,
        listing: PublicListingRecord,
        clauses: list[PublicClauseRecord],
        findings: list[PublicFindingRecord],
        requested_locale: SupportedLocale,
    ) -> LocalizedPublicContent | None:
        getter = getattr(self._repository, "get_localized_content", None)
        if getter is None or listing.current_version_id is None:
            return None
        try:
            cached = await getter(listing.current_version_id, requested_locale.value)
        except ListingRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if cached is None or listing.current_version_hash is None:
            return None
        source_listing = asdict(listing)
        source_listing["current_version_hash"] = listing.current_version_hash
        source = build_public_localization_source(
            source_listing,
            [asdict(item) for item in clauses],
            [
                {
                    **asdict(item),
                    "evidence_numbers": item.evidence_numbers or [],
                }
                for item in findings
                if item.id is not None
            ],
        )
        if localization_source_hash(source) != cached.source_hash:
            return None
        try:
            return LocalizedPublicContent.model_validate(cached.content)
        except ValidationError:
            return None

    async def _list_localized_cards(
        self,
        records: list[PublicListingRecord],
        requested_locale: SupportedLocale,
    ) -> dict[UUID | None, LocalizedPublicContent]:
        getter = getattr(self._repository, "list_localized_contents", None)
        if getter is None:
            return {}
        version_ids = [
            record.current_version_id for record in records if record.current_version_id is not None
        ]
        try:
            cached = await getter(version_ids, requested_locale.value)
        except ListingRepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        localized: dict[UUID | None, LocalizedPublicContent] = {}
        listings_by_version = {
            record.current_version_id: record
            for record in records
            if record.current_version_id is not None
        }
        for version_id, cache_record in cached.items():
            listing = listings_by_version.get(version_id)
            if listing is None or listing.current_version_hash is None:
                continue
            try:
                clauses = await self._repository.list_public_clauses(version_id)
                findings = await self._repository.list_public_findings(version_id)
                source = build_public_localization_source(
                    asdict(listing),
                    [asdict(item) for item in clauses],
                    [
                        {
                            **asdict(item),
                            "evidence_numbers": item.evidence_numbers or [],
                        }
                        for item in findings
                        if item.id is not None
                    ],
                )
                if localization_source_hash(source) != cache_record.source_hash:
                    continue
                localized[version_id] = LocalizedPublicContent.model_validate(cache_record.content)
            except ListingRepositoryUnavailableError as exc:
                self._database_unavailable(exc)
            except ValidationError:
                continue
        return localized

    @staticmethod
    def _encode_cursor(sort: str, value: Decimal | int | datetime, listing_id: UUID) -> str:
        serialized_value = value.isoformat() if isinstance(value, datetime) else str(value)
        payload = json.dumps(
            {"version": 1, "sort": sort, "value": serialized_value, "id": str(listing_id)},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode()

    @staticmethod
    def _decode_cursor(cursor: str, expected_sort: str) -> ListingCursor:
        try:
            padding = "=" * (-len(cursor) % 4)
            raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
            payload: dict[str, Any] = json.loads(raw)
            if set(payload) != {"version", "sort", "value", "id"}:
                raise ValueError
            if payload["version"] != 1 or payload["sort"] != expected_sort:
                raise ValueError
            value = payload["value"]
            if not isinstance(value, str) or not value:
                raise ValueError
            listing_id = UUID(payload["id"])
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CURSOR",
                message="The pagination cursor is invalid for this sort order.",
            ) from exc
        return ListingCursor(value=value, listing_id=listing_id)

    @staticmethod
    def _not_found() -> None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="LISTING_NOT_FOUND",
            message="Public listing was not found.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
