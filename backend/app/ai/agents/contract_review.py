from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError

from app.ai.prompts.v1.contract_review import CONTRACT_REVIEW_SYSTEM_PROMPT
from app.ai.providers.base import LanguageModelProvider
from app.ai.schemas import (
    ContractReviewFindingCandidate,
    ContractReviewSubmission,
    ContractReviewToolBatch,
    LanguageModelRequest,
)
from app.ai.tasks.contract_review_rules import ReviewClauseInput, RuleFinding
from app.ai.tools.contract_review import (
    ContractReviewSearchLimitError,
    ContractReviewToolRejectedError,
    ContractReviewTools,
)

_DISCLAIMER = (
    "AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 "
    "계약의 법적 효력을 보장하지 않습니다."
)


class ContractReviewAgentError(Exception):
    pass


class ContractReviewAgentInvalidOutputError(ContractReviewAgentError):
    pass


@dataclass(frozen=True, slots=True)
class ContractReviewAgentResult:
    findings: list[ContractReviewFindingCandidate]
    iterations_used: int
    stop_reason: Literal["completed", "max_iterations", "insufficient_evidence", "provider_error"]
    tool_sequence: list[str]
    evidence: dict[str, dict[str, Any]]


class ContractReviewAgent:
    """A host-controlled single Agent with four tools and a hard search budget."""

    def __init__(
        self,
        language_model: LanguageModelProvider,
        tools: ContractReviewTools,
        *,
        model_name: str,
        prompt_version: str,
        max_search_iterations: int = 2,
    ) -> None:
        if not 1 <= max_search_iterations <= 2:
            raise ValueError("ContractReviewAgent search iterations must be between 1 and 2.")
        self._language_model = language_model
        self._tools = tools
        self._model_name = model_name
        self._prompt_version = prompt_version
        self._max_search_iterations = max_search_iterations

    async def run(
        self,
        *,
        target_type: Literal["listing_version", "contract_version"],
        target_id: UUID,
        viewer_role: Literal["buyer", "seller"],
        category: str,
        clauses: list[ReviewClauseInput],
        terms: dict[str, Any],
        rule_findings: list[RuleFinding],
    ) -> ContractReviewAgentResult:
        transcript: list[dict[str, Any]] = []
        inventory = [
            {
                "id": str(clause.id),
                "clause_order": clause.clause_order,
                "clause_key": clause.clause_key,
                "title": clause.title,
            }
            for clause in clauses
        ]
        base_input = {
            "target_type": target_type,
            "target_id": str(target_id),
            "viewer_role": viewer_role,
            "category": category,
            "clause_inventory": inventory,
            "structured_terms": terms,
            "rule_findings": [self._serialize_rule(item) for item in rule_findings],
            "available_tools": [
                "get_clause_context",
                "search_official_evidence",
                "search_approved_templates",
                "submit_review",
            ],
            "max_search_iterations": self._max_search_iterations,
        }

        # Four planning turns allow context lookup, two bounded searches, and submission.
        for _ in range(4):
            batch = await self._language_model.generate_structured(
                LanguageModelRequest(
                    task_type="contract_review",
                    system_prompt=CONTRACT_REVIEW_SYSTEM_PROMPT,
                    input_data={**base_input, "tool_transcript": transcript},
                    prompt_version=self._prompt_version,
                    reasoning_effort="medium",
                ),
                ContractReviewToolBatch,
            )
            submitted: ContractReviewSubmission | None = None
            for call in batch.tool_calls:
                if call.name == "submit_review":
                    if submitted is not None or self._tools.submit_count:
                        raise ContractReviewToolRejectedError(
                            "submit_review may be called only once"
                        )
                    try:
                        submitted = self._normalize_submission(call.arguments, clauses)
                    except (TypeError, ValueError, ValidationError) as exc:
                        raise ContractReviewAgentInvalidOutputError from exc
                    continue
                try:
                    result = await self._tools.execute(call.name, call.arguments)
                except ContractReviewSearchLimitError:
                    return self._fallback_result(rule_findings, "max_iterations")
                transcript.append({"tool": result.tool_name, "result": result.content})
            if submitted is not None:
                self._tools.mark_submitted()
                findings = self._validate_and_merge(
                    submitted.findings, rule_findings, clauses, viewer_role
                )
                reason = (
                    "insufficient_evidence"
                    if any(item.grounding_status == "insufficient_evidence" for item in findings)
                    else "completed"
                )
                return ContractReviewAgentResult(
                    findings=findings,
                    iterations_used=self._tools.searches_used,
                    stop_reason=reason,
                    tool_sequence=list(self._tools.tool_sequence),
                    evidence=dict(self._tools.evidence),
                )
        return self._fallback_result(rule_findings, "max_iterations")

    @staticmethod
    def _normalize_submission(
        arguments: dict[str, Any], clauses: list[ReviewClauseInput]
    ) -> ContractReviewSubmission:
        """Adapt common provider field names to the persisted review schema.

        The provider is asked for a tool envelope, but some compatible models
        still return a semantically equivalent review with fields such as
        ``finding``, ``notes``, ``risk_rating`` or ``search_query``. Normalize
        those aliases at this boundary so the domain layer remains strict.
        """
        raw_findings = arguments.get("findings")
        if not isinstance(raw_findings, list):
            raw_findings = next(
                (
                    arguments.get(key)
                    for key in ("results", "reviews", "risk_findings", "items")
                    if isinstance(arguments.get(key), list)
                ),
                [],
            )
        if not raw_findings and any(
            key in arguments for key in ("clause_id", "clause_key", "finding", "notes")
        ):
            raw_findings = [arguments]
        clause_by_id = {str(clause.id): clause for clause in clauses}
        clause_by_key = {clause.clause_key: clause for clause in clauses if clause.clause_key}
        findings: list[ContractReviewFindingCandidate] = []
        for raw in raw_findings:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            raw_clause_id = str(item.get("clause_id", "")).strip()
            clause_key = str(item.get("clause_key", "")).strip()
            clause = clause_by_id.get(raw_clause_id)
            if clause is None and clause_key:
                clause = clause_by_key.get(clause_key)
            if clause is None and raw_clause_id in clause_by_key:
                clause = clause_by_key[raw_clause_id]

            severity = ContractReviewAgent._severity(item)
            grounding = ContractReviewAgent._grounding(item)
            evidence_ids = item.get("evidence_ids")
            if not isinstance(evidence_ids, list):
                evidence_ids = []
            evidence_ids = [str(value) for value in evidence_ids if str(value).strip()]
            if grounding == "grounded" and not evidence_ids:
                grounding = "insufficient_evidence"
            if grounding != "grounded":
                evidence_ids = []

            suggested_text = item.get("suggested_text") or item.get("suggestion")
            if suggested_text is not None and not isinstance(suggested_text, str):
                suggested_text = str(suggested_text)
            try:
                findings.append(
                    ContractReviewFindingCandidate.model_validate(
                        {
                            "clause_id": clause.id if clause else None,
                            "category": str(
                                item.get("category")
                                or clause_key
                                or (clause.clause_key if clause else "contract_review")
                            ),
                            "severity": severity,
                            "importance": str(item.get("importance") or _importance_for(severity)),
                            "title": str(
                                item.get("title") or (clause.title if clause else "계약 조항 검토")
                            ),
                            "explanation": str(
                                item.get("explanation")
                                or item.get("notes")
                                or item.get("finding")
                                or item.get("body_excerpt")
                                or "계약 조항의 적용 범위와 조건을 확인할 필요가 있습니다."
                            ),
                            "suggested_text": suggested_text,
                            "grounding_status": grounding,
                            "confidence": item.get("confidence", 0.5),
                            "source_location": (
                                item.get("source_location")
                                if isinstance(item.get("source_location"), dict)
                                else {}
                            ),
                            "evidence_ids": evidence_ids,
                            "disclaimer": str(item.get("disclaimer") or _DISCLAIMER),
                            "is_public": bool(item.get("is_public", False)),
                        }
                    )
                )
            except (TypeError, ValueError, ValidationError):
                continue
        return ContractReviewSubmission(findings=findings)

    @staticmethod
    def _severity(item: dict[str, Any]) -> str:
        value = item.get("severity") or item.get("risk_level")
        if isinstance(value, str) and value in {"high", "medium", "low", "none"}:
            return value
        try:
            rating = int(item.get("risk_rating"))
        except (TypeError, ValueError):
            return "medium"
        if rating >= 4:
            return "high"
        if rating >= 2:
            return "medium"
        if rating == 1:
            return "low"
        return "none"

    @staticmethod
    def _grounding(item: dict[str, Any]) -> str:
        value = item.get("grounding_status")
        if value == "grounded" and item.get("evidence_ids"):
            return "grounded"
        if value == "not_required":
            return "not_required"
        return "insufficient_evidence"

    def _validate_and_merge(
        self,
        agent_findings: list[ContractReviewFindingCandidate],
        rules: list[RuleFinding],
        clauses: list[ReviewClauseInput],
        viewer_role: str,
    ) -> list[ContractReviewFindingCandidate]:
        clause_ids = {clause.id for clause in clauses}
        merged: dict[tuple[UUID | None, str], ContractReviewFindingCandidate] = {}
        for candidate in agent_findings:
            if candidate.clause_id is not None and candidate.clause_id not in clause_ids:
                raise ContractReviewAgentInvalidOutputError
            if any(item not in self._tools.evidence for item in candidate.evidence_ids):
                raise ContractReviewAgentInvalidOutputError
            if candidate.grounding_status == "grounded" and any(
                self._tools.evidence[item]["source_type"] not in {"official", "case_reference"}
                for item in candidate.evidence_ids
            ):
                raise ContractReviewAgentInvalidOutputError
            data = candidate.model_dump()
            data["is_public"] = viewer_role == "buyer" and candidate.is_public
            merged[(candidate.clause_id, candidate.category)] = (
                ContractReviewFindingCandidate.model_validate(data)
            )
        for rule in rules:
            key = (rule.clause_id, rule.category)
            existing = merged.get(key)
            grounding = "not_required" if rule.evidence_query is None else "insufficient_evidence"
            data = {
                "clause_id": rule.clause_id,
                "category": rule.category,
                "severity": rule.severity,
                "importance": rule.importance,
                "title": rule.title,
                "explanation": rule.explanation,
                "suggested_text": rule.suggested_text,
                "grounding_status": existing.grounding_status if existing else grounding,
                "confidence": existing.confidence if existing else 1.0,
                "source_location": rule.source_location,
                "evidence_ids": existing.evidence_ids if existing else [],
                "disclaimer": _DISCLAIMER,
                "is_public": viewer_role == "buyer" and bool(existing and existing.is_public),
            }
            merged[key] = ContractReviewFindingCandidate.model_validate(data)
        return list(merged.values())

    def _fallback_result(
        self,
        rules: list[RuleFinding],
        stop_reason: Literal["max_iterations", "insufficient_evidence"],
    ) -> ContractReviewAgentResult:
        self._tools.mark_submitted()
        findings = [
            ContractReviewFindingCandidate(
                clause_id=item.clause_id,
                category=item.category,
                severity=item.severity,  # type: ignore[arg-type]
                importance=item.importance,  # type: ignore[arg-type]
                title=item.title,
                explanation=item.explanation,
                suggested_text=item.suggested_text,
                grounding_status=(
                    "not_required" if item.evidence_query is None else "insufficient_evidence"
                ),
                confidence=1.0,
                source_location=item.source_location,
                disclaimer=_DISCLAIMER,
                is_public=False,
            )
            for item in rules
        ]
        return ContractReviewAgentResult(
            findings=findings,
            iterations_used=self._tools.searches_used,
            stop_reason=stop_reason,
            tool_sequence=list(self._tools.tool_sequence),
            evidence=dict(self._tools.evidence),
        )

    @staticmethod
    def _serialize_rule(item: RuleFinding) -> dict[str, Any]:
        return {
            "clause_id": str(item.clause_id) if item.clause_id else None,
            "category": item.category,
            "severity": item.severity,
            "importance": item.importance,
            "title": item.title,
            "explanation": item.explanation,
            "suggested_text": item.suggested_text,
            "evidence_query": item.evidence_query,
            "source_location": item.source_location,
        }


def _importance_for(severity: str) -> str:
    return "high" if severity == "high" else "medium"
