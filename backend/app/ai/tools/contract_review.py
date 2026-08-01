from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.ai.providers.base import FileSearchProvider
from app.ai.schemas import FileSearchRequest
from app.ai.tasks.contract_review_rules import ReviewClauseInput


class ContractReviewToolError(Exception):
    pass


class ContractReviewToolRejectedError(ContractReviewToolError):
    pass


class ContractReviewSearchLimitError(ContractReviewToolError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewToolResult:
    tool_name: str
    content: dict[str, Any]


class ContractReviewTools:
    def __init__(
        self,
        *,
        clauses: list[ReviewClauseInput],
        category: str,
        provider: FileSearchProvider,
        official_vector_store_id: str | None,
        template_vector_store_id: str | None,
        max_searches: int = 2,
        as_of: date | None = None,
    ) -> None:
        self._clauses = clauses
        self._clause_map = {str(clause.id): clause for clause in clauses}
        self._category = category
        self._provider = provider
        self._official_store = official_vector_store_id
        self._template_store = template_vector_store_id
        self._max_searches = max_searches
        self._as_of = as_of or date.today()
        self.searches_used = 0
        self.submit_count = 0
        self.tool_sequence: list[str] = []
        self.evidence: dict[str, dict[str, Any]] = {}

    async def execute(self, name: str, arguments: dict[str, Any]) -> ReviewToolResult:
        from app.ai.tools import CONTRACT_REVIEW_TOOL_ALLOWLIST

        if name not in CONTRACT_REVIEW_TOOL_ALLOWLIST:
            raise ContractReviewToolRejectedError(name)
        self.tool_sequence.append(name)
        if name == "get_clause_context":
            return ReviewToolResult(name, self._get_clause_context(arguments))
        if name == "search_official_evidence":
            return ReviewToolResult(name, await self._search(arguments, official=True))
        if name == "search_approved_templates":
            return ReviewToolResult(name, await self._search(arguments, official=False))
        raise ContractReviewToolRejectedError("submit_review is handled by the Agent executor")

    def mark_submitted(self) -> None:
        if self.submit_count:
            raise ContractReviewToolRejectedError("submit_review may be called only once")
        self.submit_count = 1
        self.tool_sequence.append("submit_review")

    def _get_clause_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        clause_id = str(arguments.get("clause_id", ""))
        try:
            adjacent_count = int(arguments.get("adjacent_count", 1))
        except (TypeError, ValueError) as exc:
            raise ContractReviewToolRejectedError("invalid adjacent_count") from exc
        if adjacent_count < 0 or adjacent_count > 2:
            raise ContractReviewToolRejectedError("adjacent_count must be between 0 and 2")
        clause = self._clause_map.get(clause_id)
        if clause is None:
            raise ContractReviewToolRejectedError("clause is outside the selected version")
        index = self._clauses.index(clause)
        nearby = self._clauses[max(0, index - adjacent_count) : index + adjacent_count + 1]
        return {
            "clause": self._serialize_clause(clause),
            "adjacent_clauses": [
                self._serialize_clause(item) for item in nearby if item.id != clause.id
            ],
        }

    async def _search(self, arguments: dict[str, Any], *, official: bool) -> dict[str, Any]:
        if self.searches_used >= self._max_searches:
            raise ContractReviewSearchLimitError
        self.searches_used += 1
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ContractReviewToolRejectedError("search query is required")
        store_id = self._official_store if official else self._template_store
        if not store_id:
            return {"hits": [], "unavailable": True}
        source_type = "official" if official else "approved_template"
        filters: dict[str, Any] = {
            "source_type": source_type,
            "contract_category": ["common", self._category],
            "party_type": "B2C_individual",
        }
        if official:
            filters["effective_on"] = self._as_of.isoformat()
        result = await self._provider.search_files(
            FileSearchRequest(
                query=query,
                vector_store_id=store_id,
                filters=filters,
                top_k=min(5, int(arguments.get("top_k", 5))),
            )
        )
        hits: list[dict[str, Any]] = []
        for index, hit in enumerate(result.hits, start=1):
            if hit.metadata.get("source_type") != source_type:
                continue
            if official and (hit.score is None or hit.score < 0.65):
                continue
            evidence_id = f"{source_type}:{self.searches_used}:{index}"
            evidence = {
                "evidence_id": evidence_id,
                "source_type": source_type,
                "file_id": hit.file_id,
                "chunk_id": hit.chunk_id,
                "score": hit.score,
                "excerpt": hit.excerpt[:1000],
                "metadata": hit.metadata,
            }
            self.evidence[evidence_id] = evidence
            hits.append(evidence)
        return {"hits": hits, "provider_request_id": result.provider_request_id}

    @staticmethod
    def _serialize_clause(clause: ReviewClauseInput) -> dict[str, Any]:
        return {
            "id": str(clause.id),
            "clause_order": clause.clause_order,
            "clause_key": clause.clause_key,
            "title": clause.title,
            "body": clause.body,
            "source_location": clause.source_location,
        }
