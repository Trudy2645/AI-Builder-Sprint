from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.ai.providers.base import FileSearchProvider
from app.ai.schemas import FileSearchRequest
from app.rag.filters import build_retrieval_filter, metadata_matches_scope


class GoldenQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    query: str = Field(min_length=1)
    category: str
    activity_subtype: str | None = None
    expected_source_keys: list[str] = Field(default_factory=list)
    expect_insufficient: bool = False


@dataclass(frozen=True, slots=True)
class RetrievalEvaluation:
    query_count: int
    recall_at_5: float
    cross_category_leakage_rate: float
    insufficient_evidence_accuracy: float


def load_golden_queries(path: Path) -> list[GoldenQuery]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [GoldenQuery.model_validate(item) for item in payload["queries"]]


async def evaluate_retrieval(
    provider: FileSearchProvider,
    *,
    vector_store_id: str,
    corpus: str,
    queries: list[GoldenQuery],
    effective_on: date,
) -> RetrievalEvaluation:
    recalled = leaked = insufficient_correct = insufficient_count = 0
    for golden in queries:
        filters = build_retrieval_filter(
            corpus=corpus,
            category=golden.category,
            effective_on=effective_on,
            activity_subtype=golden.activity_subtype,
        )
        result = await provider.search_files(
            FileSearchRequest(
                query=golden.query,
                vector_store_id=vector_store_id,
                filters=filters,
                top_k=5,
            )
        )
        scoped = [
            hit
            for hit in result.hits
            if metadata_matches_scope(
                hit.metadata,
                corpus=corpus,
                category=golden.category,
                effective_on=effective_on,
                activity_subtype=golden.activity_subtype,
            )
        ]
        source_keys = {str(hit.metadata.get("source_key")) for hit in scoped[:5]}
        if not golden.expected_source_keys or source_keys.intersection(golden.expected_source_keys):
            recalled += 1
        if len(scoped) != len(result.hits):
            leaked += 1
        if golden.expect_insufficient:
            insufficient_count += 1
            if not scoped:
                insufficient_correct += 1
    count = len(queries)
    return RetrievalEvaluation(
        query_count=count,
        recall_at_5=recalled / count if count else 0,
        cross_category_leakage_rate=leaked / count if count else 0,
        insufficient_evidence_accuracy=(
            insufficient_correct / insufficient_count if insufficient_count else 1
        ),
    )


__all__ = [
    "GoldenQuery",
    "RetrievalEvaluation",
    "evaluate_retrieval",
    "load_golden_queries",
]
