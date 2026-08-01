from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_registration_repository
from app.core.auth import get_auth_account_provider, get_auth_provider
from app.core.config import Settings, get_settings
from app.integrations.auth import (
    AuthAccountError,
    AuthenticatedUser,
    AuthLoginResult,
    AuthSession,
    AuthSignupResult,
    FakeAuthProvider,
)
from app.repositories.auth_accounts import (
    RegistrationConflictError,
    RegistrationRecord,
    RegistrationRepositoryError,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000010")
ORG_ID = UUID("10000000-0000-0000-0000-000000000010")


class FakeAccountProvider:
    def __init__(self) -> None:
        self.error: str | None = None
        self.delete_error: str | None = None
        self.deleted_users: list[UUID] = []
        self.logged_out_tokens: list[str] = []
        self.password_changes: list[tuple[str, str]] = []
        self.login_calls: list[tuple[str, str]] = []
        self.password_reset_emails: list[tuple[str, str | None]] = []
        self.signup_session: AuthSession | None = None
        self.session = AuthSession(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            token_type="bearer",
            expires_in=3600,
            expires_at=1_785_552_000,
        )

    def _raise_if_needed(self) -> None:
        if self.error:
            raise AuthAccountError(self.error)

    async def signup(self, email: str, password: str) -> AuthSignupResult:
        del password
        self._raise_if_needed()
        return AuthSignupResult(USER_ID, email, self.signup_session)

    async def login(self, email: str, password: str) -> AuthLoginResult:
        self._raise_if_needed()
        self.login_calls.append((email, password))
        return AuthLoginResult(USER_ID, email, self.session)

    async def logout(self, access_token: str) -> None:
        self._raise_if_needed()
        self.logged_out_tokens.append(access_token)

    async def change_password(self, access_token: str, new_password: str) -> None:
        self._raise_if_needed()
        self.password_changes.append((access_token, new_password))

    async def send_password_reset_email(self, email: str, redirect_to: str | None = None) -> None:
        self._raise_if_needed()
        self.password_reset_emails.append((email, redirect_to))

    async def delete_user(self, user_id: UUID) -> None:
        if self.delete_error:
            raise AuthAccountError(self.delete_error)
        self.deleted_users.append(user_id)


class FakeRegistrationRepository:
    def __init__(self) -> None:
        self.buyer_values: dict[str, Any] | None = None
        self.seller_values: dict[str, Any] | None = None
        self.error: Exception | None = None

    async def create_buyer(self, values: dict[str, Any]) -> RegistrationRecord:
        if self.error:
            raise self.error
        self.buyer_values = values
        return RegistrationRecord(values["user_id"], None)

    async def create_seller(self, values: dict[str, Any]) -> RegistrationRecord:
        if self.error:
            raise self.error
        self.seller_values = values
        return RegistrationRecord(values["user_id"], ORG_ID)


@pytest.fixture
def account_provider() -> FakeAccountProvider:
    return FakeAccountProvider()


@pytest.fixture
def registration_repository() -> FakeRegistrationRepository:
    return FakeRegistrationRepository()


@pytest.fixture
def api_client(
    app: FastAPI,
    account_provider: FakeAccountProvider,
    registration_repository: FakeRegistrationRepository,
) -> TestClient:
    app.dependency_overrides[get_auth_account_provider] = lambda: account_provider
    app.dependency_overrides[get_registration_repository] = lambda: registration_repository
    app.dependency_overrides[get_auth_provider] = lambda: FakeAuthProvider(
        {"valid-token": AuthenticatedUser(USER_ID, "buyer@example.jp")}
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        auth_password_reset_redirect_url="https://app.example.test/reset-password",
    )
    with TestClient(app) as client:
        yield client


def buyer_signup_payload() -> dict[str, Any]:
    return {
        "role": "buyer",
        "email": "buyer@example.jp",
        "password": "correct-horse",
        "password_confirmation": "correct-horse",
        "display_name": "Aiko Tanaka",
        "phone": "+81 90-0000-0000",
        "country_code": "JP",
        "locale": "ja-JP",
        "affiliation_name": "GlobalTrip Japan",
        "business_type": "ota",
        "default_group_name": "Busan Tour",
        "preferred_currency": "JPY",
    }


def seller_signup_payload() -> dict[str, Any]:
    return {
        "role": "seller",
        "email": "seller@example.kr",
        "password": "correct-horse",
        "password_confirmation": "correct-horse",
        "display_name": "Kim Min-su",
        "phone": "051-740-2026",
        "organization_name": "Haeundae Ocean Stay",
        "legal_name": "Haeundae Ocean Stay Co., Ltd.",
        "representative_name": "Kim Min-su",
        "business_registration_no": "617-81-20260",
        "business_address": "Busan, Haeundae-gu",
        "supply_categories": ["accommodation", "tour"],
        "job_title": "Owner",
    }


def bearer(token: str = "valid-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_buyer_signup_creates_personal_profile(api_client, registration_repository) -> None:
    response = api_client.post("/api/v1/auth/signup", json=buyer_signup_payload())

    assert response.status_code == 201
    assert response.json()["data"] == {
        "user_id": str(USER_ID),
        "email": "buyer@example.jp",
        "role": "buyer",
        "organization_id": None,
        "organization_verification_status": None,
        "email_confirmation_required": True,
        "session": None,
    }
    assert registration_repository.buyer_values["affiliation_name"] == "GlobalTrip Japan"
    assert registration_repository.buyer_values["business_type"] == "ota"
    assert registration_repository.seller_values is None


def test_seller_signup_creates_pending_organization(api_client, registration_repository) -> None:
    response = api_client.post("/api/v1/auth/signup", json=seller_signup_payload())

    assert response.status_code == 201
    assert response.json()["data"]["organization_id"] == str(ORG_ID)
    assert response.json()["data"]["organization_verification_status"] == "pending"
    assert registration_repository.seller_values["supply_categories"] == [
        "accommodation",
        "tour",
    ]
    assert registration_repository.seller_values["job_title"] == "Owner"


def test_signup_rejects_mismatched_passwords(api_client) -> None:
    payload = buyer_signup_payload()
    payload["password_confirmation"] = "different-password"

    response = api_client.post("/api/v1/auth/signup", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_signup_maps_duplicate_email(api_client, account_provider) -> None:
    account_provider.error = "email_conflict"

    response = api_client.post("/api/v1/auth/signup", json=buyer_signup_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_CONFLICT"


@pytest.mark.parametrize(
    ("repository_error", "expected_code"),
    [
        (RegistrationConflictError("username"), "USERNAME_CONFLICT"),
        (RegistrationRepositoryError(), "DATABASE_UNAVAILABLE"),
    ],
)
def test_signup_rolls_back_auth_user_after_database_failure(
    api_client,
    account_provider,
    registration_repository,
    repository_error,
    expected_code,
) -> None:
    registration_repository.error = repository_error

    response = api_client.post("/api/v1/auth/signup", json=buyer_signup_payload())

    assert response.json()["error"]["code"] == expected_code
    assert account_provider.deleted_users == [USER_ID]


def test_signup_reports_failed_compensation(
    api_client, account_provider, registration_repository
) -> None:
    registration_repository.error = RegistrationRepositoryError()
    account_provider.delete_error = "provider_unavailable"

    response = api_client.post("/api/v1/auth/signup", json=buyer_signup_payload())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SIGNUP_ROLLBACK_FAILED"


def test_login_returns_supabase_session(api_client) -> None:
    response = api_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer@example.jp", "password": "correct-horse"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["session"]["access_token"] == "new-access-token"
    assert response.json()["data"]["session"]["refresh_token"] == "new-refresh-token"


def test_login_rejects_invalid_credentials(api_client, account_provider) -> None:
    account_provider.error = "invalid_credentials"

    response = api_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer@example.jp", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_demo_login_is_disabled_by_default(api_client) -> None:
    response = api_client.post("/api/v1/auth/demo-login", json={"role": "buyer"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEMO_LOGIN_DISABLED"


@pytest.mark.parametrize(
    ("role", "expected_email", "expected_password"),
    [
        ("buyer", "demo-buyer@example.test", "buyer-demo-password"),
        ("seller", "demo-seller@example.test", "seller-demo-password"),
    ],
)
def test_demo_login_uses_server_side_credentials(
    app,
    api_client,
    account_provider,
    role,
    expected_email,
    expected_password,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        demo_login_enabled=True,
        demo_buyer_email="demo-buyer@example.test",
        demo_buyer_password="buyer-demo-password",
        demo_seller_email="demo-seller@example.test",
        demo_seller_password="seller-demo-password",
    )

    response = api_client.post("/api/v1/auth/demo-login", json={"role": role})

    assert response.status_code == 200
    assert response.json()["data"]["email"] == expected_email
    assert account_provider.login_calls[-1] == (expected_email, expected_password)


def test_logout_requires_authentication(api_client) -> None:
    response = api_client.post("/api/v1/auth/logout")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_logout_revokes_session(api_client, account_provider) -> None:
    response = api_client.post("/api/v1/auth/logout", headers=bearer())

    assert response.status_code == 200
    assert response.json()["data"] == {"logged_out": True}
    assert account_provider.logged_out_tokens == ["valid-token"]


def test_password_change_updates_authenticated_user(api_client, account_provider) -> None:
    response = api_client.patch(
        "/api/v1/auth/password",
        headers=bearer(),
        json={
            "new_password": "new-correct-horse",
            "new_password_confirmation": "new-correct-horse",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"password_changed": True}
    assert account_provider.password_changes == [("valid-token", "new-correct-horse")]


def test_password_change_rejects_mismatch(api_client, account_provider) -> None:
    response = api_client.patch(
        "/api/v1/auth/password",
        headers=bearer(),
        json={
            "new_password": "new-correct-horse",
            "new_password_confirmation": "different-password",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert account_provider.password_changes == []


def test_password_change_button_sends_reset_email(api_client, account_provider) -> None:
    response = api_client.post("/api/v1/auth/password/reset-email", headers=bearer())

    assert response.status_code == 200
    assert response.json()["data"] == {"email_sent": True}
    assert account_provider.password_reset_emails == [
        ("buyer@example.jp", "https://app.example.test/reset-password")
    ]
