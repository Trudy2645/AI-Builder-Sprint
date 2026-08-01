from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
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
    suggested_text_sha256: str | None
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


@dataclass(frozen=True, slots=True)
class FindingActionContext:
    finding_id: UUID
    finding_status: str
    target_type: Literal["listing_version", "contract_version"]
    resource_id: UUID
    version_id: UUID
    version_no: int
    current_version_id: UUID
    current_version_no: int
    resource_status: str
    seller_organization_id: UUID
    buyer_user_id: UUID | None
    viewer_role: str
    clause_id: UUID | None
    title: str
    suggested_text: str | None
    suggested_text_sha256: str | None


@dataclass(frozen=True, slots=True)
class FindingReviewJob:
    job_id: UUID
    viewer_role: Literal["buyer", "seller"]


@dataclass(frozen=True, slots=True)
class FindingApplyRecord:
    finding_id: UUID
    target_type: Literal["listing_version", "contract_version"]
    resource_id: UUID
    previous_version_id: UUID
    version_id: UUID
    version_no: int
    jobs: list[FindingReviewJob]
    replayed: bool


@dataclass(frozen=True, slots=True)
class FindingDismissRecord:
    finding_id: UUID
    replayed: bool


class ContractReviewRepositoryError(Exception):
    pass


class ContractReviewIdempotencyConflictError(Exception):
    pass


class FindingActionNotFoundError(Exception):
    pass


class FindingActionConflictError(Exception):
    pass


class FindingActionVersionConflictError(Exception):
    pass


class FindingSuggestionConflictError(Exception):
    pass


class RagEvidenceValidationError(Exception):
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

    async def get_finding_action_context(self, finding_id: UUID) -> FindingActionContext | None: ...

    async def apply_finding(
        self,
        *,
        finding_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        suggested_text_hash: str,
        edited_text: str | None,
        idempotency_key: str,
        request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> FindingApplyRecord: ...

    async def dismiss_finding(
        self,
        *,
        finding_id: UUID,
        actor_user_id: UUID,
        reason: str,
        idempotency_key: str,
        request_hash: str,
    ) -> FindingDismissRecord: ...


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
                    inserted = await self._session.execute(
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
                            ) returning id
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
                    finding_id = inserted.scalar_one()
                    evidence_snapshot = await self._persist_grounded_evidence(
                        analysis_run_id=analysis_run_id,
                        finding_id=finding_id,
                        target=target,
                        selected_evidence=selected_evidence,
                    )
                    if evidence_snapshot:
                        await self._session.execute(
                            text(
                                """
                                update public.ai_findings set evidence = cast(:evidence as jsonb)
                                where id = :finding_id
                                """
                            ),
                            {
                                "finding_id": finding_id,
                                "evidence": json.dumps(evidence_snapshot, ensure_ascii=False),
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

    async def _persist_grounded_evidence(
        self,
        *,
        analysis_run_id: UUID,
        finding_id: UUID,
        target: ContractReviewTargetRecord,
        selected_evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        effective_on = _effective_date(target.terms)
        activity_subtype = target.terms.get("activity_subtype")
        for rank, selected in enumerate(selected_evidence, start=1):
            metadata = selected.get("metadata") or {}
            try:
                document_version_id = UUID(str(metadata["document_version_id"]))
                page_start = int(metadata["page_start"])
                page_end = int(metadata.get("page_end") or page_start)
                content_sha256 = str(metadata["content_sha256"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RagEvidenceValidationError(
                    "evidence location metadata is incomplete"
                ) from exc
            if page_start < 1 or page_end < page_start:
                raise RagEvidenceValidationError("evidence page range is invalid")
            section_path = metadata.get("section_path")
            bbox = metadata.get("bbox")
            version = await self._session.execute(
                text(
                    """
                    select kv.id, kv.content_sha256, kd.title, kd.source_url,
                           kd.knowledge_base_id, kb.corpus_type::text
                    from public.knowledge_document_versions kv
                    join public.knowledge_documents kd on kd.id = kv.document_id
                    join public.knowledge_bases kb on kb.id = kd.knowledge_base_id
                    where kv.id = :version_id and kv.status = 'active'
                      and kv.upstage_file_id = :file_id
                      and kv.content_sha256 = :content_sha256
                      and kd.party_type = 'B2C_individual'
                      and :category = any(kd.contract_categories::text[])
                      and (kv.effective_from is null or kv.effective_from <= :effective_on)
                      and (kv.effective_to is null or kv.effective_to >= :effective_on)
                      and (
                          :activity_subtype is null or cardinality(kd.activity_subtypes) = 0
                          or :activity_subtype = any(kd.activity_subtypes)
                      )
                    """
                ),
                {
                    "version_id": document_version_id,
                    "file_id": selected.get("file_id"),
                    "content_sha256": content_sha256,
                    "category": target.category,
                    "effective_on": effective_on,
                    "activity_subtype": activity_subtype,
                },
            )
            version_row = version.mappings().one_or_none()
            if version_row is None:
                raise RagEvidenceValidationError("evidence is outside the active knowledge scope")
            if version_row["corpus_type"] not in {"official", "case_reference"}:
                raise RagEvidenceValidationError("template content cannot be legal evidence")
            run_id = uuid4()
            await self._session.execute(
                text(
                    """
                    insert into public.rag_retrieval_runs (
                        id, analysis_run_id, knowledge_base_id, query, filters,
                        knowledge_base_version, top_k, provider_request_id, result_count
                    ) values (
                        :id, :analysis_run_id, :base_id, :query, cast(:filters as jsonb),
                        :version, :top_k, :provider_request_id, 1
                    )
                    """
                ),
                {
                    "id": run_id,
                    "analysis_run_id": analysis_run_id,
                    "base_id": version_row["knowledge_base_id"],
                    "query": selected.get("query") or "grounded contract review",
                    "filters": json.dumps(selected.get("filters") or {}),
                    "version": content_sha256,
                    "top_k": int(selected.get("top_k") or 5),
                    "provider_request_id": selected.get("provider_request_id"),
                },
            )
            evidence_id = uuid4()
            excerpt = str(selected.get("excerpt") or "").strip()[:1000]
            if not excerpt:
                raise RagEvidenceValidationError("evidence excerpt is empty")
            await self._session.execute(
                text(
                    """
                    insert into public.rag_evidence (
                        id, retrieval_run_id, finding_id, document_version_id,
                        rank, score, page_start, page_end, section_path,
                        excerpt, bbox, chunk_id, content_sha256
                    ) values (
                        :id, :run_id, :finding_id, :version_id, :rank, :score,
                        :page_start, :page_end, :section_path, :excerpt,
                        cast(:bbox as jsonb), :chunk_id, :content_sha256
                    )
                    """
                ),
                {
                    "id": evidence_id,
                    "run_id": run_id,
                    "finding_id": finding_id,
                    "version_id": document_version_id,
                    "rank": rank,
                    "score": selected.get("score"),
                    "page_start": page_start,
                    "page_end": page_end,
                    "section_path": section_path,
                    "excerpt": excerpt,
                    "bbox": json.dumps(bbox) if bbox else None,
                    "chunk_id": selected.get("chunk_id"),
                    "content_sha256": content_sha256,
                },
            )
            snapshots.append(
                {
                    "id": str(evidence_id),
                    "label": f"[{rank}]",
                    "document_title": version_row["title"],
                    "source_kind": version_row["corpus_type"],
                    "page": page_start,
                    "section": section_path,
                    "excerpt": excerpt,
                }
            )
        return snapshots

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
                   suggested_text, suggested_text_sha256, grounding_status::text,
                   confidence::float,
                   source_location, evidence, disclaimer, is_public
            from public.ai_findings where analysis_run_id = :run_id
            order by created_at, id
            """,
            {"run_id": run_id},
        )
        findings = [StoredReviewFinding(**item) for item in finding_rows]
        return StoredReviewRun(**dict(row), findings=findings)

    async def get_finding_action_context(self, finding_id: UUID) -> FindingActionContext | None:
        row = await self._one(self._FINDING_ACTION_QUERY, {"finding_id": finding_id})
        return FindingActionContext(**dict(row)) if row else None

    async def apply_finding(
        self,
        *,
        finding_id: UUID,
        actor_user_id: UUID,
        base_version_no: int,
        suggested_text_hash: str,
        edited_text: str | None,
        idempotency_key: str,
        request_hash: str,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> FindingApplyRecord:
        operation = f"finding_apply:{finding_id}"
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                replay = await self._claim_action_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return self._apply_record(replay, replayed=True)

                context = await self._lock_finding(finding_id)
                if context.finding_status != "open" or not context.suggested_text:
                    raise FindingActionConflictError
                if context.resource_status not in {
                    "draft",
                    "ready",
                    "published",
                    "paused",
                    "seller_review",
                    "revision_requested",
                }:
                    raise FindingActionConflictError
                if (
                    context.version_id != context.current_version_id
                    or context.version_no != context.current_version_no
                    or context.version_no != base_version_no
                ):
                    raise FindingActionVersionConflictError
                if context.suggested_text_sha256 != suggested_text_hash.removeprefix("sha256:"):
                    raise FindingSuggestionConflictError

                applied_text = edited_text or context.suggested_text
                version_id, version_no = await self._create_safeguard_version(
                    context, actor_user_id, applied_text
                )
                updated = await self._session.execute(
                    text(
                        """
                        update public.ai_findings
                        set status = 'applied', applied_version_id = :version_id,
                            dismissed_reason = null, updated_at = now()
                        where id = :finding_id and status = 'open'
                        returning id
                        """
                    ),
                    {"finding_id": finding_id, "version_id": version_id},
                )
                if updated.scalar_one_or_none() is None:
                    raise FindingActionConflictError

                jobs = await self._queue_reanalysis_jobs(
                    context=context,
                    version_id=version_id,
                    provider=provider,
                    model_name=model_name,
                    prompt_version=prompt_version,
                )
                await self._insert_finding_audit(
                    context,
                    actor_user_id,
                    "ai_finding_applied",
                    {
                        "finding_id": str(finding_id),
                        "base_version_id": str(context.version_id),
                        "base_version_no": context.version_no,
                        "applied_version_id": str(version_id),
                        "applied_version_no": version_no,
                        "suggested_text_sha256": context.suggested_text_sha256,
                        "applied_text_sha256": hashlib.sha256(applied_text.encode()).hexdigest(),
                        "edited": edited_text is not None,
                    },
                )
                response = {
                    "finding_id": str(finding_id),
                    "target_type": context.target_type,
                    "resource_id": str(context.resource_id),
                    "previous_version_id": str(context.version_id),
                    "version_id": str(version_id),
                    "version_no": version_no,
                    "jobs": [
                        {"job_id": str(job.job_id), "viewer_role": job.viewer_role} for job in jobs
                    ],
                }
                await self._complete_action_idempotency(
                    actor_user_id,
                    operation,
                    idempotency_key,
                    response,
                    finding_id,
                )
            return self._apply_record(response, replayed=False)
        except (
            ContractReviewIdempotencyConflictError,
            FindingActionNotFoundError,
            FindingActionConflictError,
            FindingActionVersionConflictError,
            FindingSuggestionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    async def dismiss_finding(
        self,
        *,
        finding_id: UUID,
        actor_user_id: UUID,
        reason: str,
        idempotency_key: str,
        request_hash: str,
    ) -> FindingDismissRecord:
        operation = f"finding_dismiss:{finding_id}"
        try:
            if self._session.in_transaction():
                await self._session.rollback()
            async with self._session.begin():
                replay = await self._claim_action_idempotency(
                    actor_user_id, operation, idempotency_key, request_hash
                )
                if replay is not None:
                    return FindingDismissRecord(
                        finding_id=UUID(replay["finding_id"]), replayed=True
                    )
                context = await self._lock_finding(finding_id)
                if context.finding_status != "open":
                    raise FindingActionConflictError
                updated = await self._session.execute(
                    text(
                        """
                        update public.ai_findings
                        set status = 'dismissed', dismissed_reason = :reason,
                            applied_version_id = null, updated_at = now()
                        where id = :finding_id and status = 'open'
                        returning id
                        """
                    ),
                    {"finding_id": finding_id, "reason": reason},
                )
                if updated.scalar_one_or_none() is None:
                    raise FindingActionConflictError
                await self._insert_finding_audit(
                    context,
                    actor_user_id,
                    "ai_finding_dismissed",
                    {"finding_id": str(finding_id), "reason": reason},
                )
                response = {"finding_id": str(finding_id)}
                await self._complete_action_idempotency(
                    actor_user_id,
                    operation,
                    idempotency_key,
                    response,
                    finding_id,
                )
            return FindingDismissRecord(finding_id=finding_id, replayed=False)
        except (
            ContractReviewIdempotencyConflictError,
            FindingActionNotFoundError,
            FindingActionConflictError,
        ):
            raise
        except SQLAlchemyError as exc:
            raise ContractReviewRepositoryError from exc

    _FINDING_ACTION_QUERY = """
        select f.id as finding_id, f.status::text as finding_status,
               case when ar.listing_version_id is not null
                    then 'listing_version' else 'contract_version' end as target_type,
               coalesce(l.id, c.id) as resource_id,
               coalesce(lv.id, cv.id) as version_id,
               coalesce(lv.version_no, cv.version_no) as version_no,
               coalesce(l.current_version_id, c.current_version_id) as current_version_id,
               coalesce(current_lv.version_no, current_cv.version_no) as current_version_no,
               coalesce(l.status::text, c.status::text) as resource_status,
               coalesce(l.seller_organization_id, c.seller_organization_id)
                   as seller_organization_id,
               c.buyer_user_id, ar.viewer_role::text,
               coalesce(f.listing_clause_id, f.contract_clause_id) as clause_id,
               f.title, f.suggested_text, f.suggested_text_sha256
        from public.ai_findings f
        join public.ai_analysis_runs ar on ar.id = f.analysis_run_id
        left join public.listing_versions lv on lv.id = ar.listing_version_id
        left join public.listings l on l.id = lv.listing_id
        left join public.listing_versions current_lv on current_lv.id = l.current_version_id
        left join public.contract_versions cv on cv.id = ar.contract_version_id
        left join public.contracts c on c.id = cv.contract_id
        left join public.contract_versions current_cv on current_cv.id = c.current_version_id
        where f.id = :finding_id
    """

    async def _lock_finding(self, finding_id: UUID) -> FindingActionContext:
        result = await self._session.execute(
            text(self._FINDING_ACTION_QUERY + " for update of f"),
            {"finding_id": finding_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise FindingActionNotFoundError
        context = FindingActionContext(**dict(row))
        resource_table = "listings" if context.target_type == "listing_version" else "contracts"
        await self._session.execute(
            text(
                f"select id from public.{resource_table} where id = :resource_id for update"  # noqa: S608
            ),
            {"resource_id": context.resource_id},
        )
        refreshed = await self._session.execute(
            text(self._FINDING_ACTION_QUERY), {"finding_id": finding_id}
        )
        return FindingActionContext(**dict(refreshed.mappings().one()))

    async def _create_safeguard_version(
        self, context: FindingActionContext, actor_user_id: UUID, applied_text: str
    ) -> tuple[UUID, int]:
        version_id = uuid4()
        version_no = context.version_no + 1
        prefix = "listing" if context.target_type == "listing_version" else "contract"
        version_table = f"{prefix}_versions"
        clause_table = f"{prefix}_clauses"
        version_column = f"{prefix}_version_id"
        resource_table = "listings" if prefix == "listing" else "contracts"
        clause_rows = await self._session.execute(
            text(
                f"""
                select * from public.{clause_table}
                where {version_column} = :version_id order by clause_order
                """  # noqa: S608
            ),
            {"version_id": context.version_id},
        )
        clauses = [dict(row) for row in clause_rows.mappings().all()]
        matched = False
        for clause in clauses:
            if clause["id"] == context.clause_id:
                clause["body"] = applied_text
                matched = True
        if context.clause_id is not None and not matched:
            raise FindingActionVersionConflictError
        if context.clause_id is None:
            clauses.append(
                {
                    "clause_order": len(clauses) + 1,
                    "clause_key": None,
                    "title": context.title,
                    "body": applied_text,
                    "source_page": None,
                    "source_bbox": None,
                    "source_listing_clause_id": None,
                }
            )
        body = "\n\n".join(f"{item['title']}\n{item['body']}" for item in clauses)
        if prefix == "listing":
            insert = f"""
                insert into public.{version_table} (
                    id, listing_id, version_no, title, body, content_sha256,
                    source_document_id, structured_data, created_by
                )
                select :id, listing_id, :version_no, title, :body,
                       encode(digest(:body, 'sha256'), 'hex'), source_document_id,
                       structured_data, :actor_user_id
                from public.{version_table}
                where id = :base_version_id
                returning id
            """
        else:
            insert = f"""
                insert into public.{version_table} (
                    id, contract_id, version_no, title, body, content_sha256,
                    source_listing_version_id, created_from_revision_request_id,
                    structured_data, created_by
                )
                select :id, contract_id, :version_no, title, :body,
                       encode(digest(:body, 'sha256'), 'hex'), source_listing_version_id,
                       null, structured_data, :actor_user_id
                from public.{version_table}
                where id = :base_version_id
                returning id
            """
        created = await self._session.execute(
            text(insert),
            {
                "id": version_id,
                "version_no": version_no,
                "body": body,
                "actor_user_id": actor_user_id,
                "base_version_id": context.version_id,
            },
        )
        if created.scalar_one_or_none() is None:
            raise FindingActionVersionConflictError
        for order, clause in enumerate(clauses, start=1):
            columns = ""
            values = ""
            params = {
                "version_id": version_id,
                "clause_order": order,
                "clause_key": clause.get("clause_key"),
                "title": clause["title"],
                "body": clause["body"],
                "source_page": clause.get("source_page"),
                "source_bbox": json.dumps(clause.get("source_bbox")),
            }
            if prefix == "contract":
                columns = "source_listing_clause_id, "
                values = ":source_listing_clause_id, "
                params["source_listing_clause_id"] = clause.get("source_listing_clause_id")
            await self._session.execute(
                text(
                    f"""
                    insert into public.{clause_table} (
                        {version_column}, {columns}clause_order, clause_key, title, body,
                        source_page, source_bbox
                    ) values (
                        :version_id, {values}:clause_order, :clause_key, :title, :body,
                        :source_page, cast(:source_bbox as jsonb)
                    )
                    """  # noqa: S608
                ),
                params,
            )
        current = await self._session.execute(
            text(
                f"""
                update public.{resource_table}
                set current_version_id = :version_id, updated_at = now()
                where id = :resource_id and current_version_id = :base_version_id
                returning id
                """  # noqa: S608
            ),
            {
                "version_id": version_id,
                "resource_id": context.resource_id,
                "base_version_id": context.version_id,
            },
        )
        if current.scalar_one_or_none() is None:
            raise FindingActionVersionConflictError
        return version_id, version_no

    async def _queue_reanalysis_jobs(
        self,
        *,
        context: FindingActionContext,
        version_id: UUID,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> list[FindingReviewJob]:
        jobs: list[FindingReviewJob] = []
        for viewer_role in ("seller", "buyer"):
            job_id = uuid4()
            scoped_key = hashlib.sha256(
                f"finding_reanalysis:{context.finding_id}:{version_id}:{viewer_role}".encode()
            ).hexdigest()
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
                {
                    "id": job_id,
                    "listing_version_id": (
                        version_id if context.target_type == "listing_version" else None
                    ),
                    "contract_version_id": (
                        version_id if context.target_type == "contract_version" else None
                    ),
                    "idempotency_key": scoped_key,
                    "provider": provider,
                    "model_name": model_name,
                    "prompt_version": prompt_version,
                    "metadata": json.dumps(
                        {
                            "viewer_role": viewer_role,
                            "trigger": "finding_applied",
                            "finding_id": str(context.finding_id),
                        }
                    ),
                },
            )
            jobs.append(FindingReviewJob(job_id=job_id, viewer_role=viewer_role))  # type: ignore[arg-type]
        return jobs

    async def _insert_finding_audit(
        self,
        context: FindingActionContext,
        actor_user_id: UUID,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.audit_events (
                    contract_id, listing_id, actor_user_id, actor_role,
                    event_type, target_type, target_id, event_data
                ) values (
                    :contract_id, :listing_id, :actor_user_id, 'seller',
                    :event_type, 'ai_finding', :finding_id, cast(:event_data as jsonb)
                )
                """
            ),
            {
                "contract_id": (
                    context.resource_id if context.target_type == "contract_version" else None
                ),
                "listing_id": (
                    context.resource_id if context.target_type == "listing_version" else None
                ),
                "actor_user_id": actor_user_id,
                "event_type": event_type,
                "finding_id": context.finding_id,
                "event_data": json.dumps(event_data),
            },
        )

    async def _claim_action_idempotency(
        self,
        actor_user_id: UUID,
        operation: str,
        key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        await self._session.execute(
            text(
                """
                delete from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key and expires_at <= now()
                """
            ),
            {"actor_user_id": actor_user_id, "operation": operation, "key": key},
        )
        inserted = await self._session.execute(
            text(
                """
                insert into public.idempotency_records (
                    actor_user_id, operation, idempotency_key, request_hash, expires_at
                ) values (
                    :actor_user_id, :operation, :key, :request_hash,
                    now() + interval '24 hours'
                )
                on conflict (actor_user_id, operation, idempotency_key)
                    where actor_user_id is not null do nothing
                returning id
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "operation": operation,
                "key": key,
                "request_hash": request_hash,
            },
        )
        if inserted.scalar_one_or_none() is not None:
            return None
        existing = await self._session.execute(
            text(
                """
                select request_hash, response_body from public.idempotency_records
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key for update
                """
            ),
            {"actor_user_id": actor_user_id, "operation": operation, "key": key},
        )
        row = existing.mappings().one()
        if row["request_hash"] != request_hash or row["response_body"] is None:
            raise ContractReviewIdempotencyConflictError
        return dict(row["response_body"])

    async def _complete_action_idempotency(
        self,
        actor_user_id: UUID,
        operation: str,
        key: str,
        response: dict[str, Any],
        resource_id: UUID,
    ) -> None:
        await self._session.execute(
            text(
                """
                update public.idempotency_records
                set response_status = :response_status,
                    response_body = cast(:response as jsonb),
                    resource_type = 'ai_finding', resource_id = :resource_id
                where actor_user_id = :actor_user_id and operation = :operation
                  and idempotency_key = :key
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "operation": operation,
                "key": key,
                "response": json.dumps(response),
                "resource_id": resource_id,
                "response_status": 202 if operation.startswith("finding_apply:") else 200,
            },
        )

    @staticmethod
    def _apply_record(response: dict[str, Any], *, replayed: bool) -> FindingApplyRecord:
        return FindingApplyRecord(
            finding_id=UUID(response["finding_id"]),
            target_type=response["target_type"],
            resource_id=UUID(response["resource_id"]),
            previous_version_id=UUID(response["previous_version_id"]),
            version_id=UUID(response["version_id"]),
            version_no=int(response["version_no"]),
            jobs=[
                FindingReviewJob(job_id=UUID(item["job_id"]), viewer_role=item["viewer_role"])
                for item in response["jobs"]
            ],
            replayed=replayed,
        )

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


def _effective_date(terms: dict[str, Any]) -> date:
    value = terms.get("service_start_date") or terms.get("start_date")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()
