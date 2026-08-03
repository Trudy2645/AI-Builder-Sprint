from functools import lru_cache
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.integrations.auth import (
    AuthAccountProvider,
    AuthenticatedUser,
    AuthProvider,
    AuthProviderUnavailableError,
    AuthTokenInvalidError,
    SupabaseAuthAccountProvider,
    SupabaseAuthProvider,
)

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _build_auth_provider(
    supabase_url: str,
    publishable_key: str | None,
    audience: str,
    jwks_url: str | None,
    jwks_cache_seconds: int,
    jwt_leeway_seconds: int,
    timeout_seconds: float,
) -> SupabaseAuthProvider:
    return SupabaseAuthProvider(
        supabase_url=supabase_url,
        publishable_key=publishable_key,
        audience=audience,
        jwks_url=jwks_url,
        jwks_cache_seconds=jwks_cache_seconds,
        jwt_leeway_seconds=jwt_leeway_seconds,
        timeout_seconds=timeout_seconds,
    )


def get_auth_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthProvider:
    if not settings.supabase_url:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_PROVIDER_UNAVAILABLE",
            message="Authentication provider is not configured.",
        )
    return _build_auth_provider(
        settings.supabase_url,
        settings.supabase_publishable_key,
        settings.supabase_jwt_audience,
        settings.supabase_jwks_url,
        settings.supabase_jwks_cache_seconds,
        settings.supabase_jwt_leeway_seconds,
        settings.supabase_auth_timeout_seconds,
    )


@lru_cache
def _build_auth_account_provider(
    supabase_url: str,
    publishable_key: str,
    service_role_key: str,
    timeout_seconds: float,
) -> SupabaseAuthAccountProvider:
    return SupabaseAuthAccountProvider(
        supabase_url=supabase_url,
        publishable_key=publishable_key,
        service_role_key=service_role_key,
        timeout_seconds=timeout_seconds,
    )


def get_auth_account_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthAccountProvider:
    if (
        not settings.supabase_url
        or not settings.supabase_publishable_key
        or not settings.supabase_service_role_key
    ):
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_PROVIDER_UNAVAILABLE",
            message="Authentication provider is not configured.",
        )
    return _build_auth_account_provider(
        settings.supabase_url,
        settings.supabase_publishable_key,
        settings.supabase_service_role_key,
        settings.supabase_auth_timeout_seconds,
    )


async def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="A Bearer access token is required.",
        )
    return credentials.credentials


async def get_current_user(
    access_token: Annotated[str, Depends(get_access_token)],
    provider: Annotated[AuthProvider, Depends(get_auth_provider)],
) -> AuthenticatedUser:
    try:
        return await provider.verify_access_token(access_token)
    except AuthTokenInvalidError as exc:
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="The access token is invalid or expired.",
        ) from exc
    except AuthProviderUnavailableError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="AUTH_PROVIDER_UNAVAILABLE",
            message="Authentication provider is unavailable.",
        ) from exc
