"""
Rate Limiter для защиты критичных API эндпоинтов Tenable SERM.

Двухуровневая защита:
1. Rate Limiting (429) — защита от спама: X запросов в Y секунд на tenant_id
2. Quota Check (402) — защита тарифа: проверка лимитов billing plan

Архитектура:
- Redis для хранения счетчиков (быстрое истечение TTL)
- Sliding Window Counter algorithm для точного rate limiting
- Интеграция с billing_deps для проверки квот
"""

import math
import time
from uuid import UUID

import jwt
import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_keys import resolve_api_key_tenant_id
from app.core.auth import decode_token, get_auth_config, get_current_tenant
from app.core.config import get_settings
from app.core.dependencies import get_tenant_db

# ============================================================================
# Redis Connection Pool
# ============================================================================

_redis_pool: redis.ConnectionPool | None = None


async def get_redis_pool() -> redis.ConnectionPool:
    """Singleton для пула Redis подключений."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def get_redis() -> redis.Redis:
    """Dependency для получения Redis клиента."""
    pool = await get_redis_pool()
    return redis.Redis(connection_pool=pool)


# ============================================================================
# Rate Limiting Logic
# ============================================================================


class RateLimitExceeded(HTTPException):
    """429 Too Many Requests — клиент превысил лимит запросов."""

    def __init__(
        self,
        limit: int,
        window: int,
        retry_after: int,
        tenant_id: UUID | None = None,
    ):
        detail = {
            "error": "Rate Limit Exceeded",
            "message": f"Превышен лимит {limit} запросов за {window} секунд.",
            "limit": limit,
            "window": window,
            "retry_after": retry_after,
        }
        if tenant_id:
            detail["tenant_id"] = str(tenant_id)

        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


class RateLimiter:
    """
    Sliding Window Rate Limiter на базе Redis.

    Алгоритм:
    1. Каждый запрос пишет timestamp в Redis Sorted Set (ключ: rate_limit:{tenant}:{endpoint})
    2. Удаляем записи старше окна (window)
    3. Считаем количество запросов в окне
    4. Если > limit — бросаем 429

    Плюсы Sliding Window:
    - Точнее Fixed Window (нет burst на границе окна)
    - Эффективнее Token Bucket (меньше операций в Redis)
    """

    def __init__(
        self,
        limit: int,
        window: int = 60,
        redis_client: redis.Redis | None = None,
    ):
        """
        Args:
            limit: Максимальное количество запросов
            window: Временное окно в секундах (по умолчанию 60 сек)
            redis_client: Redis клиент (для тестов)
        """
        self.limit = limit
        self.window = window
        self._redis_client = redis_client

    async def _get_redis(self) -> redis.Redis:
        """Получить Redis клиент (либо переданный, либо из pool)."""
        if self._redis_client:
            return self._redis_client
        return await get_redis()

    async def check_rate_limit(
        self,
        tenant_id: UUID,
        endpoint: str,
    ) -> tuple[int, int]:
        """
        Проверить rate limit для tenant + endpoint.

        Args:
            tenant_id: ID организации (изоляция по tenant)
            endpoint: Имя эндпоинта (например, "parse_reviews" или "llm_analysis")

        Returns:
            (current_count, remaining): текущее кол-во запросов и остаток

        Raises:
            RateLimitExceeded: если лимит превышен
        """
        r = await self._get_redis()
        key = f"rate_limit:{tenant_id}:{endpoint}"
        now = time.time()
        window_start = now - self.window

        # Pipeline для атомарности операций
        pipe = r.pipeline()

        # 1. Удаляем устаревшие записи (старше окна)
        pipe.zremrangebyscore(key, "-inf", window_start)

        # 2. Добавляем текущий запрос
        pipe.zadd(key, {str(now): now})

        # 3. Считаем количество запросов в окне
        pipe.zcard(key)

        # 4. Устанавливаем TTL на ключ (самоочистка через window + 10 сек)
        pipe.expire(key, self.window + 10)

        # Выполняем pipeline
        results = await pipe.execute()
        current_count = results[2]  # результат ZCARD

        # Проверяем лимит
        if current_count > self.limit:
            # Вычисляем retry_after (когда освободится слот)
            oldest_timestamps = await r.zrange(key, 0, 0, withscores=True)
            if oldest_timestamps:
                oldest_time = oldest_timestamps[0][1]
                retry_after = int(oldest_time + self.window - now) + 1
            else:
                retry_after = self.window

            raise RateLimitExceeded(
                limit=self.limit,
                window=self.window,
                retry_after=retry_after,
                tenant_id=tenant_id,
            )

        remaining = max(0, self.limit - current_count)
        return current_count, remaining


# ============================================================================
# FastAPI Dependencies
# ============================================================================


class RateLimitDependency:
    """
    FastAPI dependency applying a shared per-tenant or per-IP fixed-window limit.
    """

    def __init__(
        self,
        limit: int | None = None,
        window: int = 60,
        endpoint: str | None = None,
    ):
        self.authenticated_limit = 100 if limit is None else limit
        self.anonymous_limit = 20 if limit is None else limit
        self.window = window
        self.endpoint = endpoint

    @staticmethod
    def _get_tenant_id(request: Request) -> UUID | None:
        authorization = request.headers.get("authorization", "").split()
        if len(authorization) != 2 or authorization[0].lower() != "bearer":
            return None

        try:
            payload = decode_token(authorization[1], get_auth_config())
        except (jwt.PyJWTError, ValidationError):
            return None
        return payload.tenant_id or payload.sub

    async def __call__(self, request: Request) -> None:
        if not request.url.path.startswith("/api/"):
            return

        tenant_id: UUID | None
        if request.headers.get("x-api-key"):
            tenant_id = await resolve_api_key_tenant_id(request)
            scope = "api"
        else:
            tenant_id = self._get_tenant_id(request)
            scope = "dashboard" if tenant_id is not None else "anon"
        authenticated = tenant_id is not None
        limit = self.authenticated_limit if authenticated else self.anonymous_limit
        client_ip = request.client.host if request.client else "unknown"
        identity = str(tenant_id) if authenticated else client_ip
        endpoint_scope = f":{self.endpoint}" if self.endpoint else ""
        now = time.time()
        bucket = int(now // self.window)
        window_end = (bucket + 1) * self.window
        key = f"rate_limit:{identity}:{scope}{endpoint_scope}:{bucket}"

        pool = getattr(request.app.state, "redis_pool", None)
        if pool is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limit storage is unavailable",
            )

        pipe = pool.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, self.window + 1)
        results = await pipe.execute()
        current = int(results[0])
        remaining = max(0, limit - current)
        retry_after = max(1, math.ceil(window_end - now))

        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(window_end)),
        }

        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )


# ============================================================================
# Combined: Rate Limit + Quota Check
# ============================================================================


async def check_parser_limits(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> dict:
    """
    Комбинированная проверка для парсера:
    1. Rate Limit (429) — защита от спама: 5 запросов / 60 секунд
    2. Quota Check (402) — проверка тарифа через billing_deps

    Порядок проверок:
    1. Сначала rate limit (дешевле, только Redis)
    2. Потом квота (дороже, запрос в Postgres)

    Использование:
        @app.post("/api/parser/parse")
        async def parse_reviews(
            limits: dict = Depends(check_parser_limits),
            ...
        ):
            # limits = {"rate": {...}, "quota": {...}}
    """
    from app.core.billing_deps import check_quota

    # 1. Rate Limit (Redis): макс 5 запусков парсера за минуту
    limiter = RateLimiter(limit=5, window=60)
    rate_current, rate_remaining = await limiter.check_rate_limit(
        tenant_id=tenant_id,
        endpoint="parse_reviews",
    )

    # 2. Quota Check (Postgres): проверяем лимит тарифного плана
    quota_info = await check_quota(db=db, tenant_id=tenant_id)

    # Возвращаем объединенную информацию
    return {
        "rate": {
            "current": rate_current,
            "remaining": rate_remaining,
            "limit": 5,
            "window": 60,
        },
        "quota": quota_info,
    }


async def check_llm_limits(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> dict:
    """
    Комбинированная проверка для LLM-анализа:
    1. Rate Limit (429) — 20 запросов / 60 секунд (LLM дороже, но быстрее парсинга)
    2. Quota Check (402) — проверка тарифа

    Использование:
        @app.post("/api/reviews/analyze")
        async def analyze_reviews(
            limits: dict = Depends(check_llm_limits),
            ...
        ):
            ...
    """
    from app.core.billing_deps import check_quota

    # 1. Rate Limit: макс 20 LLM-запросов за минуту
    limiter = RateLimiter(limit=20, window=60)
    rate_current, rate_remaining = await limiter.check_rate_limit(
        tenant_id=tenant_id,
        endpoint="llm_analysis",
    )

    # 2. Quota Check
    quota_info = await check_quota(db=db, tenant_id=tenant_id)

    return {
        "rate": {
            "current": rate_current,
            "remaining": rate_remaining,
            "limit": 20,
            "window": 60,
        },
        "quota": quota_info,
    }


# ============================================================================
# Response Middleware для добавления Rate Limit заголовков
# ============================================================================


async def add_rate_limit_headers(request: Request, call_next):
    """
    Middleware для автоматического добавления X-RateLimit-* заголовков в ответ.

    Использование в main.py:
        app.middleware("http")(add_rate_limit_headers)
    """
    response = await call_next(request)

    # Если RateLimitDependency установила заголовки
    if hasattr(request.state, "rate_limit_headers"):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value

    return response


# ============================================================================
# Утилиты для тестирования и мониторинга
# ============================================================================


async def get_rate_limit_status(
    tenant_id: UUID,
    endpoint: str,
    redis_client: redis.Redis | None = None,
) -> dict:
    """
    Получить текущий статус rate limit (для дебага/мониторинга).

    Returns:
        {
            "current": 3,
            "limit": 5,
            "remaining": 2,
            "window": 60,
            "resets_at": 1704067200
        }
    """
    r = redis_client or await get_redis()
    limiter = RateLimiter(limit=5, window=60, redis_client=r)

    key = f"rate_limit:{tenant_id}:{endpoint}"
    now = time.time()
    window_start = now - limiter.window

    # Чистим устаревшие + считаем текущие
    await r.zremrangebyscore(key, "-inf", window_start)
    current = await r.zcard(key)

    # Время сброса счетчика (когда истечет самая старая запись)
    oldest = await r.zrange(key, 0, 0, withscores=True)
    resets_at = (
        int(oldest[0][1] + limiter.window) if oldest else int(now + limiter.window)
    )

    return {
        "current": current,
        "limit": limiter.limit,
        "remaining": max(0, limiter.limit - current),
        "window": limiter.window,
        "resets_at": resets_at,
    }


async def reset_rate_limit(
    tenant_id: UUID,
    endpoint: str,
    redis_client: redis.Redis | None = None,
):
    """Сбросить rate limit для tenant + endpoint (для админки/тестов)."""
    r = redis_client or await get_redis()
    key = f"rate_limit:{tenant_id}:{endpoint}"
    await r.delete(key)
