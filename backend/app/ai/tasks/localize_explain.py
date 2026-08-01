from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.ai.prompts.v1.localize_explain import LOCALIZE_EXPLAIN_SYSTEM_PROMPT
from app.ai.providers.base import LanguageModelProvider
from app.ai.schemas import LanguageModelRequest, LocalizedPublicContent

_TRANSLATABLE_TERMS = (
    "supply_quantity_description",
    "cancellation_policy",
    "no_show_policy",
    "refund_policy",
    "settlement_policy",
    "safety_policy",
    "compensation_policy",
    "liability_policy",
    "termination_policy",
    "special_terms",
    "price_display_basis",
    "contract_availability_note",
)
_FACT_FIELDS = (
    "service_start_date",
    "service_end_date",
    "supply_quantity",
    "quantity_unit",
    "minimum_quantity",
    "maximum_quantity",
    "people_per_unit",
    "base_price_amount_minor",
    "currency",
    "price_unit",
    "minimum_people",
    "maximum_people",
)


class LocalizationPreservationError(ValueError):
    pass


def build_public_localization_source(
    listing: dict[str, Any], clauses: list[dict[str, Any]], findings: list[dict[str, Any]]
) -> dict[str, Any]:
    source = {
        "source_locale": listing["language"],
        "listing_version_id": str(listing["current_version_id"]),
        "listing_version_hash": listing["current_version_hash"],
        "title": listing["title"],
        "public_headline": listing.get("public_headline"),
        "ai_summary": listing.get("ai_summary"),
        "seller_name": listing["seller_name"],
        "district": listing["district"],
        "category": listing["category"],
        "terms": {key: listing.get(key) for key in _TRANSLATABLE_TERMS},
        "preserved_facts": {key: listing.get(key) for key in _FACT_FIELDS},
        "preserved_names": list(
            dict.fromkeys(value for value in (listing["seller_name"], listing["district"]) if value)
        ),
        "clauses": [
            {
                "clause_id": str(item["id"]),
                "clause_no": item["clause_order"],
                "title": item["title"],
                "body": item["body"],
            }
            for item in clauses
        ],
        "findings": [
            {
                "finding_id": str(item["id"]),
                "clause_id": str(item["clause_id"]) if item.get("clause_id") else None,
                "severity": item["severity"],
                "explanation": item["explanation"],
                "suggested_text": item.get("suggested_text"),
                "disclaimer": item["disclaimer"],
                "evidence_numbers": item.get("evidence_numbers", []),
            }
            for item in findings
        ],
        "disclaimer": "법률 자문이 아닌 계약 검토 보조 의견입니다.",
    }
    return _json_safe(source)


def localization_source_hash(source: dict[str, Any]) -> str:
    raw = json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


async def localize_public_content(
    language_model: LanguageModelProvider,
    *,
    source: dict[str, Any],
    target_locale: str,
    prompt_version: str,
) -> LocalizedPublicContent:
    return await language_model.generate_structured(
        LanguageModelRequest(
            task_type="localize_explain",
            system_prompt=LOCALIZE_EXPLAIN_SYSTEM_PROMPT,
            input_data={"source": source, "target_locale": target_locale},
            prompt_version=prompt_version,
            reasoning_effort="low",
        ),
        LocalizedPublicContent,
    )


def validate_localized_content(
    source: dict[str, Any], result: LocalizedPublicContent, target_locale: str
) -> None:
    if result.locale != target_locale:
        raise LocalizationPreservationError("locale mismatch")
    if result.preserved_facts != source["preserved_facts"]:
        raise LocalizationPreservationError("preserved facts changed")
    if result.preserved_names != source["preserved_names"]:
        raise LocalizationPreservationError("proper names changed")
    if (source["public_headline"] is None) != (result.public_headline is None):
        raise LocalizationPreservationError("public headline presence changed")
    if set(result.terms) != set(source["terms"]):
        raise LocalizationPreservationError("term fields changed")
    if any(
        (source["terms"][key] is None) != (result.terms[key] is None) for key in source["terms"]
    ):
        raise LocalizationPreservationError("empty term presence changed")
    expected_clauses = [(item["clause_id"], item["clause_no"]) for item in source["clauses"]]
    actual_clauses = [(str(item.clause_id), item.clause_no) for item in result.clauses]
    if actual_clauses != expected_clauses:
        raise LocalizationPreservationError("clause references changed")
    expected_findings = [
        (
            item["finding_id"],
            item["clause_id"],
            item["severity"],
            item["evidence_numbers"],
        )
        for item in source["findings"]
    ]
    actual_findings = [
        (
            str(item.finding_id),
            str(item.clause_id) if item.clause_id else None,
            item.severity,
            item.evidence_numbers,
        )
        for item in result.findings
    ]
    if actual_findings != expected_findings:
        raise LocalizationPreservationError("finding or evidence references changed")
    source_tokens = _numeric_tokens(source)
    result_tokens = _numeric_tokens(result.model_dump(mode="json"))
    if source_tokens != result_tokens:
        raise LocalizationPreservationError("numeric, date, percentage, or reference changed")


def _numeric_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()

    def visit(item: Any, key: str | None = None) -> None:
        if key and (key.endswith("_id") or key in {"listing_version_hash"}):
            return
        if isinstance(item, dict):
            for child_key, child in item.items():
                visit(child, child_key)
        elif isinstance(item, list):
            for child in item:
                visit(child, key)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            tokens.add(str(item))
        elif isinstance(item, str):
            import re

            for token in re.findall(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?%?", item):
                tokens.add(token.replace(",", ""))

    visit(value)
    return tokens


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


__all__ = [
    "LocalizationPreservationError",
    "build_public_localization_source",
    "localization_source_hash",
    "localize_public_content",
    "validate_localized_content",
]
