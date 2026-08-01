from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.tasks.localize_explain import (
    build_public_localization_source,
    localization_source_hash,
)
from app.api.dependencies import get_public_listing_repository
from app.repositories.listings import (
    ListingCursor,
    ListingRepositoryUnavailableError,
    ListingSearchFilters,
    PublicClauseRecord,
    PublicFindingRecord,
    PublicListingRecord,
    PublicListingVersionRecord,
    PublicLocalizationRecord,
    SqlAlchemyPublicListingRepository,
)
from app.schemas.listings import PublicListingSort

PUBLISHED_ID = UUID("20000000-0000-0000-0000-000000000001")
PAUSED_ID = UUID("20000000-0000-0000-0000-000000000002")
ACTIVITY_ID = UUID("20000000-0000-0000-0000-000000000003")
DRAFT_ID = UUID("20000000-0000-0000-0000-000000000004")
EXPIRED_ID = UUID("20000000-0000-0000-0000-000000000005")
VERSION_ID = UUID("30000000-0000-0000-0000-000000000001")
PAUSED_VERSION_ID = UUID("30000000-0000-0000-0000-000000000002")
ACTIVITY_VERSION_ID = UUID("30000000-0000-0000-0000-000000000003")
CLAUSE_ID = UUID("40000000-0000-0000-0000-000000000001")
TODAY = date(2026, 7, 30)


def listing(
    listing_id: UUID,
    *,
    title: str,
    seller_name: str,
    district: str,
    category: str,
    status: str,
    price: int,
    service_start: date,
    service_end: date,
    minimum_people: int,
    maximum_people: int,
    version_id: UUID,
    verified: bool = True,
) -> PublicListingRecord:
    return PublicListingRecord(
        id=listing_id,
        title=title,
        district=district,
        category=category,
        language="ko-KR",
        public_headline=f"{title} 한 줄 소개",
        ai_summary=f"{title} 공개 요약",
        status=status,
        seller_name=seller_name,
        verification_status="verified" if verified else "pending",
        rating_average=Decimal("4.80"),
        rating_count=24,
        service_start_date=service_start,
        service_end_date=service_end,
        supply_quantity=30,
        supply_quantity_description="주말 객실 최대 30실",
        quantity_unit="room" if category == "accommodation" else "person",
        minimum_quantity=10,
        maximum_quantity=30,
        people_per_unit=2 if category == "accommodation" else 1,
        base_price_amount_minor=price,
        currency="KRW",
        price_unit="room_night" if category == "accommodation" else "person",
        minimum_people=minimum_people,
        maximum_people=maximum_people,
        cancellation_policy="이용 7일 전까지 무료 취소",
        no_show_policy="당일 미이용은 환불 불가",
        refund_policy="취소 승인 후 원 결제수단으로 환불",
        settlement_policy="이용 완료 후 15일 이내 정산",
        safety_policy="시설 안전점검과 긴급 연락체계 제공",
        compensation_policy="셀러 귀책 시 대체 서비스 또는 환불",
        liability_policy="당사자별 고의 또는 과실 범위에서 책임",
        termination_policy="중대한 계약 위반 시 해지",
        special_terms="단체 인원은 14일 전 확정",
        price_display_basis="1인 기준 가격",
        contract_availability_note="잔여 수량 확인 후 계약 확정",
        attention_required_count=1 if version_id == VERSION_ID else 0,
        current_version_id=version_id,
        sort_value=Decimal(0),
        current_version_hash="a" * 64,
    )


class FakePublicListingRepository:
    def __init__(self) -> None:
        self.unavailable = False
        self.internal_seller_note = "never expose seller-only analysis"
        self.listings = [
            listing(
                PUBLISHED_ID,
                title="2026 부산 여름 객실 공급",
                seller_name="해운대 오션스테이",
                district="해운대구",
                category="accommodation",
                status="published",
                price=145_000,
                service_start=date(2026, 7, 1),
                service_end=date(2026, 8, 31),
                minimum_people=10,
                maximum_people=40,
                version_id=VERSION_ID,
            ),
            listing(
                PAUSED_ID,
                title="부산 원도심 버스 투어",
                seller_name="부산 링크 투어",
                district="중구",
                category="tour",
                status="paused",
                price=90_000,
                service_start=date(2026, 7, 1),
                service_end=date(2026, 9, 30),
                minimum_people=1,
                maximum_people=50,
                version_id=PAUSED_VERSION_ID,
            ),
            listing(
                ACTIVITY_ID,
                title="광안리 요트 체험",
                seller_name="부산 마린",
                district="수영구",
                category="activity",
                status="published",
                price=200_000,
                service_start=date(2026, 8, 1),
                service_end=date(2026, 12, 31),
                minimum_people=2,
                maximum_people=12,
                version_id=ACTIVITY_VERSION_ID,
                verified=False,
            ),
            listing(
                DRAFT_ID,
                title="내부 작성 중 공고",
                seller_name="비공개 셀러",
                district="해운대구",
                category="tour",
                status="draft",
                price=1,
                service_start=date(2026, 7, 1),
                service_end=date(2026, 12, 31),
                minimum_people=1,
                maximum_people=100,
                version_id=UUID("30000000-0000-0000-0000-000000000004"),
            ),
            listing(
                EXPIRED_ID,
                title="공급 기간 종료 공고",
                seller_name="지난 상품 셀러",
                district="해운대구",
                category="accommodation",
                status="published",
                price=50_000,
                service_start=date(2026, 6, 1),
                service_end=date(2026, 7, 29),
                minimum_people=1,
                maximum_people=100,
                version_id=UUID("30000000-0000-0000-0000-000000000005"),
            ),
        ]
        self.versions = {
            VERSION_ID: PublicListingVersionRecord(
                id=VERSION_ID,
                body="공개 계약 본문입니다.",
            ),
            PAUSED_VERSION_ID: PublicListingVersionRecord(
                id=PAUSED_VERSION_ID,
                body="일시 중지된 공고의 공개 계약 본문입니다.",
            ),
            ACTIVITY_VERSION_ID: PublicListingVersionRecord(
                id=ACTIVITY_VERSION_ID,
                body="요트 체험 계약 본문입니다.",
            ),
        }
        self.clauses = {
            VERSION_ID: [
                PublicClauseRecord(
                    id=CLAUSE_ID,
                    clause_key="cancellation",
                    title="제3조 취소 및 변경",
                    body="최종 수량과 취소 수수료는 협상 후 확정됩니다.",
                    clause_order=3,
                )
            ]
        }
        self.findings = {
            VERSION_ID: [
                PublicFindingRecord(
                    clause_id=CLAUSE_ID,
                    severity="medium",
                    explanation="취소 수수료 확정 시점이 모호합니다.",
                    suggested_text="무료 취소 기한을 명시해 보세요.",
                    disclaimer="법률 자문이 아닌 계약 검토 보조 의견입니다.",
                    id=UUID("50000000-0000-0000-0000-000000000001"),
                    evidence_numbers=[1],
                )
            ]
        }
        self.localizations: dict[tuple[UUID, str], PublicLocalizationRecord] = {}

    def _check_available(self) -> None:
        if self.unavailable:
            raise ListingRepositoryUnavailableError

    async def search_public_listings(
        self,
        filters: ListingSearchFilters,
        cursor: ListingCursor | None,
        limit: int,
    ) -> list[PublicListingRecord]:
        self._check_available()
        rows = [
            row
            for row in self.listings
            if row.status in {"published", "paused"}
            and (row.service_end_date is None or row.service_end_date >= TODAY)
        ]
        if filters.contract_available_only:
            rows = [row for row in rows if row.status == "published"]
        if filters.q:
            keyword = filters.q.lower()
            rows = [row for row in rows if keyword in f"{row.title} {row.seller_name}".lower()]
        if filters.districts:
            rows = [row for row in rows if row.district in filters.districts]
        if filters.people is not None:
            rows = [
                row
                for row in rows
                if (row.minimum_people is None or row.minimum_people <= filters.people)
                and (row.maximum_people is None or row.maximum_people >= filters.people)
            ]
        if filters.min_price is not None:
            rows = [
                row
                for row in rows
                if row.base_price_amount_minor is not None
                and row.base_price_amount_minor >= filters.min_price
            ]
        if filters.max_price is not None:
            rows = [
                row
                for row in rows
                if row.base_price_amount_minor is not None
                and row.base_price_amount_minor <= filters.max_price
            ]
        if filters.currency is not None:
            rows = [row for row in rows if row.currency == filters.currency]
        if filters.category is not None:
            rows = [row for row in rows if row.category == filters.category.value]
        if filters.start_date is not None:
            rows = [
                row
                for row in rows
                if row.service_start_date is None or row.service_start_date <= filters.start_date
            ]
        if filters.end_date is not None:
            rows = [
                row
                for row in rows
                if row.service_end_date is None or row.service_end_date >= filters.end_date
            ]

        values: dict[str, dict[UUID, Decimal | int | datetime]] = {
            "recommended": {
                PUBLISHED_ID: Decimal("1110020"),
                PAUSED_ID: Decimal("1010050"),
                ACTIVITY_ID: Decimal("110010"),
            },
            "popular": {
                PUBLISHED_ID: Decimal(20),
                PAUSED_ID: Decimal(50),
                ACTIVITY_ID: Decimal(10),
            },
            "latest": {
                PUBLISHED_ID: datetime(2026, 7, 20, tzinfo=UTC),
                PAUSED_ID: datetime(2026, 7, 15, tzinfo=UTC),
                ACTIVITY_ID: datetime(2026, 7, 25, tzinfo=UTC),
            },
            "price_asc": {
                PUBLISHED_ID: 145_000,
                PAUSED_ID: 90_000,
                ACTIVITY_ID: 200_000,
            },
            "price_desc": {
                PUBLISHED_ID: 145_000,
                PAUSED_ID: 90_000,
                ACTIVITY_ID: 200_000,
            },
        }
        sort_values = values[filters.sort.value]
        rows = [replace(row, sort_value=sort_values[row.id]) for row in rows]
        descending = filters.sort.value not in {"price_asc"}
        rows.sort(key=lambda row: (row.sort_value, row.id), reverse=descending)
        if cursor is not None:
            cursor_index = next(
                (index for index, row in enumerate(rows) if row.id == cursor.listing_id), None
            )
            rows = [] if cursor_index is None else rows[cursor_index + 1 :]
        return rows[:limit]

    async def get_public_listing(self, listing_id: UUID) -> PublicListingRecord | None:
        self._check_available()
        return next(
            (
                row
                for row in self.listings
                if row.id == listing_id
                and row.status in {"published", "paused"}
                and (row.service_end_date is None or row.service_end_date >= TODAY)
            ),
            None,
        )

    async def get_public_version(
        self, listing_id: UUID, version_id: UUID
    ) -> PublicListingVersionRecord | None:
        self._check_available()
        listing_row = await self.get_public_listing(listing_id)
        if listing_row is None or listing_row.current_version_id != version_id:
            return None
        return self.versions.get(version_id)

    async def list_public_clauses(self, version_id: UUID) -> list[PublicClauseRecord]:
        self._check_available()
        return self.clauses.get(version_id, [])

    async def list_public_findings(self, version_id: UUID) -> list[PublicFindingRecord]:
        self._check_available()
        return self.findings.get(version_id, [])

    async def get_localized_content(self, version_id: UUID, locale: str):
        self._check_available()
        return self.localizations.get((version_id, locale))

    async def list_localized_contents(self, version_ids: list[UUID], locale: str):
        self._check_available()
        return {
            version_id: content
            for version_id in version_ids
            if (content := self.localizations.get((version_id, locale))) is not None
        }


class EmptyMappingResult:
    def mappings(self) -> "EmptyMappingResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement: object | None = None

    async def execute(self, statement: object, params: dict[str, object]) -> EmptyMappingResult:
        self.statement = statement
        return EmptyMappingResult()


@pytest.fixture
def listing_repository() -> FakePublicListingRepository:
    return FakePublicListingRepository()


@pytest.fixture
def public_client(app: FastAPI, listing_repository: FakePublicListingRepository) -> TestClient:
    app.dependency_overrides[get_public_listing_repository] = lambda: listing_repository
    with TestClient(app) as client:
        yield client


def test_public_listings_are_available_without_authentication(
    public_client: TestClient,
) -> None:
    response = public_client.get("/api/v1/public/listings")

    assert response.status_code == 200
    payload = response.json()
    assert [row["id"] for row in payload["data"]] == [
        str(PUBLISHED_ID),
        str(PAUSED_ID),
        str(ACTIVITY_ID),
    ]
    assert payload["data"][0]["contract_available"] is True
    assert payload["data"][0]["attention_required_count"] == 1
    assert payload["data"][1]["status"] == "paused"
    assert payload["data"][1]["contract_available"] is False
    assert payload["meta"]["has_more"] is False


def test_contract_available_only_returns_published_listings(
    public_client: TestClient,
) -> None:
    response = public_client.get(
        "/api/v1/public/listings", params={"contract_available_only": "true"}
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [
        str(PUBLISHED_ID),
        str(ACTIVITY_ID),
    ]
    assert all(row["contract_available"] for row in response.json()["data"])


@pytest.mark.asyncio
async def test_contract_availability_is_filtered_in_database_before_pagination() -> None:
    session = CapturingSession()
    repository = SqlAlchemyPublicListingRepository(session)  # type: ignore[arg-type]
    filters = ListingSearchFilters(
        q=None,
        contract_available_only=True,
        districts=(),
        people=None,
        min_price=None,
        max_price=None,
        currency=None,
        category=None,
        start_date=None,
        end_date=None,
        sort=PublicListingSort.LATEST,
    )

    await repository.search_public_listings(filters, cursor=None, limit=21)

    sql = " ".join(str(session.statement).split())
    availability_position = sql.index("(l.status = 'published')")
    pagination_position = sql.index("order by sort_value")
    assert availability_position < pagination_position
    assert "ar.viewer_role = 'buyer'" in sql
    assert "ar.status = 'succeeded'" in sql
    assert "af.status in ('open', 'applied')" in sql


def test_availability_filter_combines_with_search_filters_and_sort(
    public_client: TestClient,
) -> None:
    response = public_client.get(
        "/api/v1/public/listings",
        params={
            "contract_available_only": "true",
            "category": "activity",
            "people": 4,
            "sort": "price_desc",
        },
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [str(ACTIVITY_ID)]


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"q": "오션스테이"}, [PUBLISHED_ID]),
        ({"district": ["해운대구", "중구"]}, [PUBLISHED_ID, PAUSED_ID]),
        ({"category": "activity"}, [ACTIVITY_ID]),
        ({"people": 30}, [PUBLISHED_ID, PAUSED_ID]),
        ({"min_price": 100_000, "max_price": 150_000, "currency": "KRW"}, [PUBLISHED_ID]),
        ({"start_date": "2026-08-15", "end_date": "2026-09-15"}, [PAUSED_ID, ACTIVITY_ID]),
    ],
)
def test_public_listing_filters(
    public_client: TestClient,
    params: dict[str, object],
    expected_ids: list[UUID],
) -> None:
    response = public_client.get("/api/v1/public/listings", params=params)

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [
        str(listing_id) for listing_id in expected_ids
    ]


@pytest.mark.parametrize(
    ("sort", "expected_ids"),
    [
        ("recommended", [PUBLISHED_ID, PAUSED_ID, ACTIVITY_ID]),
        ("popular", [PAUSED_ID, PUBLISHED_ID, ACTIVITY_ID]),
        ("latest", [ACTIVITY_ID, PUBLISHED_ID, PAUSED_ID]),
        ("price_asc", [PAUSED_ID, PUBLISHED_ID, ACTIVITY_ID]),
        ("price_desc", [ACTIVITY_ID, PUBLISHED_ID, PAUSED_ID]),
    ],
)
def test_public_listing_sort_orders_are_deterministic(
    public_client: TestClient, sort: str, expected_ids: list[UUID]
) -> None:
    response = public_client.get("/api/v1/public/listings", params={"sort": sort})

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [
        str(listing_id) for listing_id in expected_ids
    ]


def test_cursor_pagination_has_no_duplicates(public_client: TestClient) -> None:
    first = public_client.get("/api/v1/public/listings", params={"limit": 2})
    cursor = first.json()["meta"]["next_cursor"]
    second = public_client.get("/api/v1/public/listings", params={"limit": 2, "cursor": cursor})

    assert first.status_code == 200
    assert first.json()["meta"]["has_more"] is True
    assert [row["id"] for row in first.json()["data"]] == [
        str(PUBLISHED_ID),
        str(PAUSED_ID),
    ]
    assert second.status_code == 200
    assert [row["id"] for row in second.json()["data"]] == [str(ACTIVITY_ID)]
    assert second.json()["meta"]["next_cursor"] is None


def test_cursor_pagination_combines_with_availability_filter(
    public_client: TestClient,
) -> None:
    params = {"contract_available_only": "true", "limit": 1, "sort": "latest"}
    first = public_client.get("/api/v1/public/listings", params=params)
    second = public_client.get(
        "/api/v1/public/listings",
        params={**params, "cursor": first.json()["meta"]["next_cursor"]},
    )

    assert first.status_code == 200
    assert [row["id"] for row in first.json()["data"]] == [str(ACTIVITY_ID)]
    assert first.json()["meta"]["has_more"] is True
    assert second.status_code == 200
    assert [row["id"] for row in second.json()["data"]] == [str(PUBLISHED_ID)]
    assert second.json()["meta"]["has_more"] is False


def test_cursor_cannot_be_reused_with_another_sort(public_client: TestClient) -> None:
    first = public_client.get("/api/v1/public/listings", params={"limit": 1})

    response = public_client.get(
        "/api/v1/public/listings",
        params={"sort": "popular", "cursor": first.json()["meta"]["next_cursor"]},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_listing_detail_returns_public_terms_and_locale_fallback(
    public_client: TestClient,
) -> None:
    response = public_client.get(
        f"/api/v1/public/listings/{PUBLISHED_ID}", params={"locale": "en-US"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["supply_quantity"] == 30
    assert data["minimum_people"] == 10
    assert data["cancellation_policy"] == "이용 7일 전까지 무료 취소"
    assert data["refund_policy"] == "취소 승인 후 원 결제수단으로 환불"
    assert data["settlement_policy"] == "이용 완료 후 15일 이내 정산"
    assert data["safety_policy"] == "시설 안전점검과 긴급 연락체계 제공"
    assert data["compensation_policy"] == "셀러 귀책 시 대체 서비스 또는 환불"
    assert data["liability_policy"] == "당사자별 고의 또는 과실 범위에서 책임"
    assert data["price_display_basis"] == "1인 기준 가격"
    assert data["contract_availability_note"] == "잔여 수량 확인 후 계약 확정"
    assert data["attention_required_count"] == 1
    assert data["people_per_unit"] == 2
    assert data["no_show_policy"] == "당일 미이용은 환불 불가"
    assert data["termination_policy"] == "중대한 계약 위반 시 해지"
    assert data["special_terms"] == "단체 인원은 14일 전 확정"
    assert data["vat_included"] is None
    assert data["hero_image_url"] is None
    assert data["clauses"][0]["highlight"] == "warning"
    assert data["requested_locale"] == "en-US"
    assert data["content_locale"] == "ko-KR"
    assert data["fallback_locale"] == "ko-KR"


def test_listing_detail_returns_validated_localized_cache(
    public_client: TestClient,
    listing_repository: FakePublicListingRepository,
) -> None:
    record = next(item for item in listing_repository.listings if item.id == PUBLISHED_ID)
    clauses = listing_repository.clauses[VERSION_ID]
    findings = listing_repository.findings[VERSION_ID]
    source = build_public_localization_source(
        asdict(record),
        [asdict(item) for item in clauses],
        [asdict(item) for item in findings],
    )
    content = {
        "locale": "en-US",
        "title": "2026 Busan Summer Room Supply",
        "public_headline": "Oceanstay group accommodation in Haeundae",
        "summary": "Public summary for 2026 group accommodation.",
        "easy_explanation": "Plain-language guidance for this public contract.",
        "terms": source["terms"],
        "clauses": [
            {
                "clause_id": item["clause_id"],
                "clause_no": item["clause_no"],
                "title": item["title"],
                "body": item["body"],
                "easy_explanation": "Review the cancellation conditions.",
            }
            for item in source["clauses"]
        ],
        "findings": source["findings"],
        "preserved_facts": source["preserved_facts"],
        "preserved_names": source["preserved_names"],
        "disclaimer": "This is contract review assistance, not legal advice.",
    }
    listing_repository.localizations[(VERSION_ID, "en-US")] = PublicLocalizationRecord(
        source_hash=localization_source_hash(source),
        content=content,
    )

    response = public_client.get(
        f"/api/v1/public/listings/{PUBLISHED_ID}", params={"locale": "en-US"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content_locale"] == "en-US"
    assert data["fallback_locale"] is None
    assert data["localized_content"]["easy_explanation"].startswith("Plain-language")
    assert data["localized_content"]["preserved_names"] == [
        "해운대 오션스테이",
        "해운대구",
    ]

    list_response = public_client.get("/api/v1/public/listings", params={"locale": "en-US"})
    card = next(item for item in list_response.json()["data"] if item["id"] == str(PUBLISHED_ID))
    assert card["title"] == "2026 Busan Summer Room Supply"
    assert card["public_headline"] == "Oceanstay group accommodation in Haeundae"
    assert card["ai_summary"] == "Public summary for 2026 group accommodation."
    assert card["content_locale"] == "en-US"
    assert card["fallback_locale"] is None


def test_paused_listing_remains_readable_but_is_not_contractable(
    public_client: TestClient,
) -> None:
    response = public_client.get(f"/api/v1/public/listings/{PAUSED_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "paused"
    assert response.json()["data"]["contract_available"] is False


def test_contract_preview_returns_only_public_buyer_finding(
    public_client: TestClient,
) -> None:
    response = public_client.get(f"/api/v1/public/listings/{PUBLISHED_ID}/contract-preview")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["listing_version_id"] == str(VERSION_ID)
    assert data["body"] == "공개 계약 본문입니다."
    assert data["findings"] == [
        {
            "clause_id": str(CLAUSE_ID),
            "severity": "medium",
            "explanation": "취소 수수료 확정 시점이 모호합니다.",
            "suggested_text": "무료 취소 기한을 명시해 보세요.",
            "disclaimer": "법률 자문이 아닌 계약 검토 보조 의견입니다.",
        }
    ]


@pytest.mark.parametrize("listing_id", [DRAFT_ID, EXPIRED_ID, UUID(int=999)])
def test_non_public_or_missing_listing_is_not_found(
    public_client: TestClient, listing_id: UUID
) -> None:
    response = public_client.get(f"/api/v1/public/listings/{listing_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LISTING_NOT_FOUND"


def test_malformed_cursor_is_rejected(public_client: TestClient) -> None:
    response = public_client.get("/api/v1/public/listings", params={"cursor": "not-a-valid-cursor"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_public_responses_do_not_expose_internal_or_personal_data(
    public_client: TestClient,
) -> None:
    responses = [
        public_client.get("/api/v1/public/listings"),
        public_client.get(f"/api/v1/public/listings/{PUBLISHED_ID}"),
        public_client.get(f"/api/v1/public/listings/{PUBLISHED_ID}/contract-preview"),
    ]

    combined = " ".join(str(response.json()).lower() for response in responses)
    for forbidden in (
        "business_registration_no",
        "verification_note",
        "storage_object_path",
        "provider_request_id",
        "seller-only analysis",
        "created_by",
        "email",
        "phone",
    ):
        assert forbidden not in combined


@pytest.mark.parametrize(
    "params",
    [
        {"category": "restaurant"},
        {"locale": "fr-FR"},
        {"people": 0},
        {"min_price": 200, "max_price": 100},
        {"start_date": "2026-09-01", "end_date": "2026-08-01"},
        {"limit": 101},
        {"currency": "krw"},
    ],
)
def test_invalid_public_listing_query_is_rejected(
    public_client: TestClient, params: dict[str, object]
) -> None:
    response = public_client.get("/api/v1/public/listings", params=params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_database_failure_uses_safe_error_envelope(
    public_client: TestClient, listing_repository: FakePublicListingRepository
) -> None:
    listing_repository.unavailable = True

    response = public_client.get("/api/v1/public/listings")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["details"] == {}


def test_openapi_exposes_public_listing_schemas(public_client: TestClient) -> None:
    response = public_client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()
    paths = openapi["paths"]
    assert "get" in paths["/api/v1/public/listings"]
    assert "get" in paths["/api/v1/public/listings/{listing_id}"]
    assert "get" in paths["/api/v1/public/listings/{listing_id}/contract-preview"]
    parameter_names = {
        parameter["name"] for parameter in paths["/api/v1/public/listings"]["get"]["parameters"]
    }
    assert "contract_available_only" in parameter_names
    detail_properties = openapi["components"]["schemas"]["PublicListingDetail"]["properties"]
    for field in (
        "cancellation_policy",
        "refund_policy",
        "settlement_policy",
        "safety_policy",
        "compensation_policy",
        "liability_policy",
        "price_display_basis",
        "contract_availability_note",
        "attention_required_count",
        "no_show_policy",
        "vat_included",
    ):
        assert field in detail_properties
