from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_profile_repository
from app.core.auth import get_auth_provider
from app.integrations.auth import AuthenticatedUser, FakeAuthProvider
from app.repositories.profiles import (
    OrganizationMembershipRecord,
    OrganizationRecord,
    ProfileRecord,
)
from tests.fakes import FakeProfileRepository

BUYER_ID = UUID("00000000-0000-0000-0000-000000000001")
ADMIN_ID = UUID("00000000-0000-0000-0000-000000000002")
MEMBER_ID = UUID("00000000-0000-0000-0000-000000000003")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000004")
MISSING_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000005")
ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORG_ID = UUID("10000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def profile(user_id: UUID, username: str, role: str) -> ProfileRecord:
    return ProfileRecord(
        id=user_id,
        username=username,
        display_name=username.title(),
        phone=None,
        country_code="JP" if role == "buyer" else "KR",
        locale="ja-JP" if role == "buyer" else "ko-KR",
        preferred_currency="JPY" if role == "buyer" else "KRW",
        default_group_name="Busan Friends" if role == "buyer" else None,
        active_organization_id=ORG_ID if role == "seller" else None,
        active_business_role=role,
        created_at=NOW,
        updated_at=NOW,
    )


def organization(organization_id: UUID, name: str) -> OrganizationRecord:
    return OrganizationRecord(
        id=organization_id,
        organization_type="seller",
        name=name,
        legal_name=f"{name} Co., Ltd.",
        business_registration_no="protected-registration-number",
        verification_status="verified",
        rating_average=Decimal("4.80"),
        rating_count=24,
        created_at=NOW,
        updated_at=NOW,
        verified_at=NOW,
    )


@pytest.fixture
def fake_repository() -> FakeProfileRepository:
    org = organization(ORG_ID, "Ocean Stay")
    other_org = organization(OTHER_ORG_ID, "Other Seller")
    memberships = {
        (ADMIN_ID, ORG_ID): OrganizationMembershipRecord(
            organization_id=ORG_ID,
            organization_name=org.name,
            organization_type="seller",
            verification_status="verified",
            role="admin",
        ),
        (MEMBER_ID, ORG_ID): OrganizationMembershipRecord(
            organization_id=ORG_ID,
            organization_name=org.name,
            organization_type="seller",
            verification_status="verified",
            role="member",
        ),
        (OTHER_ID, OTHER_ORG_ID): OrganizationMembershipRecord(
            organization_id=OTHER_ORG_ID,
            organization_name=other_org.name,
            organization_type="seller",
            verification_status="verified",
            role="owner",
        ),
    }
    return FakeProfileRepository(
        profiles=[
            profile(BUYER_ID, "buyer_aiko", "buyer"),
            profile(ADMIN_ID, "seller_admin", "seller"),
            profile(MEMBER_ID, "seller_member", "seller"),
            profile(OTHER_ID, "other_seller", "seller"),
        ],
        organizations=[org, other_org],
        memberships=memberships,
    )


@pytest.fixture
def auth_provider() -> FakeAuthProvider:
    return FakeAuthProvider(
        {
            "buyer-token": AuthenticatedUser(BUYER_ID, "buyer@example.jp"),
            "admin-token": AuthenticatedUser(ADMIN_ID, "admin@example.kr"),
            "member-token": AuthenticatedUser(MEMBER_ID, "member@example.kr"),
            "other-token": AuthenticatedUser(OTHER_ID, "other@example.kr"),
            "missing-profile-token": AuthenticatedUser(MISSING_PROFILE_ID, "missing@example.com"),
        }
    )


@pytest.fixture
def api_client(
    app: FastAPI,
    fake_repository: FakeProfileRepository,
    auth_provider: FakeAuthProvider,
) -> TestClient:
    app.dependency_overrides[get_profile_repository] = lambda: fake_repository
    app.dependency_overrides[get_auth_provider] = lambda: auth_provider
    with TestClient(app) as client:
        yield client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def organization_headers(token: str, organization_id: UUID = ORG_ID) -> dict[str, str]:
    return {**bearer(token), "X-Organization-Id": str(organization_id)}


def test_buyer_reads_own_profile(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/me", headers=bearer("buyer-token"))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": str(BUYER_ID),
        "email": "buyer@example.jp",
        "username": "buyer_aiko",
        "display_name": "Buyer_Aiko",
        "phone": None,
        "country_code": "JP",
        "locale": "ja-JP",
        "preferred_currency": "JPY",
        "default_group_name": "Busan Friends",
        "affiliation_name": None,
        "business_type": None,
        "role": "buyer",
        "created_at": "2026-07-29T00:00:00Z",
        "updated_at": "2026-07-29T00:00:00Z",
        "organizations": [],
    }


def test_buyer_updates_own_profile(api_client: TestClient) -> None:
    response = api_client.patch(
        "/api/v1/me",
        headers=bearer("buyer-token"),
        json={"display_name": "Aiko Tanaka", "locale": "en-US", "preferred_currency": "USD"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["display_name"] == "Aiko Tanaka"
    assert response.json()["data"]["locale"] == "en-US"
    assert response.json()["data"]["preferred_currency"] == "USD"


def test_seller_profile_includes_organization_and_can_read_it(api_client: TestClient) -> None:
    me_response = api_client.get("/api/v1/me", headers=bearer("admin-token"))
    organization_response = api_client.get(
        f"/api/v1/organizations/{ORG_ID}", headers=organization_headers("admin-token")
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["role"] == "seller"
    assert me_response.json()["data"]["organizations"][0]["id"] == str(ORG_ID)
    assert organization_response.status_code == 200
    assert organization_response.json()["data"]["member_role"] == "admin"


def test_organization_admin_updates_organization(api_client: TestClient) -> None:
    response = api_client.patch(
        f"/api/v1/organizations/{ORG_ID}",
        headers=organization_headers("admin-token"),
        json={"name": "Updated Ocean Stay", "legal_name": "Updated Ocean Stay Ltd."},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Updated Ocean Stay"


def test_authorization_header_is_required(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize("token", ["invalid-token", "expired-token"])
def test_invalid_or_expired_token_is_rejected(api_client: TestClient, token: str) -> None:
    response = api_client.get("/api/v1/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


def test_missing_profile_returns_not_found(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/me", headers=bearer("missing-profile-token"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROFILE_NOT_FOUND"


def test_patch_cannot_target_another_user(api_client: TestClient) -> None:
    response = api_client.patch(
        "/api/v1/me",
        headers=bearer("buyer-token"),
        json={"id": str(OTHER_ID), "display_name": "Compromised"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_other_organization_access_is_denied(api_client: TestClient) -> None:
    response = api_client.get(
        f"/api/v1/organizations/{ORG_ID}",
        headers=organization_headers("other-token", ORG_ID),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORG_ACCESS_DENIED"


def test_buyer_cannot_access_seller_organization(api_client: TestClient) -> None:
    response = api_client.get(
        f"/api/v1/organizations/{ORG_ID}",
        headers=organization_headers("buyer-token"),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORG_ACCESS_DENIED"


def test_organization_header_is_required(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/organizations/{ORG_ID}", headers=bearer("admin-token"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ORGANIZATION_HEADER_REQUIRED"


def test_organization_header_must_match_path(api_client: TestClient) -> None:
    response = api_client.get(
        f"/api/v1/organizations/{ORG_ID}",
        headers=organization_headers("admin-token", OTHER_ORG_ID),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORG_ACCESS_DENIED"


def test_member_can_read_but_cannot_update_organization(api_client: TestClient) -> None:
    get_response = api_client.get(
        f"/api/v1/organizations/{ORG_ID}", headers=organization_headers("member-token")
    )
    patch_response = api_client.patch(
        f"/api/v1/organizations/{ORG_ID}",
        headers=organization_headers("member-token"),
        json={"name": "Forbidden Update"},
    )

    assert get_response.status_code == 200
    assert patch_response.status_code == 403
    assert patch_response.json()["error"]["code"] == "ORG_ACCESS_DENIED"


def test_duplicate_username_returns_conflict(api_client: TestClient) -> None:
    response = api_client.patch(
        "/api/v1/me",
        headers=bearer("buyer-token"),
        json={"username": "SELLER_ADMIN"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_CONFLICT"


@pytest.mark.parametrize(
    ("payload", "field"),
    [({"locale": "fr-FR"}, "locale"), ({"preferred_currency": "usd"}, "preferred_currency")],
)
def test_invalid_locale_or_currency_is_rejected(
    api_client: TestClient, payload: dict[str, str], field: str
) -> None:
    response = api_client.patch("/api/v1/me", headers=bearer("buyer-token"), json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert field in str(response.json()["error"]["details"])


def test_responses_do_not_expose_credentials_or_internal_fields(api_client: TestClient) -> None:
    me_response = api_client.get("/api/v1/me", headers=bearer("admin-token"))
    organization_response = api_client.get(
        f"/api/v1/organizations/{ORG_ID}", headers=organization_headers("admin-token")
    )

    combined = f"{me_response.json()} {organization_response.json()}".lower()
    forbidden_fields = (
        "password",
        "service_role",
        "service-role",
        "verification_note",
        "created_by",
    )
    for forbidden in forbidden_fields:
        assert forbidden not in combined


def test_database_failure_uses_safe_error_envelope(
    api_client: TestClient, fake_repository: FakeProfileRepository
) -> None:
    fake_repository.unavailable = True

    response = api_client.get("/api/v1/me", headers=bearer("buyer-token"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["details"] == {}


def test_auth_provider_failure_uses_safe_error_envelope(
    app: FastAPI, fake_repository: FakeProfileRepository
) -> None:
    app.dependency_overrides[get_profile_repository] = lambda: fake_repository
    app.dependency_overrides[get_auth_provider] = lambda: FakeAuthProvider(unavailable=True)

    with TestClient(app) as client:
        response = client.get("/api/v1/me", headers=bearer("any-token"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_PROVIDER_UNAVAILABLE"


def test_openapi_exposes_profile_and_organization_schemas(api_client: TestClient) -> None:
    response = api_client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert {"get", "patch"} <= paths["/api/v1/me"].keys()
    assert {"get", "patch"} <= paths["/api/v1/organizations/{organization_id}"].keys()
