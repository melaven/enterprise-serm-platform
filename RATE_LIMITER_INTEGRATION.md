# Rate Limiter Integration Guide

## 📋 Обзор

Система защиты API Tenable SERM от спама и превышения квот на основе Redis.

### Двухуровневая защита

1. **Rate Limiting (429)** — Защита от спама запросами
   - Redis Sorted Set с Sliding Window алгоритмом
   - Точный подсчет запросов в временном окне
   - Автоматическая очистка устаревших записей

2. **Quota Check (402)** — Защита тарифного плана
   - PostgreSQL проверка лимитов billing plan
   - Интеграция с `organization_quotas` таблицей
   - Атомарное списание через `consume_request()`

---

## 🔧 Установка зависимостей

```bash
# Redis client для Python
pip install redis[hiredis]

# Уже установлено в проекте:
# - fastapi
# - sqlalchemy
# - arq (использует redis тоже)
```

---

## 🚀 Быстрый старт

### 1. Добавить Rate Limiter в эндпоинт

```python
from fastapi import APIRouter, Depends
from app.core.rate_limit import check_parser_limits, check_llm_limits

router = APIRouter()

# Парсер: 5 запросов / 60 секунд
@router.post("/api/v1/parsers/start")
async def start_parser(
    limits: dict = Depends(check_parser_limits),
    # ... остальные dependencies
):
    # limits = {
    #   "rate": {"current": 3, "remaining": 2, "limit": 5, "window": 60},
    #   "quota": {"used": 150, "limit": 1000}
    # }
    pass

# LLM-анализ: 20 запросов / 60 секунд
@router.post("/api/v1/reviews/analyze")
async def analyze_reviews(
    limits: dict = Depends(check_llm_limits),
    # ...
):
    pass
```

### 2. Кастомный Rate Limit

```python
from app.core.rate_limit import RateLimitDependency

# 10 запросов в 30 секунд
@router.post(
    "/api/custom/endpoint",
    dependencies=[Depends(RateLimitDependency(limit=10, window=30))]
)
async def custom_endpoint():
    pass
```

### 3. Программная проверка лимита

```python
from app.core.rate_limit import RateLimiter, RateLimitExceeded

async def manual_check():
    limiter = RateLimiter(limit=100, window=3600)
    
    try:
        current, remaining = await limiter.check_rate_limit(
            tenant_id=tenant_uuid,
            endpoint="custom_operation"
        )
        print(f"Использовано: {current}/{limiter.limit}")
    except RateLimitExceeded as e:
        print(f"Лимит превышен! Retry after: {e.headers['Retry-After']} сек")
```

---

## 📊 Архитектура

### Sliding Window Algorithm

```
Временная шкала (60 секунд):

[--------------------окно-------------------]
  ^      ^    ^       ^         ^         now
  req1  req2 req3    req4      req5

1. Каждый запрос → ZADD с timestamp
2. Удаляем записи старше (now - window)
3. Считаем ZCARD (количество в окне)
4. Если > limit → 429 Too Many Requests
```

### Redis Keys Structure

```
rate_limit:{tenant_id}:{endpoint} → Sorted Set
  - member: timestamp (str)
  - score: timestamp (float)
  - TTL: window + 10 секунд (самоочистка)
```

### Пример Redis данных

```redis
# Tenant f47ac10b..., endpoint parse_reviews
ZRANGE rate_limit:f47ac10b-58cc-4372-a567-0e02b2c3d479:parse_reviews 0 -1 WITHSCORES

1) "1704067200.123"  # member (timestamp)
2) "1704067200.123"  # score
3) "1704067205.456"
4) "1704067205.456"
5) "1704067210.789"
6) "1704067210.789"
# Total: 3 requests в окне
```

---

## 🔒 Интеграция с Billing

### Порядок проверок

```python
async def check_parser_limits(
    tenant_id: UUID,
    db: AsyncSession,
):
    # 1. Rate Limit (быстро, Redis)
    #    ❌ 429 Too Many Requests
    limiter = RateLimiter(limit=5, window=60)
    await limiter.check_rate_limit(tenant_id, "parse_reviews")
    
    # 2. Quota Check (медленнее, Postgres)
    #    ❌ 402 Payment Required
    from app.core.billing_deps import check_quota
    quota = await check_quota(db=db, tenant_id=tenant_id)
    
    return {"rate": {...}, "quota": quota}
```

### Атомарное списание квоты

```python
from app.core.billing_deps import consume_request

# ПОСЛЕ успешной операции списываем квоту
async def after_successful_parse():
    await consume_request(
        db=db,
        tenant_id=tenant_id,
        amount=1  # списать 1 запрос
    )
```

---

## 📡 HTTP Headers

### Response Headers (автоматически)

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 2
X-RateLimit-Reset: 1704067260
```

### 429 Too Many Requests

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
Content-Type: application/json

{
  "detail": {
    "error": "Rate Limit Exceeded",
    "message": "Превышен лимит 5 запросов за 60 секунд.",
    "limit": 5,
    "window": 60,
    "retry_after": 45,
    "tenant_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
  }
}
```

### 402 Payment Required

```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "detail": {
    "error": "Quota Exceeded",
    "used": 1000,
    "limit": 1000
  }
}
```

---

## 🧪 Тестирование

### Postman Collection

```json
{
  "name": "Rate Limit Tests",
  "item": [
    {
      "name": "Parser Rate Limit - Success",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/api/v1/parsers/start",
        "header": [
          {"key": "Authorization", "value": "Bearer {{jwt_token}}"}
        ],
        "body": {
          "url": "https://www.trustpilot.com/review/example.com"
        }
      },
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test('Status 200', () => pm.response.to.have.status(200));",
              "pm.test('Has rate limit headers', () => {",
              "  pm.response.to.have.header('X-RateLimit-Limit');",
              "  pm.response.to.have.header('X-RateLimit-Remaining');",
              "});"
            ]
          }
        }
      ]
    },
    {
      "name": "Parser Rate Limit - Exceed (429)",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/api/v1/parsers/start",
        "header": [
          {"key": "Authorization", "value": "Bearer {{jwt_token}}"}
        ]
      },
      "event": [
        {
          "listen": "prerequest",
          "script": {
            "exec": [
              "// Отправить 6 запросов подряд для триггера 429",
              "for (let i = 0; i < 6; i++) {",
              "  pm.sendRequest(pm.request.url, (err, res) => {});",
              "}"
            ]
          }
        },
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test('Status 429', () => pm.response.to.have.status(429));",
              "pm.test('Has Retry-After header', () => {",
              "  pm.response.to.have.header('Retry-After');",
              "});",
              "pm.test('Error message correct', () => {",
              "  const body = pm.response.json();",
              "  pm.expect(body.detail.error).to.eql('Rate Limit Exceeded');",
              "});"
            ]
          }
        }
      ]
    }
  ]
}
```

### Python Unit Tests

```python
import pytest
from app.core.rate_limit import RateLimiter, RateLimitExceeded
from uuid import uuid4

@pytest.mark.asyncio
async def test_rate_limit_within_threshold(redis_client):
    tenant_id = uuid4()
    limiter = RateLimiter(limit=5, window=60, redis_client=redis_client)
    
    # 5 запросов должны пройти
    for i in range(5):
        current, remaining = await limiter.check_rate_limit(tenant_id, "test")
        assert current == i + 1
        assert remaining == 5 - (i + 1)

@pytest.mark.asyncio
async def test_rate_limit_exceed_threshold(redis_client):
    tenant_id = uuid4()
    limiter = RateLimiter(limit=3, window=60, redis_client=redis_client)
    
    # Первые 3 запроса проходят
    for _ in range(3):
        await limiter.check_rate_limit(tenant_id, "test")
    
    # 4-й запрос должен вызвать исключение
    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.check_rate_limit(tenant_id, "test")
    
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers
```

---

## 🛠️ Утилиты и мониторинг

### Проверка статуса Rate Limit

```python
from app.core.rate_limit import get_rate_limit_status

status = await get_rate_limit_status(
    tenant_id=tenant_uuid,
    endpoint="parse_reviews"
)

# {
#   "current": 3,
#   "limit": 5,
#   "remaining": 2,
#   "window": 60,
#   "resets_at": 1704067260
# }
```

### Сброс Rate Limit (для админки)

```python
from app.core.rate_limit import reset_rate_limit

# Сбросить лимит для tenant
await reset_rate_limit(
    tenant_id=tenant_uuid,
    endpoint="parse_reviews"
)
```

### Admin Endpoint (опционально)

```python
from fastapi import APIRouter, Depends
from app.core.rate_limit import reset_rate_limit, get_rate_limit_status
from app.core.auth import require_admin  # ваша админ-проверка

admin_router = APIRouter(prefix="/admin")

@admin_router.get("/rate-limits/{tenant_id}/{endpoint}")
async def get_limits(
    tenant_id: UUID,
    endpoint: str,
    admin: bool = Depends(require_admin)
):
    return await get_rate_limit_status(tenant_id, endpoint)

@admin_router.delete("/rate-limits/{tenant_id}/{endpoint}")
async def reset_limits(
    tenant_id: UUID,
    endpoint: str,
    admin: bool = Depends(require_admin)
):
    await reset_rate_limit(tenant_id, endpoint)
    return {"status": "reset"}
```

---

## ⚙️ Конфигурация

### Environment Variables

```bash
# Redis для Rate Limiter (тот же, что для ARQ)
REDIS_URL=redis://localhost:6379/0

# Production:
REDIS_URL=rediss://:password@redis.example.com:6379/0
```

### Rate Limit параметры по эндпоинтам

```python
# app/core/rate_limit.py

RATE_LIMITS = {
    "parse_reviews": {"limit": 5, "window": 60},      # Парсер: 5 req/min
    "llm_analysis": {"limit": 20, "window": 60},      # LLM: 20 req/min
    "export_data": {"limit": 10, "window": 3600},     # Экспорт: 10 req/hour
    "api_general": {"limit": 100, "window": 60},      # Общий API: 100 req/min
}
```

---

## 🚨 Обработка ошибок

### Frontend (TypeScript)

```typescript
import axios, { AxiosError } from 'axios';

try {
  const response = await axios.post('/api/v1/parsers/start', data, {
    headers: { Authorization: `Bearer ${token}` }
  });
} catch (error) {
  const axiosError = error as AxiosError;
  
  if (axiosError.response?.status === 429) {
    const retryAfter = axiosError.response.headers['retry-after'];
    toast.error(`Слишком много запросов. Повторите через ${retryAfter} секунд.`);
  } else if (axiosError.response?.status === 402) {
    toast.error('Квота исчерпана. Обновите тарифный план.');
    // Redirect to billing page
    router.push('/billing');
  }
}
```

### Backend (Python)

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.rate_limit import RateLimitExceeded

app = FastAPI()

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )
```

---

## 📈 Production Best Practices

### 1. Monitoring

```python
import structlog

logger = structlog.get_logger()

# Логируем все 429 ответы
@app.middleware("http")
async def log_rate_limits(request: Request, call_next):
    response = await call_next(request)
    
    if response.status_code == 429:
        logger.warning(
            "rate_limit_exceeded",
            tenant_id=request.state.tenant_id,
            endpoint=request.url.path,
            headers=dict(response.headers)
        )
    
    return response
```

### 2. Redis High Availability

```python
# Использовать Redis Sentinel или Cluster
REDIS_URL = "redis-sentinel://sentinel1:26379,sentinel2:26379/mymaster/0"
```

### 3. Graceful Degradation

```python
from app.core.rate_limit import RateLimiter

async def check_with_fallback():
    try:
        limiter = RateLimiter(limit=5, window=60)
        await limiter.check_rate_limit(tenant_id, endpoint)
    except Exception as e:
        # Если Redis недоступен, пропускаем проверку (но логируем!)
        logger.error("rate_limiter_failure", error=str(e))
        # НЕ блокируем запрос
```

### 4. Distributed Rate Limiting

Rate Limiter автоматически работает в distributed окружении:
- Все API инстансы используют один Redis
- Sliding Window синхронизирован через Redis Sorted Sets
- Нет race conditions благодаря Redis pipeline atomicity

---

## 🔗 API Reference

### `RateLimiter`

```python
class RateLimiter:
    def __init__(
        self,
        limit: int,           # Макс. запросов в окне
        window: int = 60,     # Окно в секундах
        redis_client: Optional[redis.Redis] = None
    )
    
    async def check_rate_limit(
        self,
        tenant_id: UUID,      # ID организации
        endpoint: str,        # Имя эндпоинта
    ) -> tuple[int, int]:    # (current_count, remaining)
```

### Dependencies

```python
# Комбинированная проверка (Rate + Quota)
check_parser_limits: dict = Depends(...)  # 5 req/min
check_llm_limits: dict = Depends(...)     # 20 req/min

# Только Rate Limit
RateLimitDependency(limit=10, window=30)
```

### Utilities

```python
async def get_rate_limit_status(...) -> dict
async def reset_rate_limit(...)
async def add_rate_limit_headers(request, call_next)  # middleware
```

---

## 📝 Changelog

### 2026-10-13
- ✅ Создан `app/core/rate_limit.py`
- ✅ Sliding Window Rate Limiter на Redis
- ✅ Интеграция с `billing_deps.check_quota`
- ✅ `check_parser_limits()` и `check_llm_limits()`
- ✅ X-RateLimit-* headers middleware
- ✅ Утилиты для мониторинга и тестирования
- ✅ Документация и примеры интеграции

---

## 🤝 Контрибьютинг

При добавлении новых защищенных эндпоинтов:

1. Определите лимит и окно для эндпоинта
2. Добавьте `Depends(check_*_limits)` или `RateLimitDependency`
3. Обновите Postman коллекцию с тестами на 429
4. Добавьте обработку ошибок во фронтенде
5. Обновите этот документ

---

**Вопросы?** Проверьте код в `app/core/rate_limit.py` или создайте issue.
