from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = ""  # postgresql+asyncpg://app_tenant:...@host/db?ssl=require

    # AI-разметка
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    business_name: str = "our company"
    ai_retry_max_attempts: int = Field(5, ge=1)

    # Воркер
    worker_max_jobs: int = Field(10, ge=1)
    worker_job_timeout_s: int = Field(300, ge=10)  # жёсткий потолок ARQ на задачу
    worker_max_tries: int = Field(4, ge=1)
    worker_result_ttl_s: int = Field(
        3600, ge=60
    )  # пока жив результат, тот же job_id не поставить

    # Пайплайн sync_platform_reviews
    sync_max_reviews: int = Field(500, ge=1, le=5000)
    sync_ai_timeout_s: float = Field(300.0, gt=0)
    sync_save_attempts: int = Field(3, ge=1)

    # Скрейпинг
    scrape_timeout_s: float = Field(120.0, gt=0)
    scrape_proxy_url: str | None = None
    retry_base_delay_s: float = Field(5.0, gt=0)
    retry_max_delay_s: float = Field(300.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
