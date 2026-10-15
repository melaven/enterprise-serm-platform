"""PII-минимизация для 152-ФЗ / GDPR: псевдонимизация (HMAC-SHA256 + pepper) и TTL.

Принцип: хранить только то, что нужно для задачи.
  * Дедуп / «уже писали» / opt-out  -> хранится ТОЛЬКО HMAC-хеш (необратим без pepper).
  * Показать лид Матвею             -> сырой username живёт <= TTL (30 дн), затем затирается, хеш остаётся.
  * Авторы отзывов                  -> display name не нужен для аналитики: хранить хеш + первую букву.
Хеш без pepper (голый sha256 от username) НЕ защита: пространство имён мало, перебирается за минуты.
Pepper — в секрет-хранилище, НЕ в БД с данными; версия ключа в префиксе позволяет ротацию.
Важно: псевдонимизированные данные по GDPR остаются персональными; хеш снижает риск утечки, но не отменяет
правовое основание и право на удаление (для opt-out нужен хеш -> он и есть «список подавления»).
"""
from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass

_WS = re.compile(r"\s+")


def normalize_handle(value: str) -> str:
    v = unicodedata.normalize("NFKC", value).strip().lstrip("@").casefold()
    return _WS.sub("", v)


def normalize_name(value: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", value).strip().casefold())


@dataclass(frozen=True, slots=True)
class Pseudonymizer:
    peppers: dict[int, bytes]   # {1: b"...32+ bytes..."}; новые записи — current, чтение — любые версии
    current: int

    def __post_init__(self) -> None:
        if any(len(k) < 32 for k in self.peppers.values()):
            raise ValueError("pepper must be >= 32 bytes")

    def _h(self, version: int, namespace: str, value: str) -> str:
        mac = hmac.new(self.peppers[version], f"{namespace}\x00{value}".encode(), hashlib.sha256)
        return f"v{version}:{mac.hexdigest()}"

    def handle(self, username: str) -> str:
        return self._h(self.current, "tg_handle", normalize_handle(username))

    def handle_all_versions(self, username: str) -> list[str]:
        """Для lookup в период ротации ключей: проверять по всем версиям."""
        n = normalize_handle(username)
        return [self._h(v, "tg_handle", n) for v in self.peppers]

    def author(self, platform: str, name: str) -> str:
        return self._h(self.current, f"author:{platform}", normalize_name(name))


def mask_name(name: str) -> str:
    n = normalize_name(name)
    return (n[:1].upper() + "***") if n else ""


# ---- ARQ cron: затирание PII по TTL (Postgres) ----
PURGE_SQL = """
-- 1) сырые PII отзывов старше TTL: оставляем хеш, текст отзыва (публичный) и метрики
UPDATE reviews
   SET author_name = NULL, author_profile_url = NULL, pii_purged_at = now()
 WHERE pii_purged_at IS NULL
   AND created_at < now() - make_interval(days => $1);
-- 2) логи парсинга: сырой HTML/ответы могут содержать PII
DELETE FROM parsing_logs WHERE created_at < now() - make_interval(days => $2);
"""

MIGRATION_SQL = """
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS author_hash text,
  ADD COLUMN IF NOT EXISTS pii_purged_at timestamptz;
CREATE INDEX IF NOT EXISTS reviews_pii_ttl_idx ON reviews (created_at) WHERE pii_purged_at IS NULL;
-- Список подавления: только хеши, без TTL (его цель — не писать повторно)
CREATE TABLE IF NOT EXISTS suppression_list (
  handle_hash text PRIMARY KEY, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
-- RLS: сервисная роль worker'а видит только свои таблицы
ALTER TABLE suppression_list ENABLE ROW LEVEL SECURITY;
"""
