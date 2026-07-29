import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.integrations.auth import AuthTokenInvalidError, SupabaseAuthProvider

USER_ID = UUID("20000000-0000-0000-0000-000000000001")
SUPABASE_URL = "https://project-ref.supabase.co"
KEY_ID = "test-key"


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
