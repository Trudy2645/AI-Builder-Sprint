from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK, PyJWTError


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: UUID
    email: str | None


class AuthProvider(Protocol):
    async def verify_access_token(self, token: str) -> AuthenticatedUser: ...


class AuthTokenInvalidError(Exception):
    """The supplied credential is not a valid Supabase user access token."""


class AuthProviderUnavailableError(Exception):
    """Supabase Auth could not be reached or is not configured."""


class SupabaseAuthProvider:
    _ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}

    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str | None,
        audience: str = "authenticated",
        jwks_url: str | None = None,
        jwks_cache_seconds: int = 600,
        timeout_seconds: float = 5.0,
    ) -> None:
        base_url = supabase_url.rstrip("/")
        self._issuer = f"{base_url}/auth/v1"
        self._jwks_url = jwks_url or f"{self._issuer}/.well-known/jwks.json"
        self._user_url = f"{self._issuer}/user"
        self._publishable_key = publishable_key
        self._audience = audience
        self._cache_duration = timedelta(seconds=jwks_cache_seconds)
        self._timeout_seconds = timeout_seconds
        self._jwks: dict[str, Any] | None = None
        self._jwks_fetched_at: datetime | None = None

    async def verify_access_token(self, token: str) -> AuthenticatedUser:
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise AuthTokenInvalidError from exc

        algorithm = header.get("alg")
        if algorithm in self._ASYMMETRIC_ALGORITHMS:
            claims = await self._verify_with_jwks(token, header)
            return self._identity_from_claims(claims)
        if algorithm == "HS256":
            return await self._verify_with_auth_server(token)
        raise AuthTokenInvalidError

    async def _verify_with_jwks(self, token: str, header: dict[str, Any]) -> dict[str, Any]:
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise AuthTokenInvalidError

        jwks = await self._get_jwks()
        key = self._find_key(jwks, key_id)
        if key is None:
            jwks = await self._get_jwks(force_refresh=True)
            key = self._find_key(jwks, key_id)
        if key is None:
            raise AuthTokenInvalidError

        try:
            verification_key = PyJWK.from_dict(key).key
            return jwt.decode(
                token,
                verification_key,
                algorithms=[header["alg"]],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except (PyJWTError, ValueError, TypeError) as exc:
            raise AuthTokenInvalidError from exc

    async def _get_jwks(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = datetime.now(UTC)
        if (
            not force_refresh
            and self._jwks is not None
            and self._jwks_fetched_at is not None
            and now - self._jwks_fetched_at < self._cache_duration
        ):
            return self._jwks

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(self._jwks_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthProviderUnavailableError from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise AuthProviderUnavailableError
        self._jwks = payload
        self._jwks_fetched_at = now
        return payload

    @staticmethod
    def _find_key(jwks: dict[str, Any], key_id: str) -> dict[str, Any] | None:
        for key in jwks["keys"]:
            if isinstance(key, dict) and key.get("kid") == key_id:
                return key
        return None

    async def _verify_with_auth_server(self, token: str) -> AuthenticatedUser:
        if not self._publishable_key:
            raise AuthProviderUnavailableError
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    self._user_url,
                    headers={
                        "apikey": self._publishable_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.HTTPError as exc:
            raise AuthProviderUnavailableError from exc

        if response.status_code in {401, 403}:
            raise AuthTokenInvalidError
        if response.status_code != 200:
            raise AuthProviderUnavailableError
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthProviderUnavailableError from exc
        return self._identity_from_user_response(payload)

    def _identity_from_claims(self, claims: dict[str, Any]) -> AuthenticatedUser:
        if claims.get("role") != "authenticated" or claims.get("is_anonymous") is True:
            raise AuthTokenInvalidError
        return self._build_identity(claims.get("sub"), claims.get("email"))

    @staticmethod
    def _identity_from_user_response(payload: Any) -> AuthenticatedUser:
        if not isinstance(payload, dict) or payload.get("is_anonymous") is True:
            raise AuthTokenInvalidError
        return SupabaseAuthProvider._build_identity(payload.get("id"), payload.get("email"))

    @staticmethod
    def _build_identity(subject: Any, email: Any) -> AuthenticatedUser:
        try:
            user_id = UUID(str(subject))
        except (TypeError, ValueError) as exc:
            raise AuthTokenInvalidError from exc
        return AuthenticatedUser(
            id=user_id,
            email=email if isinstance(email, str) and email else None,
        )


class FakeAuthProvider:
    def __init__(
        self,
        users_by_token: dict[str, AuthenticatedUser] | None = None,
        *,
        unavailable: bool = False,
    ) -> None:
        self._users_by_token = users_by_token or {}
        self._unavailable = unavailable

    async def verify_access_token(self, token: str) -> AuthenticatedUser:
        if self._unavailable:
            raise AuthProviderUnavailableError
        try:
            return self._users_by_token[token]
        except KeyError as exc:
            raise AuthTokenInvalidError from exc
