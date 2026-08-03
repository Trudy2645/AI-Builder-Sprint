import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.integrations.auth import (
    AuthAccountError,
    AuthTokenInvalidError,
    SupabaseAuthAccountProvider,
    SupabaseAuthProvider,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000001")
SUPABASE_URL = "https://project-ref.supabase.co"
KEY_ID = "test-key"


def account_provider(handler) -> SupabaseAuthAccountProvider:
    return SupabaseAuthAccountProvider(
        supabase_url=SUPABASE_URL,
        publishable_key="publishable-key",
        service_role_key="service-role-key",
        transport=httpx.MockTransport(handler),
    )


def build_provider_and_key() -> tuple[SupabaseAuthProvider, ec.EllipticCurvePrivateKey]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": KEY_ID, "alg": "ES256", "use": "sig"})
    provider = SupabaseAuthProvider(
        supabase_url=SUPABASE_URL,
        publishable_key=None,
    )
    provider._jwks = {"keys": [public_jwk]}
    provider._jwks_fetched_at = datetime.now(UTC)
    return provider, private_key


def make_token(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    expires_at: datetime,
    audience: str = "authenticated",
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": f"{SUPABASE_URL}/auth/v1",
            "aud": audience,
            "sub": str(USER_ID),
            "role": "authenticated",
            "email": "verified@example.com",
            "iat": now - timedelta(seconds=1),
            "exp": expires_at,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )


@pytest.mark.asyncio
async def test_supabase_provider_verifies_asymmetric_jwt_claims() -> None:
    provider, private_key = build_provider_and_key()
    token = make_token(private_key, expires_at=datetime.now(UTC) + timedelta(minutes=5))

    identity = await provider.verify_access_token(token)

    assert identity.id == USER_ID
    assert identity.email == "verified@example.com"


@pytest.mark.asyncio
async def test_supabase_provider_rejects_expired_jwt() -> None:
    provider, private_key = build_provider_and_key()
    token = make_token(private_key, expires_at=datetime.now(UTC) - timedelta(minutes=1))

    with pytest.raises(AuthTokenInvalidError):
        await provider.verify_access_token(token)


@pytest.mark.asyncio
async def test_supabase_provider_rejects_wrong_audience() -> None:
    provider, private_key = build_provider_and_key()
    token = make_token(
        private_key,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        audience="anon",
    )

    with pytest.raises(AuthTokenInvalidError):
        await provider.verify_access_token(token)


@pytest.mark.asyncio
async def test_supabase_provider_accepts_small_issuer_clock_skew() -> None:
    provider, private_key = build_provider_and_key()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": f"{SUPABASE_URL}/auth/v1",
            "aud": "authenticated",
            "sub": str(USER_ID),
            "role": "authenticated",
            "email": "verified@example.com",
            "iat": now + timedelta(seconds=1),
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )

    assert (await provider.verify_access_token(token)).id == USER_ID


@pytest.mark.asyncio
async def test_account_provider_signs_up_and_parses_session() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/signup"
        assert request.headers["apikey"] == "publishable-key"
        assert json.loads(request.content) == {
            "email": "new@example.com",
            "password": "correct-horse",
        }
        return httpx.Response(
            200,
            json={
                "user": {"id": str(USER_ID), "email": "new@example.com"},
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "token_type": "bearer",
            },
        )

    result = await account_provider(handler).signup("new@example.com", "correct-horse")

    assert result.user_id == USER_ID
    assert result.session is not None
    assert result.session.access_token == "access"


@pytest.mark.asyncio
async def test_account_provider_maps_duplicate_signup() -> None:
    provider = account_provider(
        lambda _: httpx.Response(
            200,
            json={
                "user": {
                    "id": str(USER_ID),
                    "email": "existing@example.com",
                    "identities": [],
                }
            },
        )
    )

    with pytest.raises(AuthAccountError, match="email_conflict"):
        await provider.signup("existing@example.com", "correct-horse")


@pytest.mark.asyncio
async def test_account_provider_uses_bearer_token_for_logout_and_password_change() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(200, json={"id": str(USER_ID)})

    provider = account_provider(handler)
    await provider.logout("user-access-token")
    await provider.change_password("user-access-token", "new-correct-horse")

    assert [request.url.path for request in requests] == ["/auth/v1/logout", "/auth/v1/user"]
    assert all(
        request.headers["Authorization"] == "Bearer user-access-token" for request in requests
    )
    assert json.loads(requests[1].content) == {"password": "new-correct-horse"}


@pytest.mark.asyncio
async def test_account_provider_uses_service_role_only_for_compensation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == f"/auth/v1/admin/users/{USER_ID}"
        assert request.headers["apikey"] == "service-role-key"
        assert request.headers["Authorization"] == "Bearer service-role-key"
        return httpx.Response(204)

    await account_provider(handler).delete_user(USER_ID)


@pytest.mark.asyncio
async def test_account_provider_sends_password_recovery_email() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/recover"
        assert request.url.params["redirect_to"] == "https://app.example.test/reset password"
        assert request.headers["apikey"] == "publishable-key"
        assert json.loads(request.content) == {"email": "user@example.com"}
        return httpx.Response(200, json={})

    await account_provider(handler).send_password_reset_email(
        "user@example.com",
        "https://app.example.test/reset password",
    )
