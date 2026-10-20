from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env ищем от корня проекта, а не от текущей директории: uvicorn/start.bat из другой папки
    # раньше молча не находил файл. Переменные окружения ОС приоритетнее .env (см. scripts/db_diag.py).
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[2] / ".env", ".env"), extra="ignore"
    )

    # Runtime-коннект под ролью app_tenant (НЕ postgres), Supavisor :6543:
    # postgresql+asyncpg://app_tenant.<ref>:<pwd>@<pooler-host>:6543/postgres
    #   ?prepared_statement_cache_size=0
    database_url: str
    # https://<ref>.supabase.co
    supabase_url: str
    # Брокер ARQ. В проде: rediss://:<password>@host:6379/0 (Redis только во
    # внутренней сети: ARQ сериализует аргументы задач через pickle).
    # --- Таймауты БД: без них недоступный хост = зависание на минуты ---
    db_connect_timeout: float = (
        5.0  # установка соединения (TCP+TLS+auth), сек; дефолт asyncpg = 60
    )
    db_command_timeout: float = (
        35.0  # страховка клиента; серверный statement_timeout = 30 с (context.py)
    )
    db_pool_recycle: int = 300  # Supavisor/NAT молча рвут простаивающие соединения

    redis_url: str = "redis://127.0.0.1:6379/0"
    # Только для legacy-проектов с HS256. Пусто -> проверка подписи через JWKS.
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"

    # --- Stripe. Всё необязательное: без ключей вебхук закрыт (503), checkout недоступен. ---
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = (
        None  # whsec_..., отдельный для каждого endpoint/режима
    )
    stripe_price_pro: str | None = None  # price_...
    # Отдельный DSN роли billing_service (EXECUTE только на app.billing_*). НЕ тот же, что database_url.
    billing_database_url: str | None = None
    # Отдельный DSN роли apikey_service (EXECUTE только на app.resolve_api_key). НЕ тот же, что database_url.
    apikey_database_url: str | None = None
    # --- LLM (Gemini). Без ключа воркер остаётся на эвристике по рейтингу (is_analyzed=false). ---
    gemini_api_key: SecretStr | None = None
    gemini_model: str = (
        "gemini-2.5-flash"  # проверь актуальное имя модели в консоли Google AI Studio
    )
    llm_call_timeout_s: float = 25.0  # один вызов LLM, включая сетевые ожидания
    llm_concurrency: int = (
        8  # одновременных вызовов на процесс воркера (лимит RPM/квоты Gemini)
    )
    # --- Telegram-алерты (Enterprise). Без токена Telegram-канал просто отключён, ARQ-конвейер не затрагивается. ---
    telegram_bot_token: SecretStr | None = None
    telegram_timeout_s: float = 5.0
    app_base_url: str = "http://localhost:5173"  # для success/cancel URL checkout


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg, unused-ignore]
