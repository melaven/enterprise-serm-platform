from uuid import UUID

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Читает .env (общий с бэкендом); все переменные бота с префиксом TG_."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TG_", extra="ignore")

    bot_token: SecretStr
    # 127.0.0.1, а не localhost: на Windows localhost может уйти в IPv6 (::1).
    api_base_url: str = "http://127.0.0.1:8000"
    # Хардкодный тестовый тенант. Замени на реальный company_id своей компании.
    company_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    # Если бэкенд требует токен: уйдёт как "Authorization: Bearer ...".
    api_token: SecretStr | None = None

    poll_interval: float = 3.0  # сек между опросами статуса
    poll_timeout: float = 300.0  # сколько ждать автоматически, потом только кнопка

    # Telegram user id через запятую. Пусто = бот открыт всем (только для тестов:
    # любой пользователь запускает задачи от имени тестовой компании).
    allowed_user_ids: str = ""

    @property
    def allowed_ids(self) -> frozenset[int]:
        return frozenset(
            int(part) for part in self.allowed_user_ids.split(",") if part.strip()
        )
