from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode
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


class AuthAccountError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class AuthSession:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    expires_at: int | None


@dataclass(frozen=True, slots=True)
class AuthSignupResult:
    user_id: UUID
    email: str
    session: AuthSession | None


@dataclass(frozen=True, slots=True)
class AuthLoginResult:
    user_id: UUID
    email: str
    session: AuthSession


class AuthAccountProvider(Protocol):
    async def signup(self, email: str, password: str) -> AuthSignupResult: ...

    async def login(self, email: str, password: str) -> AuthLoginResult: ...

    async def logout(self, access_token: str) -> None: ...

    async def change_password(self, access_token: str, new_password: str) -> None: ...

    async def send_password_reset_email(
        self, email: str, redirect_to: str | None = None
    ) -> None: ...

    async def delete_user(self, user_id: UUID) -> None: ...


class SupabaseAuthAccountProvider:
    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        service_role_key: str,
        timeout_seconds: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = f"{supabase_url.rstrip('/')}/auth/v1"
        self._publishable_key = publishable_key
        self._service_role_key = service_role_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def signup(self, email: str, password: str) -> AuthSignupResult:
        payload = await self._request(
            "POST",
            "/signup",
            headers={"apikey": self._publishable_key},
            json={"email": email, "password": password},
        )
        user = self._user(payload)
        if user.get("identities") == []:
            raise AuthAccountError("email_conflict")
        return AuthSignupResult(
            user_id=self._uuid(user.get("id")),
            email=self._email(user.get("email"), email),
            session=self._session(payload, required=False),
        )

    async def login(self, email: str, password: str) -> AuthLoginResult:
        payload = await self._request(
            "POST",
            "/token?grant_type=password",
            headers={"apikey": self._publishable_key},
            json={"email": email, "password": password},
        )
        user = self._user(payload)
        return AuthLoginResult(
            user_id=self._uuid(user.get("id")),
            email=self._email(user.get("email"), email),
            session=self._session(payload, required=True),
        )

    async def logout(self, access_token: str) -> None:
        await self._request(
            "POST",
            "/logout",
            headers=self._user_headers(access_token),
            json={},
            allow_empty=True,
        )

    async def change_password(self, access_token: str, new_password: str) -> None:
        await self._request(
            "PUT",
            "/user",
            headers=self._user_headers(access_token),
            json={"password": new_password},
        )

    async def send_password_reset_email(self, email: str, redirect_to: str | None = None) -> None:
        path = "/recover"
        if redirect_to:
            path = f"{path}?{urlencode({'redirect_to': redirect_to})}"
        await self._request(
            "POST",
            path,
            headers={"apikey": self._publishable_key},
            json={"email": email},
            allow_empty=True,
        )

    async def delete_user(self, user_id: UUID) -> None:
        await self._request(
            "DELETE",
            f"/admin/users/{user_id}",
            headers={
                "apikey": self._service_role_key,
                "Authorization": f"Bearer {self._service_role_key}",
            },
            allow_empty=True,
        )

    def _user_headers(self, access_token: str) -> dict[str, str]:
        return {
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {access_token}",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise AuthAccountError("provider_unavailable") from exc
        if response.status_code >= 400:
            self._raise_response_error(response)
        if allow_empty and not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthAccountError("provider_unavailable") from exc
        if not isinstance(payload, dict):
            raise AuthAccountError("provider_unavailable")
        return payload

    @staticmethod
    def _raise_response_error(response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message = " ".join(
            str(payload.get(key, "")) for key in ("code", "error_code", "msg", "message")
        ).lower()
        if response.status_code in {401, 403}:
            reason = "invalid_credentials" if "password" in message else "token_invalid"
        elif response.status_code == 422 and ("password" in message or "weak" in message):
            reason = "weak_password"
        elif response.status_code in {400, 422} and (
            "registered" in message or "exists" in message or "unique" in message
        ):
            reason = "email_conflict"
        elif response.status_code == 429:
            reason = "rate_limited"
        elif response.status_code >= 500:
            reason = "provider_unavailable"
        else:
            reason = "request_rejected"
        raise AuthAccountError(reason)

    @staticmethod
    def _user(payload: dict[str, Any]) -> dict[str, Any]:
        user = payload.get("user")
        if not isinstance(user, dict):
            raise AuthAccountError("provider_unavailable")
        return user

    @staticmethod
    def _uuid(value: Any) -> UUID:
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise AuthAccountError("provider_unavailable") from exc

    @staticmethod
    def _email(value: Any, fallback: str) -> str:
        return value if isinstance(value, str) and value else fallback

    @staticmethod
    def _session(payload: dict[str, Any], *, required: bool) -> AuthSession | None:
        source: Any = payload.get("session", payload)
        if source is None and not required:
            return None
        if not isinstance(source, dict):
            raise AuthAccountError("provider_unavailable")
        access_token = source.get("access_token")
        refresh_token = source.get("refresh_token")
        expires_in = source.get("expires_in")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            if not required:
                return None
            raise AuthAccountError("provider_unavailable")
        if not isinstance(expires_in, int) or expires_in <= 0:
            raise AuthAccountError("provider_unavailable")
        expires_at = source.get("expires_at")
        return AuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=str(source.get("token_type") or "bearer"),
            expires_in=expires_in,
            expires_at=expires_at if isinstance(expires_at, int) else None,
        )


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
