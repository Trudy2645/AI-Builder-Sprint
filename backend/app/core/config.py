from functools import lru_cache
from typing import Literal

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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str | None = Field(default=None, repr=False)
    supabase_url: str | None = None
    supabase_publishable_key: str | None = Field(default=None, repr=False)
    supabase_service_role_key: str | None = Field(default=None, repr=False)
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str | None = None
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60, le=1200)
    supabase_auth_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    storage_request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    document_max_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    document_download_url_expires_seconds: int = Field(default=300, ge=60, le=3600)
    auth_password_reset_redirect_url: str | None = None
    demo_login_enabled: bool = False
    demo_buyer_email: str | None = None
    demo_buyer_password: str | None = Field(default=None, repr=False)
    demo_seller_email: str | None = None
    demo_seller_password: str | None = Field(default=None, repr=False)
    ai_provider: Literal["fake", "upstage"] = "fake"
    upstage_api_key: str | None = Field(default=None, repr=False)
    upstage_document_base_url: str = "https://api.upstage.ai/v1"
    upstage_chat_base_url: str = "https://api.upstage.ai/v1"
    upstage_agent_base_url: str = "https://api.upstage.ai/v2"
    upstage_chat_model: str = "solar-pro3"
    upstage_official_vector_store_id: str | None = Field(default=None, repr=False)
    upstage_template_vector_store_id: str | None = Field(default=None, repr=False)
    ai_prompt_version: str = "busan-link-v1"
    ai_agent_max_iterations: int = Field(default=2, ge=1, le=2)
    ai_max_retries: int = Field(default=3, ge=0, le=5)
    ai_request_timeout_seconds: float = Field(default=60, gt=0, le=180)

    modusign_base_url: str = "https://api.modusign.co.kr"
    modusign_api_key: str | None = Field(default=None, repr=False)
    modusign_auth_email: str | None = None
    modusign_template_id: str | None = None
    modusign_timeout_seconds: float = Field(default=15.0, gt=0, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
