from functools import lru_cache

from pydantic import SecretStr
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

    # --- Stripe. Всё необязательное: без ключей вебхук закрыт (503), checkout недоступен. ---
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None  # whsec_..., отдельный для каждого endpoint/режима
    stripe_price_pro: str | None = None  # price_...
    # Отдельный DSN роли billing_service (EXECUTE только на app.billing_*). НЕ тот же, что database_url.
    billing_database_url: str | None = None
    app_base_url: str = "http://localhost:5173"  # для success/cancel URL checkout


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg, unused-ignore]
