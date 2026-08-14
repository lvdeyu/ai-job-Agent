from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-job-AGENT"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+psycopg://ai_job_agent:ai_job_agent@localhost:5432/ai_job_agent",
        validation_alias="BACKEND_DATABASE_URL",
    )
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "ai_job_agent"
    minio_secret_key: str = "ai_job_agent_dev_secret"
    jwt_secret_key: str = "local-dev-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    resume_storage_dir: str = "../data/resumes"
    cors_origins: list[str] = ["http://localhost:15173", "http://127.0.0.1:15173"]
    boss_adapter_enabled: bool = True
    boss_adapter_min_extension_version: str = "0.1.0"
    boss_collection_page_limit: int = 3
    boss_collection_rate_limit_window_seconds: int = 60
    boss_collection_rate_limit_max_sessions: int = 30

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
