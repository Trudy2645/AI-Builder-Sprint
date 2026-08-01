from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import ContractReviewFindingCandidate
from app.ai.tasks.contract_review_rules import ReviewClauseInput


@dataclass(frozen=True, slots=True)
class ContractReviewTargetRecord:
    target_type: Literal["listing_version", "contract_version"]
    resource_id: UUID
    version_id: UUID
    version_no: int
    category: str
    seller_organization_id: UUID
    buyer_user_id: UUID | None
    terms: dict[str, Any]
    clauses: list[ReviewClauseInput]


@dataclass(frozen=True, slots=True)
class ReviewJobClaim:
    job_id: UUID
    status: str
    should_schedule: bool


@dataclass(frozen=True, slots=True)
class StoredReviewFinding:
    id: UUID
    clause_id: UUID | None
    category: str
    severity: str
    importance: str
    title: str
    explanation: str
    suggested_text: str | None
    grounding_status: str
    confidence: float | None
    source_location: dict[str, Any]
    evidence: list[dict[str, Any]]
    disclaimer: str
    is_public: bool


@dataclass(frozen=True, slots=True)
class StoredReviewRun:
    id: UUID
    job_id: UUID | None
    target_type: str
    target_id: UUID
    resource_id: UUID
    viewer_role: str
    status: str
    model_name: str
    prompt_version: str
    execution_mode: str
    agent_name: str | None
    max_iterations: int
    iterations_used: int
    stop_reason: str | None
    findings: list[StoredReviewFinding]


class ContractReviewRepositoryError(Exception):
    pass


class ContractReviewIdempotencyConflictError(Exception):
    pass


class ContractReviewRepository(Protocol):
    async def get_listing_target(
        self, listing_id: UUID, version_id: UUID
    ) -> ContractReviewTargetRecord | None: ...

    async def get_contract_target(
        self, contract_id: UUID, version_id: UUID
    ) -> ContractReviewTargetRecord | None: ...

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool: ...

    async def claim_review(
        self,
        *,
        target: ContractReviewTargetRecord,
        actor_user_id: UUID,
        viewer_role: str,
        idempotency_key: str,
        request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> ReviewJobClaim: ...

    async def mark_processing(
        self,
        *,
        job_id: UUID,
        target: ContractReviewTargetRecord,
        viewer_role: str,
        model_name: str,
        prompt_version: str,
        input_sha256: str,
        max_iterations: int,
    ) -> UUID: ...

    async def complete_review(
        self,
        *,
        job_id: UUID,
        analysis_run_id: UUID,
        target: ContractReviewTargetRecord,
        findings: list[ContractReviewFindingCandidate],
        evidence: dict[str, dict[str, Any]],
        iterations_used: int,
        stop_reason: str,
        execution_metadata: dict[str, Any],
    ) -> None: ...

    async def fail_review(
        self, *, job_id: UUID, analysis_run_id: UUID | None, failure_code: str
    ) -> None: ...

    async def get_run(self, run_id: UUID) -> StoredReviewRun | None: ...


class SqlAlchemyContractReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_listing_target(
        self, listing_id: UUID, version_id: UUID
    ) -> ContractReviewTargetRecord | None:
        query = """
            select l.id as resource_id, lv.id as version_id, lv.version_no,
                   l.category::text as category, l.seller_organization_id,
                   null::uuid as buyer_user_id, to_jsonb(lt) as terms
            from public.listings l
            join public.listing_versions lv on lv.listing_id = l.id
            join public.listing_terms lt on lt.listing_id = l.id
            where l.id = :resource_id and lv.id = :version_id
        """
        row = await self._one(query, {"resource_id": listing_id, "version_id": version_id})
        if row is None:
            return None
        clauses = await self._clauses("listing", version_id)
        return self._target("listing_version", row, clauses)

    async def get_contract_target(
        self, contract_id: UUID, version_id: UUID
    ) -> ContractReviewTargetRecord | None:
        query = """
            select c.id as resource_id, cv.id as version_id, cv.version_no,
                   l.category::text as category, c.seller_organization_id,
                   c.buyer_user_id,
                   coalesce(cv.structured_data -> 'contract_terms', cv.structured_data) as terms
            from public.contracts c
            join public.contract_versions cv on cv.contract_id = c.id
            left join public.listings l on l.id = c.listing_id
            where c.id = :resource_id and cv.id = :version_id
        """
        row = await self._one(query, {"resource_id": contract_id, "version_id": version_id})
        if row is None:
            return None
        values = dict(row)
        values["category"] = values.get("category") or "tour"
        clauses = await self._clauses("contract", version_id)
        return self._target("contract_version", values, clauses)

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        row = await self._one(
            """
            select 1 from public.organization_members
            where user_id = :user_id and organization_id = :organization_id
            """,
            {"user_id": user_id, "organization_id": organization_id},
        )
        return row is not None

    async def claim_review(
        self,
        *,
        target: ContractReviewTargetRecord,
        actor_user_id: UUID,
        viewer_role: str,
        idempotency_key: str,
        request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> ReviewJobClaim:
        scoped_key = hashlib.sha256(
            f"contract_review:{actor_user_id}:{target.version_id}:{viewer_role}:{idempotency_key}".encode()
        ).hexdigest()
        params = {
            "id": uuid4(),
            "listing_version_id": (
                target.version_id if target.target_type == "listing_version" else None
            ),
            "contract_version_id": (
                target.version_id if target.target_type == "contract_version" else None
            ),
            "idempotency_key": scoped_key,
            "provider": provider,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "metadata": json.dumps({"request_hash": request_hash, "viewer_role": viewer_role}),
        }
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                existing = await self._session.execute(
                    text(
                        """
                        select id, status::text, result_metadata
                        from public.ai_jobs where idempotency_key = :idempotency_key
                        for update
                        """
                    ),
                    {"idempotency_key": scoped_key},
                )
                row = existing.mappings().one_or_none()
                if row:
                    if (row["result_metadata"] or {}).get("request_hash") != request_hash:
                        raise ContractReviewIdempotencyConflictError
                    return ReviewJobClaim(row["id"], row["status"], False)
                await self._session.execute(
                    text(
                        """
                        insert into public.ai_jobs (
                            id, listing_version_id, contract_version_id, job_type, status,
                            idempotency_key, provider, model_name, prompt_version, result_metadata
                        ) values (
                            :id, :listing_version_id, :contract_version_id, 'risk_analysis',
                            'queued', :idempotency_key, :provider, :model_name,
                            :prompt_version, cast(:metadata as jsonb)
                        )
                        """
                    ),
                    params,
                )
            return ReviewJobClaim(params["id"], "queued", True)
        except ContractReviewIdempotencyConflictError:
            raise
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    async def mark_processing(
        self,
        *,
        job_id: UUID,
        target: ContractReviewTargetRecord,
        viewer_role: str,
        model_name: str,
        prompt_version: str,
        input_sha256: str,
        max_iterations: int,
    ) -> UUID:
        run_id = uuid4()
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs set status = 'processing', started_at = now(),
                            attempt_count = attempt_count + 1, provider_status = 'processing'
                        where id = :job_id and status = 'queued'
                        """
                    ),
                    {"job_id": job_id},
                )
                await self._session.execute(
                    text(
                        """
                        insert into public.ai_analysis_runs (
                            id, ai_job_id, listing_version_id, contract_version_id,
                            viewer_role, analysis_type, model_name, prompt_version,
                            input_sha256, status, execution_mode, agent_name,
                            max_iterations, iterations_used, execution_metadata
                        ) values (
                            :id, :job_id, :listing_version_id, :contract_version_id,
                            cast(:viewer_role as public.party_role), 'risk', :model_name,
                            :prompt_version, :input_sha256, 'processing', 'single_agent',
                            'contract_review', :max_iterations, 0, '{}'::jsonb
                        )
                        """
                    ),
                    {
                        "id": run_id,
                        "job_id": job_id,
                        "listing_version_id": (
                            target.version_id if target.target_type == "listing_version" else None
                        ),
                        "contract_version_id": (
                            target.version_id if target.target_type == "contract_version" else None
                        ),
                        "viewer_role": viewer_role,
                        "model_name": model_name,
                        "prompt_version": prompt_version,
                        "input_sha256": input_sha256,
                        "max_iterations": max_iterations,
                    },
                )
            return run_id
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    async def complete_review(
        self,
        *,
        job_id: UUID,
        analysis_run_id: UUID,
        target: ContractReviewTargetRecord,
        findings: list[ContractReviewFindingCandidate],
        evidence: dict[str, dict[str, Any]],
        iterations_used: int,
        stop_reason: str,
        execution_metadata: dict[str, Any],
    ) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                for finding in findings:
                    suggested_hash = (
                        hashlib.sha256(finding.suggested_text.encode()).hexdigest()
                        if finding.suggested_text
                        else None
                    )
                    selected_evidence = [evidence[item] for item in finding.evidence_ids]
                    await self._session.execute(
                        text(
                            """
                            insert into public.ai_findings (
                                analysis_run_id, listing_clause_id, contract_clause_id,
                                category, severity, importance, title, explanation,
                                suggested_text, suggested_text_sha256, grounding_status,
                                confidence, source_location, evidence, disclaimer, is_public
                            ) values (
                                :analysis_run_id, :listing_clause_id, :contract_clause_id,
                                :category, cast(:severity as public.finding_severity),
                                cast(:importance as public.finding_importance), :title,
                                :explanation, :suggested_text, :suggested_text_sha256,
                                cast(:grounding_status as public.grounding_status), :confidence,
                                cast(:source_location as jsonb), cast(:evidence as jsonb),
                                :disclaimer, :is_public
                            )
                            """
                        ),
                        {
                            "analysis_run_id": analysis_run_id,
                            "listing_clause_id": (
                                finding.clause_id
                                if target.target_type == "listing_version"
                                else None
                            ),
                            "contract_clause_id": (
                                finding.clause_id
                                if target.target_type == "contract_version"
                                else None
                            ),
                            "category": finding.category,
                            "severity": finding.severity,
                            "importance": finding.importance,
                            "title": finding.title,
                            "explanation": finding.explanation,
                            "suggested_text": finding.suggested_text,
                            "suggested_text_sha256": suggested_hash,
                            "grounding_status": finding.grounding_status,
                            "confidence": finding.confidence,
                            "source_location": json.dumps(finding.source_location),
                            "evidence": json.dumps(selected_evidence),
                            "disclaimer": finding.disclaimer,
                            "is_public": finding.is_public,
                        },
                    )
                await self._session.execute(
                    text(
                        """
                        update public.ai_analysis_runs
                        set status = 'succeeded', completed_at = now(),
                            iterations_used = :iterations_used, stop_reason = :stop_reason,
                            execution_metadata = cast(:metadata as jsonb)
                        where id = :run_id and status = 'processing'
                        """
                    ),
                    {
                        "run_id": analysis_run_id,
                        "iterations_used": iterations_used,
                        "stop_reason": stop_reason,
                        "metadata": json.dumps(execution_metadata),
                    },
                )
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs
                        set status = 'succeeded', provider_status = 'succeeded',
                            completed_at = now(),
                            result_metadata = result_metadata || cast(:metadata as jsonb)
                        where id = :job_id and status = 'processing'
                        """
                    ),
                    {
                        "job_id": job_id,
                        "metadata": json.dumps(
                            {
                                "result_resource_type": "ai_analysis_run",
                                "result_resource_id": str(analysis_run_id),
                                "finding_count": len(findings),
                            }
                        ),
                    },
                )
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    async def fail_review(
        self, *, job_id: UUID, analysis_run_id: UUID | None, failure_code: str
    ) -> None:
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                if analysis_run_id:
                    await self._session.execute(
                        text(
                            """
                            update public.ai_analysis_runs
                            set status = 'failed', completed_at = now(),
                                stop_reason = 'provider_error'
                            where id = :run_id and status = 'processing'
                            """
                        ),
                        {"run_id": analysis_run_id},
                    )
                await self._session.execute(
                    text(
                        """
                        update public.ai_jobs set status = 'failed', provider_status = 'failed',
                            failure_code = :failure_code, failure_message = null,
                            completed_at = now()
                        where id = :job_id and status in ('queued', 'processing')
                        """
                    ),
                    {"job_id": job_id, "failure_code": failure_code},
                )
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    async def get_run(self, run_id: UUID) -> StoredReviewRun | None:
        row = await self._one(
            """
            select ar.id, ar.ai_job_id as job_id,
                   case when ar.listing_version_id is not null
                        then 'listing_version' else 'contract_version' end as target_type,
                   coalesce(ar.listing_version_id, ar.contract_version_id) as target_id,
                   coalesce(l.id, c.id) as resource_id,
                   ar.viewer_role::text, ar.status::text, ar.model_name, ar.prompt_version,
                   ar.execution_mode, ar.agent_name, ar.max_iterations,
                   ar.iterations_used, ar.stop_reason
            from public.ai_analysis_runs ar
            left join public.listing_versions lv on lv.id = ar.listing_version_id
            left join public.listings l on l.id = lv.listing_id
            left join public.contract_versions cv on cv.id = ar.contract_version_id
            left join public.contracts c on c.id = cv.contract_id
            where ar.id = :run_id
            """,
            {"run_id": run_id},
        )
        if row is None:
            return None
        finding_rows = await self._all(
            """
            select id, coalesce(listing_clause_id, contract_clause_id) as clause_id,
                   category, severity::text, importance::text, title, explanation,
                   suggested_text, grounding_status::text, confidence::float,
                   source_location, evidence, disclaimer, is_public
            from public.ai_findings where analysis_run_id = :run_id
            order by created_at, id
            """,
            {"run_id": run_id},
        )
        findings = [StoredReviewFinding(**item) for item in finding_rows]
        return StoredReviewRun(**dict(row), findings=findings)

    async def _clauses(self, target: str, version_id: UUID) -> list[ReviewClauseInput]:
        table = "listing_clauses" if target == "listing" else "contract_clauses"
        column = "listing_version_id" if target == "listing" else "contract_version_id"
        rows = await self._all(
            f"""
            select id, clause_order, clause_key, title, body, source_page, source_bbox
            from public.{table} where {column} = :version_id order by clause_order
            """,  # noqa: S608
            {"version_id": version_id},
        )
        return [
            ReviewClauseInput(
                id=row["id"],
                clause_order=row["clause_order"],
                clause_key=row["clause_key"],
                title=row["title"],
                body=row["body"],
                source_location={
                    key: value
                    for key, value in {
                        "page": row["source_page"],
                        "bbox": row["source_bbox"],
                    }.items()
                    if value is not None
                },
            )
            for row in rows
        ]

    @staticmethod
    def _target(
        target_type: Literal["listing_version", "contract_version"],
        row: Any,
        clauses: list[ReviewClauseInput],
    ) -> ContractReviewTargetRecord:
        values = dict(row)
        terms = dict(values.pop("terms") or {})
        for field in ("listing_id", "created_at", "updated_at"):
            terms.pop(field, None)
        return ContractReviewTargetRecord(
            target_type=target_type,
            terms=terms,
            clauses=clauses,
            **values,
        )

    async def _one(self, sql: str, params: dict[str, Any]):
        try:
            result = await self._session.execute(text(sql), params)
            return result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    async def _all(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            result = await self._session.execute(text(sql), params)
            return [dict(row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc
