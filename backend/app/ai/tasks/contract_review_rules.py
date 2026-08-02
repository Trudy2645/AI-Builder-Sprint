from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReviewClauseInput:
    id: UUID
    clause_order: int
    clause_key: str | None
    title: str
    body: str
    source_location: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RuleFinding:
    clause_id: UUID | None
    category: str
    severity: str
    importance: str
    title: str
    explanation: str
    suggested_text: str | None
    evidence_query: str | None
    source_location: dict[str, Any]


def review_contract_rules(
    *, category: str, terms: dict[str, Any], clauses: list[ReviewClauseInput]
) -> list[RuleFinding]:
    """Run deterministic omissions and ordering checks before the Agent."""
    findings: list[RuleFinding] = []
    clause_by_key = {clause.clause_key: clause for clause in clauses if clause.clause_key}

    def missing(
        *,
        field_names: tuple[str, ...],
        clause_keys: tuple[str, ...],
        finding_category: str,
        title: str,
        explanation: str,
        suggested_text: str,
        query: str,
        severity: str = "medium",
    ) -> None:
        if any(_present(terms.get(name)) for name in field_names):
            return
        clause = next((clause_by_key.get(key) for key in clause_keys if key in clause_by_key), None)
        if clause is None and any(_contains_any(item.body, field_names) for item in clauses):
            return
        findings.append(
            RuleFinding(
                clause_id=clause.id if clause else None,
                category=finding_category,
                severity=severity,
                importance="high",
                title=title,
                explanation=explanation,
                suggested_text=suggested_text,
                evidence_query=query,
                source_location=clause.source_location if clause else {},
            )
        )

    missing(
        field_names=("cancellation_policy", "cancellation"),
        clause_keys=("cancellation", "cancellation_refund"),
        finding_category="cancellation",
        title="취소 기한과 수수료 기준 확인이 필요합니다",
        explanation=(
            "취소 기한 또는 수수료 기준이 빠져 있어 당사자 간 해석 차이가 생길 수 있습니다."
        ),
        suggested_text="취소 가능 기한과 시점별 수수료를 당사자가 확인해 구체적으로 기재하세요.",
        query=f"{category} 개인 관광 계약 취소 환불 기준",
    )
    missing(
        field_names=("no_show_policy", "no_show"),
        clause_keys=("no_show",),
        finding_category="no_show",
        title="노쇼 처리 기준 확인이 필요합니다",
        explanation="사전 통지 없이 이용하지 않은 경우의 비용 기준이 명시되지 않았습니다.",
        suggested_text="노쇼의 정의와 부과 금액 또는 비율을 당사자가 확인해 기재하세요.",
        query=f"{category} 관광 계약 노쇼 기준",
    )
    missing(
        field_names=("settlement_policy", "settlement"),
        clause_keys=("settlement", "payment"),
        finding_category="settlement",
        title="정산 시점과 지급 주체 확인이 필요합니다",
        explanation=(
            "정산 마감일, 지급일 또는 지급 주체가 명확하지 않아 지급 지연 분쟁이 생길 수 있습니다."
        ),
        suggested_text="정산 기준일, 지급기한과 지급 주체를 구체적으로 기재하세요.",
        query=f"{category} 관광 공급 계약 정산 지급 기준",
    )

    start = _as_date(terms.get("service_start_date") or terms.get("start_date"))
    end = _as_date(terms.get("service_end_date") or terms.get("end_date"))
    if start and end and start > end:
        findings.append(
            RuleFinding(
                clause_id=None,
                category="service_period",
                severity="high",
                importance="high",
                title="서비스 기간의 날짜 순서를 확인해야 합니다",
                explanation=f"시작일 {start.isoformat()}이 종료일 {end.isoformat()}보다 늦습니다.",
                suggested_text=None,
                evidence_query=None,
                source_location={},
            )
        )

    minimum = _as_number(terms.get("minimum_quantity") or terms.get("minimum_people"))
    maximum = _as_number(terms.get("maximum_quantity") or terms.get("maximum_people"))
    if minimum is not None and maximum is not None and minimum > maximum:
        findings.append(
            RuleFinding(
                clause_id=None,
                category="quantity_range",
                severity="high",
                importance="high",
                title="최소 수량과 최대 수량을 확인해야 합니다",
                explanation=f"최소값 {minimum:g}이 최대값 {maximum:g}보다 큽니다.",
                suggested_text=None,
                evidence_query=None,
                source_location={},
            )
        )

    category_requirements = {
        "vehicle_rental": (
            ("safety_policy", "liability_policy"),
            "vehicle_liability",
            "보험과 사고 책임 범위 확인이 필요합니다",
            "보험 종류, 보장 범위, 자기부담금과 사고 처리 기준을 확인해 기재하세요.",
        ),
        "activity": (
            ("safety_policy",),
            "activity_safety",
            "안전·기상 취소 기준 확인이 필요합니다",
            "안전 의무, 이용 제한과 기상 취소 기준을 확인해 기재하세요.",
        ),
        "tour": (
            ("liability_policy",),
            "tour_supplier_liability",
            "구성 상품의 책임 주체 확인이 필요합니다",
            "각 구성 상품의 공급·취소 책임 주체를 확인해 기재하세요.",
        ),
    }
    requirement = category_requirements.get(category)
    if requirement and not any(_present(terms.get(name)) for name in requirement[0]):
        findings.append(
            RuleFinding(
                clause_id=None,
                category=requirement[1],
                severity="medium",
                importance="high",
                title=requirement[2],
                explanation=requirement[2].replace(
                    "확인이 필요합니다", "이 빠져 분쟁 가능성이 있습니다"
                ),
                suggested_text=requirement[3],
                evidence_query=f"{category} 개인 관광 계약 {requirement[1]} 기준",
                source_location={},
            )
        )
    return findings


def _present(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _contains_any(body: str, fields: tuple[str, ...]) -> bool:
    normalized = body.lower()
    aliases = {
        "cancellation_policy": ("취소", "cancellation"),
        "cancellation": ("취소", "cancellation"),
        "no_show_policy": ("노쇼", "no-show", "no show"),
        "no_show": ("노쇼", "no-show", "no show"),
        "settlement_policy": ("정산", "지급", "settlement"),
        "settlement": ("정산", "지급", "settlement"),
    }
    return any(alias in normalized for field in fields for alias in aliases.get(field, ()))
