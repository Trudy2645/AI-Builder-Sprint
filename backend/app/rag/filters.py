from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any


def build_retrieval_filter(
    *,
    corpus: str,
    category: str,
    effective_on: date,
    activity_subtype: str | None = None,
) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [
        _comparison("eq", "corpus", corpus),
        _comparison("eq", "status", "active"),
        _comparison("eq", "party_type", "B2C_individual"),
        {
            "type": "or",
            "filters": [
                _comparison("eq", "category_common", True),
                _comparison("eq", f"category_{category}", True),
            ],
        },
        _comparison("lte", "effective_from_epoch", _epoch(effective_on)),
        _comparison("gte", "effective_to_epoch", _epoch(effective_on)),
    ]
    if category == "activity" and activity_subtype:
        filters.append(
            {
                "type": "or",
                "filters": [
                    _comparison("eq", "activity_subtype", "common"),
                    _comparison("eq", "activity_subtype", activity_subtype),
                ],
            }
        )
    return {"type": "and", "filters": filters}


def metadata_matches_scope(
    metadata: dict[str, Any],
    *,
    corpus: str,
    category: str,
    effective_on: date,
    activity_subtype: str | None = None,
) -> bool:
    epoch = _epoch(effective_on)
    return bool(
        metadata.get("corpus") == corpus
        and metadata.get("status") == "active"
        and metadata.get("party_type") == "B2C_individual"
        and (
            metadata.get("category_common") is True or metadata.get(f"category_{category}") is True
        )
        and int(metadata.get("effective_from_epoch", epoch + 1)) <= epoch
        and int(metadata.get("effective_to_epoch", epoch - 1)) >= epoch
        and (
            category != "activity"
            or not activity_subtype
            or metadata.get("activity_subtype") in {"common", activity_subtype}
        )
    )


def _comparison(operator: str, key: str, value: str | int | bool) -> dict[str, Any]:
    return {"type": operator, "key": key, "value": value}


def _epoch(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())


__all__ = ["build_retrieval_filter", "metadata_matches_scope"]
