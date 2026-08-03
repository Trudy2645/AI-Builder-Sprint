from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.ai.providers.base import FileSearchProvider
from app.ai.schemas import FileSearchRequest
from app.ai.tasks.contract_review_rules import ReviewClauseInput
from app.rag.filters import build_retrieval_filter, metadata_matches_scope
from app.rag.locator import EvidenceLocator


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
        case_vector_store_id: str | None = None,
        activity_subtype: str | None = None,
        evidence_locator: EvidenceLocator | None = None,
        minimum_evidence_score: float = 0.3,
        max_searches: int = 2,
        as_of: date | None = None,
    ) -> None:
        self._clauses = clauses
        self._clause_map = {str(clause.id): clause for clause in clauses}
        self._clause_key_map = {
            clause.clause_key: clause
            for clause in clauses
            if clause.clause_key
        }
        self._category = category
        self._provider = provider
        self._official_store = official_vector_store_id
        self._template_store = template_vector_store_id
        self._case_store = case_vector_store_id
        self._activity_subtype = activity_subtype
        self._evidence_locator = evidence_locator
        self._minimum_evidence_score = minimum_evidence_score
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
        # Models naturally select a clause by its stable semantic key (for
        # example ``cancellation_policy``), while the persisted finding schema
        # uses the clause UUID. Accept both representations at the tool
        # boundary and always return the canonical UUID in the context payload.
        clause_id = str(arguments.get("clause_id", "")).strip()
        clause_key = str(arguments.get("clause_key", "")).strip()
        try:
            adjacent_count = int(arguments.get("adjacent_count", 1))
        except (TypeError, ValueError) as exc:
            raise ContractReviewToolRejectedError("invalid adjacent_count") from exc
        if adjacent_count < 0 or adjacent_count > 2:
            raise ContractReviewToolRejectedError("adjacent_count must be between 0 and 2")
        clause = self._resolve_clause(clause_id=clause_id, clause_key=clause_key)
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
        query = str(arguments.get("query") or arguments.get("search_query") or "").strip()
        if not query:
            clause = self._resolve_clause(
                clause_id=str(arguments.get("clause_id", "")).strip(),
                clause_key=str(arguments.get("clause_key", "")).strip(),
            )
            if clause is not None:
                query = f"{self._category} {clause.title}".strip()
        if not query:
            raise ContractReviewToolRejectedError("search query is required")
        stores = (
            [
                (self._official_store, "official_evidence", "official"),
                (self._case_store, "case_reference", "case_reference"),
            ]
            if official
            else [(self._template_store, "approved_templates", "approved_template")]
        )
        stores = [(store, corpus, source) for store, corpus, source in stores if store]
        if not stores:
            return {"hits": [], "unavailable": True}
        try:
            requested_top_k = min(
                5,
                max(1, int(arguments.get("top_k", arguments.get("max_num_results", 5)))),
            )
        except (TypeError, ValueError):
            requested_top_k = 5
        candidates: list[dict[str, Any]] = []
        request_ids: list[str] = []
        for store_id, corpus, source_type in stores:
            filters = build_retrieval_filter(
                corpus=corpus,
                category=self._category,
                effective_on=self._as_of,
                activity_subtype=self._activity_subtype,
            )
            result = await self._provider.search_files(
                FileSearchRequest(
                    query=query,
                    vector_store_id=store_id,
                    filters=filters,
                    top_k=requested_top_k,
                )
            )
            if result.provider_request_id:
                request_ids.append(result.provider_request_id)
            for hit in result.hits:
                if not metadata_matches_scope(
                    hit.metadata,
                    corpus=corpus,
                    category=self._category,
                    effective_on=self._as_of,
                    activity_subtype=self._activity_subtype,
                ):
                    continue
                if official and (hit.score is None or hit.score < self._minimum_evidence_score):
                    continue
                if official and not _clickable_location(hit.metadata) and self._evidence_locator:
                    location = await self._evidence_locator.locate(hit.file_id, hit.excerpt)
                    if location:
                        hit.metadata.update(location)
                if official and not _clickable_location(hit.metadata):
                    continue
                candidates.append(
                    {
                        "source_type": source_type,
                        "corpus": corpus,
                        "file_id": hit.file_id,
                        "chunk_id": hit.chunk_id,
                        "score": hit.score,
                        "excerpt": hit.excerpt[:1000],
                        "metadata": hit.metadata,
                        "query": query,
                        "filters": filters,
                        "top_k": requested_top_k,
                        "provider_request_id": result.provider_request_id,
                    }
                )
        candidates.sort(key=lambda item: item["score"] or 0, reverse=True)
        hits: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None]] = set()
        for candidate in candidates:
            dedupe_key = (candidate["file_id"], candidate["chunk_id"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            evidence_id = f"{candidate['source_type']}:{self.searches_used}:{len(hits) + 1}"
            evidence = {"evidence_id": evidence_id, **candidate}
            self.evidence[evidence_id] = evidence
            hits.append(evidence)
            if len(hits) == requested_top_k:
                break
        return {"hits": hits, "provider_request_ids": request_ids}

    def _resolve_clause(
        self, *, clause_id: str = "", clause_key: str = ""
    ) -> ReviewClauseInput | None:
        clause = self._clause_map.get(clause_id)
        if clause is None and clause_key:
            clause = self._clause_key_map.get(clause_key)
        return clause

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


def _clickable_location(metadata: dict[str, Any]) -> bool:
    try:
        return int(metadata.get("page_start", 0)) > 0
    except (TypeError, ValueError):
        return False
