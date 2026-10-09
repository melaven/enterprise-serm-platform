from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime-коннект под ролью app_tenant (НЕ postgres), Supavisor :6543:
    # postgresql+asyncpg://app_tenant.<ref>:<pwd>@<pooler-host>:6543/postgres
    #   ?prepared_statement_cache_size=0
    database_url: str
    # https://<ref>.supabase.co
    supabase_url: str
    # Брокер ARQ. В проде: rediss://:<password>@host:6379/0 (Redis только во
    # внутренней сети: ARQ сериализует аргументы задач через pickle).
    redis_url: str = "redis://127.0.0.1:6379/0"
    # Только для legacy-проектов с HS256. Пусто -> проверка подписи через JWKS.
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"
    
    # Google Gemini API для LLM-анализа
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg, unused-ignore]
