from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

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
)


@dataclass(frozen=True, slots=True)
class ContractGenerationMembershipRecord:
    organization_id: UUID
    organization_type: str


@dataclass(frozen=True, slots=True)
class ContractGenerationInputRecord:
    id: UUID
    seller_organization_id: UUID
    organization_name: str
    title: str
    category: str
    district: str
    language: str
    status: str
    current_version_id: UUID
    current_version_no: int
    terms: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NewGeneratedClause:
    clause_key: str
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class GeneratedClauseRecord:
    id: UUID
    clause_order: int
    clause_key: str
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class ContractGenerationRecord:
    listing_id: UUID
    job_id: UUID
    listing_version_id: UUID
    version_no: int
    status: str
    clauses: list[GeneratedClauseRecord]


@dataclass(frozen=True, slots=True)
class ContractGenerationClaim:
    job_id: UUID | None
    cached: ContractGenerationRecord | None


class ContractGenerationRepositoryError(Exception):
    pass


class ContractGenerationNotFoundError(Exception):
    pass


class ContractGenerationVersionConflictError(Exception):
    pass


class ContractGenerationStateConflictError(Exception):
    pass


class ContractGenerationIdempotencyConflictError(Exception):
    pass


class ContractGenerationInProgressError(Exception):
    pass


class ContractGenerationRepository(Protocol):
    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> ContractGenerationMembershipRecord | None: ...

    async def get_input(self, listing_id: UUID) -> ContractGenerationInputRecord | None: ...

    async def claim_generation(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        expected_version_no: int,
        idempotency_key: str,
        request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> ContractGenerationClaim: ...

    async def complete_generation(
        self,
        *,
        listing: ContractGenerationInputRecord,
        actor_user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
        request_hash: str,
        clauses: list[NewGeneratedClause],
        body: str,
        ai_summary: str,
        result_metadata: dict[str, Any],
    ) -> ContractGenerationRecord: ...

    async def fail_generation(
        self,
        *,
        listing: ContractGenerationInputRecord,
        job_id: UUID,
        idempotency_key: str,
        failure_code: str,
    ) -> None: ...


class SqlAlchemyContractGenerationRepository:
    _OPERATION = "seller_listing_generate"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> ContractGenerationMembershipRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.organization_type::text
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id and om.organization_id = :organization_id
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
            row = result.mappings().one_or_none()
            return ContractGenerationMembershipRecord(**row) if row else None
        except SQLAlchemyError as exc:
            raise ContractGenerationRepositoryError from exc

    async def get_input(self, listing_id: UUID) -> ContractGenerationInputRecord | None:
        try:
            result = await self._session.execute(
                text(
                    f"""
                    select l.id, l.seller_organization_id, o.name as organization_name,
                           l.title, l.category::text as category, l.district,
                           l.language::text as language, l.status::text as status,
                           l.current_version_id, lv.version_no as current_version_no,
                           {", ".join(f"lt.{field}" for field in _TERM_FIELDS)}
                    from public.listings l
                    join public.organizations o on o.id = l.seller_organization_id
                    join public.listing_versions lv on lv.id = l.current_version_id
                    join public.listing_terms lt on lt.listing_id = l.id
                    where l.id = :listing_id
                    """  # noqa: S608
                ),
                {"listing_id": listing_id},
            )
            row = result.mappings().one_or_none()
            if row is None:
                return None
            values = dict(row)
            terms = {field: values.pop(field) for field in _TERM_FIELDS}
            return ContractGenerationInputRecord(**values, terms=terms)
        except SQLAlchemyError as exc:
            raise ContractGenerationRepositoryError from exc

    async def claim_generation(
        self,
        *,
        listing_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        expected_version_no: int,
        idempotency_key: str,
        request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> ContractGenerationClaim:
        job_id = uuid4()
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing = await self._idempotency_record(
                    organization_id, listing_id, idempotency_key, lock=True
                )
                if existing is not None:
                    if existing["request_hash"] != request_hash:
                        raise ContractGenerationIdempotencyConflictError
                    if existing["response_body"] is None:
                        raise ContractGenerationInProgressError
                    return ContractGenerationClaim(
                        job_id=None,
                        cached=self._record_from_response(existing["response_body"]),
                    )
                locked = await self._session.execute(
                    text(
                        """
                        select l.status::text as status, l.current_version_id,
                               lv.version_no as current_version_no
                        from public.listings l
                        join public.listing_versions lv on lv.id = l.current_version_id
                        where l.id = :listing_id
                          and l.seller_organization_id = :organization_id
                        for update of l
                        """
                    ),
                    {"listing_id": listing_id, "organization_id": organization_id},
                )
                row = locked.mappings().one_or_none()
                if row is None:
                    raise ContractGenerationNotFoundError
                if row["current_version_no"] != expected_version_no:
                    raise ContractGenerationVersionConflictError
                if row["status"] != "draft":
                    raise ContractGenerationStateConflictError
                await self._session.execute(
                    text(
                        """
                        insert into public.idempotency_records (
                            organization_id, operation, idempotency_key, request_hash,
                            resource_type, resource_id, expires_at
                        ) values (
                            :organization_id, :operation, :idempotency_key, :request_hash,
                            'listing', :listing_id, now() + interval '24 hours'
                        )
                        """
                    ),
                    {
                        "organization_id": organization_id,
                        "operation": self._operation(listing_id),
                        "idempotency_key": idempotency_key,
                        "request_hash": request_hash,
                        "listing_id": listing_id,
                    },
                )
                await self._session.execute(
                    text(
                        """
                        insert into public.ai_jobs (
                            id, listing_version_id, job_type, status, idempotency_key,
                            provider, model_name, prompt_version, attempt_count,
                            provider_status, started_at
                        ) values (
                            :id, :listing_version_id, 'contract_generate', 'processing',
                            :job_key, :provider, :model_name, :prompt_version, 1,
                            'processing', now()
                        )
                        """
                    ),
                    {
                        "id": job_id,
                        "listing_version_id": row["current_version_id"],
                        "job_key": f"contract-generate:{job_id}",
                        "provider": provider,
                        "model_name": model_name,
                        "prompt_version": prompt_version,
                    },
                )
                await self._session.execute(
                    text("update public.listings set status = 'processing' where id = :id"),
                    {"id": listing_id},
                )
                await self._insert_audit(
                    listing_id,
                    actor_user_id,
                    "listing_generation_started",
                    row["current_version_id"],
                    {"job_id": str(job_id), "base_version_no": expected_version_no},
                )
            return ContractGenerationClaim(job_id=job_id, cached=None)
        except (
            ContractGenerationIdempotencyConflictError,
            ContractGenerationInProgressError,
            ContractGenerationNotFoundError,
            ContractGenerationStateConflictError,
            ContractGenerationVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise ContractGenerationRepositoryError from exc

    async def complete_generation(
        self,
        *,
        listing: ContractGenerationInputRecord,
        actor_user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
        request_hash: str,
        clauses: list[NewGeneratedClause],
        body: str,
        ai_summary: str,
        result_metadata: dict[str, Any],
    ) -> ContractGenerationRecord:
        version_id = uuid4()
        version_no = listing.current_version_no + 1
        clause_records = [
            GeneratedClauseRecord(uuid4(), order, clause.clause_key, clause.title, clause.body)
            for order, clause in enumerate(clauses, start=1)
        ]
        record = ContractGenerationRecord(
            listing_id=listing.id,
            job_id=job_id,
            listing_version_id=version_id,
            version_no=version_no,
            status="ready",
            clauses=clause_records,
        )
        response_body = self._response_from_record(record)
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                locked = await self._session.execute(
                    text(
                        """
                        select status::text as status, current_version_id
                        from public.listings
                        where id = :listing_id and seller_organization_id = :organization_id
                        for update
                        """
                    ),
                    {
                        "listing_id": listing.id,
                        "organization_id": listing.seller_organization_id,
                    },
                )
                row = locked.mappings().one_or_none()
                if row is None:
                    raise ContractGenerationNotFoundError
                if row["current_version_id"] != listing.current_version_id:
                    raise ContractGenerationVersionConflictError
                if row["status"] != "processing":
                    raise ContractGenerationStateConflictError
                await self._session.execute(
                    text(
                        """
                        insert into public.listing_versions (
                            id, listing_id, version_no, title, body, content_sha256,
                            structured_data, created_by
                        ) values (
                            :id, :listing_id, :version_no, :title, :body,
                            encode(digest(:body, 'sha256'), 'hex'),
                            cast(:structured_data as jsonb), :actor_user_id
                        )
                        """
                    ),
                    {
                        "id": version_id,
                        "listing_id": listing.id,
                        "version_no": version_no,
                        "title": listing.title,
                        "body": body,
                        "structured_data": json.dumps(listing.terms, default=str),
                        "actor_user_id": actor_user_id,
                    },
                )
                for clause in clause_records:
                    await self._session.execute(
                        text(
                            """
                            insert into public.listing_clauses (
                                id, listing_version_id, clause_order, clause_key, title, body
                            ) values (
                                :id, :version_id, :clause_order, :clause_key, :title, :body
                            )
                            """
                        ),
                        {
                            "id": clause.id,
                            "version_id": version_id,
                            "clause_order": clause.clause_order,
                            "clause_key": clause.clause_key,
                            "title": clause.title,
                            "body": clause.body,
                        },
                    )
                await self._session.execute(
                    text(
                        """
                        update public.listings
                        set current_version_id = :version_id, status = 'ready',
                            ai_summary = :ai_summary
                        where id = :listing_id
                        """
                    ),
                    {
                        "version_id": version_id,
                        "listing_id": listing.id,
                        "ai_summary": ai_summary,
                    },
                )
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs
                        set status = 'succeeded', provider_status = 'succeeded',
                            completed_at = now(),
                            result_metadata = cast(:metadata as jsonb)
                        where id = :job_id and status = 'processing'
                        """
                    ),
                    {
                        "job_id": job_id,
                        "metadata": json.dumps(
                            {
                                **result_metadata,
                                "result_resource_type": "listing_version",
                                "result_resource_id": str(version_id),
                            }
                        ),
                    },
                )
                updated = await self._session.execute(
                    text(
                        """
                        update public.idempotency_records
                        set response_status = 200, response_body = cast(:response_body as jsonb),
                            resource_type = 'listing_version', resource_id = :version_id
                        where organization_id = :organization_id
                          and operation = :operation and idempotency_key = :idempotency_key
                          and request_hash = :request_hash and response_body is null
                        returning id
                        """
                    ),
                    {
                        "response_body": json.dumps(response_body),
                        "version_id": version_id,
                        "organization_id": listing.seller_organization_id,
                        "operation": self._operation(listing.id),
                        "idempotency_key": idempotency_key,
                        "request_hash": request_hash,
                    },
                )
                if updated.scalar_one_or_none() is None:
                    raise ContractGenerationIdempotencyConflictError
                await self._insert_audit(
                    listing.id,
                    actor_user_id,
                    "listing_generated",
                    version_id,
                    {"job_id": str(job_id), "version_no": version_no},
                )
            return record
        except (
            ContractGenerationIdempotencyConflictError,
            ContractGenerationNotFoundError,
            ContractGenerationStateConflictError,
            ContractGenerationVersionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise ContractGenerationRepositoryError from exc

    async def fail_generation(
        self,
        *,
        listing: ContractGenerationInputRecord,
        job_id: UUID,
        idempotency_key: str,
        failure_code: str,
    ) -> None:
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
                await self._session.execute(
                    text(
                        """
                        update public.listings set status = 'draft'
                        where id = :listing_id and status = 'processing'
                          and current_version_id = :version_id
                        """
                    ),
                    {"listing_id": listing.id, "version_id": listing.current_version_id},
                )
                await self._session.execute(
                    text(
                        """
                        delete from public.idempotency_records
                        where organization_id = :organization_id
                          and operation = :operation and idempotency_key = :idempotency_key
                          and response_body is null
                        """
                    ),
                    {
                        "organization_id": listing.seller_organization_id,
                        "operation": self._operation(listing.id),
                        "idempotency_key": idempotency_key,
                    },
                )
        except SQLAlchemyError as exc:
            raise ContractGenerationRepositoryError from exc

    async def _idempotency_record(
        self, organization_id: UUID, listing_id: UUID, key: str, *, lock: bool
    ):
        await self._session.execute(
            text(
                """
                delete from public.idempotency_records
                where organization_id = :organization_id and operation = :operation
                  and idempotency_key = :key and expires_at <= now()
                """
            ),
            {
                "organization_id": organization_id,
                "operation": self._operation(listing_id),
                "key": key,
            },
        )
        suffix = " for update" if lock else ""
        result = await self._session.execute(
            text(
                """
                select request_hash, response_body
                from public.idempotency_records
                where organization_id = :organization_id and operation = :operation
                  and idempotency_key = :key
                """
                + suffix
            ),
            {
                "organization_id": organization_id,
                "operation": self._operation(listing_id),
                "key": key,
            },
        )
        return result.mappings().one_or_none()

    @classmethod
    def _operation(cls, listing_id: UUID) -> str:
        return f"{cls._OPERATION}:{listing_id}"

    @staticmethod
    def _response_from_record(record: ContractGenerationRecord) -> dict[str, Any]:
        return {
            "listing_id": str(record.listing_id),
            "job_id": str(record.job_id),
            "listing_version_id": str(record.listing_version_id),
            "version_no": record.version_no,
            "status": record.status,
            "clauses": [
                {
                    "id": str(clause.id),
                    "clause_order": clause.clause_order,
                    "clause_key": clause.clause_key,
                    "title": clause.title,
                    "body": clause.body,
                }
                for clause in record.clauses
            ],
        }

    @staticmethod
    def _record_from_response(response: dict[str, Any]) -> ContractGenerationRecord:
        return ContractGenerationRecord(
            listing_id=UUID(response["listing_id"]),
            job_id=UUID(response["job_id"]),
            listing_version_id=UUID(response["listing_version_id"]),
            version_no=int(response["version_no"]),
            status=str(response["status"]),
            clauses=[
                GeneratedClauseRecord(
                    id=UUID(clause["id"]),
                    clause_order=int(clause["clause_order"]),
                    clause_key=str(clause["clause_key"]),
                    title=str(clause["title"]),
                    body=str(clause["body"]),
                )
                for clause in response["clauses"]
            ],
        )

    async def _insert_audit(
        self,
        listing_id: UUID,
        actor_user_id: UUID,
        event_type: str,
        target_id: UUID,
        event_data: dict[str, Any],
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.audit_events (
                    listing_id, actor_user_id, actor_role, event_type,
                    target_type, target_id, event_data
                ) values (
                    :listing_id, :actor_user_id, 'seller', :event_type,
                    'listing_version', :target_id, cast(:event_data as jsonb)
                )
                """
            ),
            {
                "listing_id": listing_id,
                "actor_user_id": actor_user_id,
                "event_type": event_type,
                "target_id": target_id,
                "event_data": json.dumps(event_data),
            },
        )


def json_safe_terms(terms: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, date) else value for key, value in terms.items()
    }
