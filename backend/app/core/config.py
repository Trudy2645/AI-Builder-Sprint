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
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str | None = Field(default=None, repr=False)
    supabase_url: str | None = None
    supabase_publishable_key: str | None = Field(default=None, repr=False)
    supabase_service_role_key: str | None = Field(default=None, repr=False)
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str | None = None
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60, le=1200)
    supabase_auth_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    modusign_base_url: str = "https://api.modusign.co.kr"
    modusign_api_key: str | None = Field(default=None, repr=False)
    modusign_auth_email: str | None = None
    modusign_template_id: str | None = None
    modusign_timeout_seconds: float = Field(default=15.0, gt=0, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
