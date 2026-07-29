from functools import lru_cache
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.integrations.auth import (
    AuthenticatedUser,
    AuthProvider,
    AuthProviderUnavailableError,
    AuthTokenInvalidError,
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
    timeout_seconds: float,
) -> SupabaseAuthProvider:
    return SupabaseAuthProvider(
        supabase_url=supabase_url,
        publishable_key=publishable_key,
        audience=audience,
        jwks_url=jwks_url,
        jwks_cache_seconds=jwks_cache_seconds,
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
        settings.supabase_auth_timeout_seconds,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    provider: Annotated[AuthProvider, Depends(get_auth_provider)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="A Bearer access token is required.",
        )
    try:
        return await provider.verify_access_token(credentials.credentials)
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
