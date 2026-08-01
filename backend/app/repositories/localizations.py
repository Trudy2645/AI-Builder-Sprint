from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class LocalizationSourceRecord:
    listing: dict[str, Any]
    clauses: list[dict[str, Any]]
    findings: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class LocalizationCacheRecord:
    id: UUID
    locale: str
    content: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LocalizationJobClaim:
    job_id: UUID
    should_run: bool


class LocalizationRepositoryError(Exception):
    pass


class LocalizationIdempotencyConflictError(Exception):
    pass


class LocalizationRepository(Protocol):
    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...

    async def get_source(
        self, listing_id: UUID, organization_id: UUID
    ) -> LocalizationSourceRecord | None: ...

    async def get_cached(
        self,
        version_id: UUID,
        locale: str,
        prompt_version: str,
        source_hash: str,
    ) -> LocalizationCacheRecord | None: ...

    async def claim_job(
        self,
        *,
        version_id: UUID,
        locale: str,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
        batch_request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> LocalizationJobClaim: ...

    async def save_localization(
        self,
        *,
        job_id: UUID,
        version_id: UUID,
        locale: str,
        content: dict[str, Any],
        source_hash: str,
        prompt_version: str,
        model_name: str,
    ) -> LocalizationCacheRecord: ...

    async def fail_job(self, job_id: UUID, failure_code: str) -> None: ...


class SqlAlchemyLocalizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        row = await self._one(
            """
            select 1 from public.organization_members
            where user_id = :user_id and organization_id = :organization_id
            """,
            {"user_id": user_id, "organization_id": organization_id},
        )
        return row is not None

    async def get_source(
        self, listing_id: UUID, organization_id: UUID
    ) -> LocalizationSourceRecord | None:
        listing = await self._one(
            """
            select l.id, l.current_version_id, lv.version_no,
                   lv.content_sha256 as current_version_hash,
                   coalesce(l.display_title, l.title) as title,
                   l.language::text as language, l.public_headline, l.ai_summary,
                   coalesce(l.display_company_name, o.name) as seller_name,
                   l.district, l.category::text as category,
                   lt.service_start_date, lt.service_end_date, lt.supply_quantity,
                   lt.supply_quantity_description, lt.quantity_unit,
                   lt.minimum_quantity, lt.maximum_quantity,
                   lt.people_per_unit, lt.base_price_amount_minor, lt.currency,
                   lt.price_unit, lt.minimum_people, lt.maximum_people,
                   lt.cancellation_policy, lt.no_show_policy, lt.refund_policy,
                   lt.settlement_policy, lt.safety_policy, lt.compensation_policy,
                   lt.liability_policy, lt.termination_policy, lt.special_terms,
                   lt.price_display_basis, lt.contract_availability_note
            from public.listings l
            join public.listing_versions lv on lv.id = l.current_version_id
            join public.organizations o on o.id = l.seller_organization_id
            left join public.listing_terms lt on lt.listing_id = l.id
            where l.id = :listing_id and l.seller_organization_id = :organization_id
              and l.status in ('published', 'paused')
            """,
            {"listing_id": listing_id, "organization_id": organization_id},
        )
        if listing is None:
            return None
        version_id = listing["current_version_id"]
        clauses = await self._all(
            """
            select id, clause_order, clause_key, title, body
            from public.listing_clauses
            where listing_version_id = :version_id order by clause_order
            """,
            {"version_id": version_id},
        )
        findings = await self._all(
            """
            with latest_buyer_analysis as (
                select id from public.ai_analysis_runs
                where listing_version_id = :version_id and viewer_role = 'buyer'
                  and status = 'succeeded'
                order by completed_at desc nulls last, created_at desc limit 1
            )
            select af.id, af.listing_clause_id as clause_id,
                   af.severity::text as severity, af.explanation,
                   af.suggested_text, af.disclaimer, af.evidence
            from public.ai_findings af
            where af.analysis_run_id = (select id from latest_buyer_analysis)
              and af.status in ('open', 'applied') and af.is_public = true
            order by case af.severity
                         when 'high' then 1 when 'medium' then 2
                         when 'low' then 3 else 4
                     end,
                     af.created_at, af.id
            """,
            {"version_id": version_id},
        )
        for finding in findings:
            finding["evidence_numbers"] = list(range(1, len(finding.pop("evidence") or []) + 1))
        return LocalizationSourceRecord(dict(listing), clauses, findings)

    async def get_cached(
        self,
        version_id: UUID,
        locale: str,
        prompt_version: str,
        source_hash: str,
    ) -> LocalizationCacheRecord | None:
        row = await self._one(
            """
            select id, locale::text, content
            from public.localized_contents
            where listing_version_id = :version_id
              and locale = cast(:locale as public.supported_locale)
              and content_type = 'public_listing'
              and prompt_version = :prompt_version and source_hash = :source_hash
              and numeric_validation_passed = true
            order by created_at desc limit 1
            """,
            {
                "version_id": version_id,
                "locale": locale,
                "prompt_version": prompt_version,
                "source_hash": source_hash,
            },
        )
        return LocalizationCacheRecord(**dict(row)) if row else None

    async def claim_job(
        self,
        *,
        version_id: UUID,
        locale: str,
        actor_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
        batch_request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> LocalizationJobClaim:
        scoped_key = hashlib.sha256(
            f"localize:{actor_user_id}:{version_id}:{locale}:{idempotency_key}".encode()
        ).hexdigest()
        batch_id = hashlib.sha256(
            f"localize_batch:{actor_user_id}:{version_id}:{idempotency_key}".encode()
        ).hexdigest()
        job_id = uuid4()
        metadata = json.dumps(
            {
                "request_hash": request_hash,
                "batch_id": batch_id,
                "batch_request_hash": batch_request_hash,
                "locale": locale,
                "content_type": "public_listing",
            }
        )
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                batch = await self._session.execute(
                    text(
                        """
                        select result_metadata ->> 'batch_request_hash' as request_hash
                        from public.ai_jobs
                        where listing_version_id = :version_id
                          and job_type = 'localize_explain'
                          and result_metadata ->> 'batch_id' = :batch_id
                        limit 1
                        """
                    ),
                    {"version_id": version_id, "batch_id": batch_id},
                )
                batch_row = batch.mappings().one_or_none()
                if batch_row and batch_row["request_hash"] != batch_request_hash:
                    raise LocalizationIdempotencyConflictError
                existing = await self._session.execute(
                    text(
                        """
                        select id, status::text, result_metadata from public.ai_jobs
                        where idempotency_key = :key for update
                        """
                    ),
                    {"key": scoped_key},
                )
                row = existing.mappings().one_or_none()
                if row:
                    if (row["result_metadata"] or {}).get("request_hash") != request_hash:
                        raise LocalizationIdempotencyConflictError
                    return LocalizationJobClaim(row["id"], False)
                await self._session.execute(
                    text(
                        """
                        insert into public.ai_jobs (
                            id, listing_version_id, job_type, status, idempotency_key,
                            provider, model_name, prompt_version, result_metadata,
                            started_at, attempt_count
                        ) values (
                            :id, :version_id, 'localize_explain', 'processing', :key,
                            :provider, :model_name, :prompt_version, cast(:metadata as jsonb),
                            now(), 1
                        )
                        """
                    ),
                    {
                        "id": job_id,
                        "version_id": version_id,
                        "key": scoped_key,
                        "provider": provider,
                        "model_name": model_name,
                        "prompt_version": prompt_version,
                        "metadata": metadata,
                    },
                )
            return LocalizationJobClaim(job_id, True)
        except LocalizationIdempotencyConflictError:
            raise
        except SQLAlchemyError as exc:
            raise LocalizationRepositoryError from exc

    async def save_localization(
        self,
        *,
        job_id: UUID,
        version_id: UUID,
        locale: str,
        content: dict[str, Any],
        source_hash: str,
        prompt_version: str,
        model_name: str,
    ) -> LocalizationCacheRecord:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                result = await self._session.execute(
                    text(
                        """
                        insert into public.localized_contents (
                            listing_version_id, locale, content_type, content, source_hash,
                            prompt_version, model_name, numeric_validation_passed
                        ) values (
                            :version_id, cast(:locale as public.supported_locale),
                            'public_listing', cast(:content as jsonb), :source_hash,
                            :prompt_version, :model_name, true
                        )
                        on conflict (listing_version_id, locale, content_type,
                                     prompt_version, source_hash)
                            where listing_version_id is not null
                        do update set content = excluded.content,
                                      numeric_validation_passed = true
                        returning id, locale::text, content
                        """
                    ),
                    {
                        "version_id": version_id,
                        "locale": locale,
                        "content": json.dumps(content, ensure_ascii=False),
                        "source_hash": source_hash,
                        "prompt_version": prompt_version,
                        "model_name": model_name,
                    },
                )
                row = result.mappings().one()
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs
                        set status = 'succeeded', provider_status = 'succeeded',
                            completed_at = now(), result_metadata = result_metadata ||
                            jsonb_build_object('localized_content_id', cast(:content_id as text))
                        where id = :job_id and status = 'processing'
                        """
                    ),
                    {"job_id": job_id, "content_id": row["id"]},
                )
            return LocalizationCacheRecord(**dict(row))
        except SQLAlchemyError as exc:
            raise LocalizationRepositoryError from exc

    async def fail_job(self, job_id: UUID, failure_code: str) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs
                        set status = 'failed', provider_status = 'failed',
                            failure_code = :failure_code, failure_message = null,
                            completed_at = now()
                        where id = :job_id and status = 'processing'
                        """
                    ),
                    {"job_id": job_id, "failure_code": failure_code},
                )
        except SQLAlchemyError as exc:
            raise LocalizationRepositoryError from exc

    async def _one(self, sql: str, params: dict[str, Any]):
        try:
            result = await self._session.execute(text(sql), params)
            return result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise LocalizationRepositoryError from exc

    async def _all(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            result = await self._session.execute(text(sql), params)
            return [dict(row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            raise LocalizationRepositoryError from exc
