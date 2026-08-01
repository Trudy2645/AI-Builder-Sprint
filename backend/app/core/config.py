from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "BusanLink API"
    app_version: str = "0.1.0"
    app_environment: str = "local"
    docs_enabled: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str | None = Field(default=None, repr=False)
    supabase_url: str | None = None
    supabase_publishable_key: str | None = Field(default=None, repr=False)
    supabase_service_role_key: str | None = Field(default=None, repr=False)
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str | None = None
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60, le=1200)
    supabase_auth_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    auth_password_reset_redirect_url: str | None = None
    demo_login_enabled: bool = False
    demo_buyer_email: str | None = None
    demo_buyer_password: str | None = Field(default=None, repr=False)
    demo_seller_email: str | None = None
    demo_seller_password: str | None = Field(default=None, repr=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
