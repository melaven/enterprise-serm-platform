# Tenable SERM

**B2B SaaS для управления репутацией (SERM): собирает отзывы с площадок, размечает их Sentiment Intelligence и отвечает на негатив.**

`FastAPI` · `PostgreSQL + RLS` · `Redis / ARQ` · `React + TypeScript` · `Stripe` · `Terraform + GitHub Actions + k6`

> Это MVP, но инженерные решения принимались так, как принимают их для платёжной многоарендной системы:
> изоляция данных на уровне СУБД, атомарная квота, идемпотентные очереди и вебхуки, сквозная трассировка, Zero Trust по умолчанию.
> Раздел [Статус](#статус-что-реализовано-а-что-нет) честно разделяет «работает и проверено», «написано, не подключено» и «спроектировано».

[🇬🇧 English version](README.en.md)

---

## Что делает продукт

| Для кого | Что получает |
|---|---|
| **Владелец бизнеса** (рестораны, e-commerce, HoReCa) | Сбор отзывов (Google, Яндекс, 2GIS, Otzovik), тональность и теги, черновики ответов на негатив, дашборд репутации |

**Монетизация.** Free (жёсткая квота) → Pro (Stripe-подписка). Квота — не маркетинг, а инвариант БД: исчерпал лимит — получил `402 Payment Required` с данными для paywall-а.

**Чего продукт не делает намеренно:** не удаляет честные отзывы и не обещает этого (только жалобы на нарушения правил площадок), не накручивает рейтинг.

---

## Архитектура

```
Browser (React + TypeScript + Zustand)
   |
   |  Bearer JWT (from Supabase Auth)
   |  Protected routes with auto-logout on 401
   v
+------------------+
| FastAPI API      |  PostgreSQL connection with pgbouncer compatibility
| (uvicorn)        |  (statement_cache_size=0, unique prepared statement names)
|                  |
| - JWT validation |  RLS context set per request: app.company_id, app.user_id
| - Quota checks   |  Atomic quota operations via SQL functions
| - Rate limiting  |  Tenant isolation enforced by database policies
+--------+---------+
         |
         |  asyncpg driver with NullPool
         |  (no connection reuse across requests)
         v
+------------------------------------------+
| PostgreSQL (Supabase)                    |
| - Row Level Security on all tables       |
| - tenant_quotas with atomic operations   |
| - RLS policies filter by company_id      |
| - Prepared statement compatibility       |
+------------------------------------------+
```

**Key constraints:**
- PostgreSQL required (SQLite is not supported)
- Connection pooler compatibility: `statement_cache_size=0` prevents prepared statement conflicts with pgbouncer/Supavisor
- Database initialization strict: server refuses to start if connection fails (no silent fallback)
- Tenant isolation: RLS context set on every request, enforced by PostgreSQL policies

---

## Ключевые инженерные решения

**1. Изоляция арендаторов в СУБД, а не в `WHERE`.**
Каждая запрос-транзакция начинается с `set_config('app.current_tenant_id', …, true)`; политики RLS отсекают чужие строки даже при ошибке в коде приложения. `company_id` берётся только из подписанного JWT (custom access token hook), не из тела запроса. Роль вебхука биллинга отделена и умеет вызывать только `app.billing_*`.

**2. Конкурентность без advisory locks.**
Гонки закрыты атомарными инструкциями и ограничениями, а не блокировками сессии:
- квота: `UPDATE … WHERE used + :n <= limit RETURNING` в одном выражении (резерв **до** парсинга, возврат излишка после);
- дубль задачи: детерминированный `job_id` (company + платформа + хеш URL) → второй клик получает `409`;
- дубль отзыва: `ON CONFLICT DO NOTHING` на уникальном ключе;
- дубль вебхука: `event_id` — PRIMARY KEY, запись события и применение — одна транзакция.

Почему не advisory locks: через пулер Supavisor в transaction-режиме session-level блокировки небезопасны (соединение может смениться между запросами), а xact-level держат соединение и усложняют пул. Атомарный SQL проще, быстрее и проверяем тестом.

**3. SSE-реалтайм прогресса задач.**
Статус задачи парсинга приходит в браузер потоком `text/event-stream`, а не опросом: нативная реализация в `app/routers/parser.py`. Поток авторизуется той же HttpOnly-cookie (EventSource не умеет ставить заголовок `Authorization` — ещё один довод за cookie-сессии). Клиентский опрос `waitForJob` остаётся как фолбэк для сетей, режущих потоки.

**4. Zero Trust.**
HttpOnly + `__Host-` cookie с подписанным double-submit CSRF (токены недоступны JS), строгие заголовки (CSP, HSTS, nosniff, frame-ancestors), HMAC-псевдонимизация PII с версионируемым pepper и TTL, SSRF-защита (allowlist хостов площадок, проверка **каждого** редиректа, запрет приватных/служебных адресов; DNS-ребиндинг закрывается резолвером и egress-политикой), изоляция воркеров по сетям и ролям БД.

**5. Stripe-биллинг как конечный автомат.**
Подпись вебхука проверяется `stripe.Webhook.construct_event` по сырым байтам (окно 5 мин против replay) **до** любого разбора и обращения к БД. План меняется только подписанным событием; Pro без Stripe-подписки запрещён CHECK-ограничением. Запоздавшие и пришедшие не по порядку события безопасны.

**6. Сквозная трассировка.**
`X-Correlation-ID` проходит браузер → API → задача ARQ → воркер → JSON-логи; клиент показывает «ID запроса» в ошибке, поддержка находит весь путь одним поиском.

**7. Деградация вместо падения.**
LLM за circuit breaker-ом, «ядовитый» отзыв изолируется бисекцией пачки, отзывы без разметки получают `ai_pending` и дообрабатываются фоновым cron-ом с lease (`FOR UPDATE SKIP LOCKED`).

---

## Статус: что реализовано, а что нет

Мы не называем систему «готовой к нагрузке», пока нет цифр. Ниже — что реально лежит в репозитории.

| Область | Статус | Проверка |
|---|---|---|
| Мультиарендность, RLS, tenant-сессии, атомарная квота (SQL 001–012b) | Реализовано | SQL-смоук-тест в репозитории; 008 и 013 применены и проверены на PostgreSQL 16 |
| Очередь ARQ, идемпотентная постановка, ретраи AI, трассировка | Реализовано | Юнит-тесты `tests/core`, `parser_worker` |
| Stripe: схема, вебхук с подписью, checkout, 402-гейт | Реализовано | SQL проверен на PG16; логика событий — 14 тестов; тест подписи на реальном SDK написан, ждёт окружения со `stripe` |
| SSE-стриминг прогресса задач | Реализовано | Нативно в `app/routers/parser.py`; интеграционный тест потока с Redis — в планах |
| React-клиент: дизайн-токены, дашборд, 401/402/429-интерсепторы, polling-фолбэк | Реализовано | Vitest-тесты API-слоя |
| SSRF: allowlist площадок + проверка каждого редиректа в скрейпере | Реализовано | `tests/services/scrapers/test_ssrf.py` |
| Zero Trust (cookie/CSRF, заголовки, PII-хеширование, DNS-резолвер SSRF, nginx) | Написано, **не подключено** | `hardening/`; PII/SSRF/OpSec прогнаны, middleware и cookie-auth требуют интеграционного теста |
| IaC и CI/CD (Terraform, GitHub Actions, Trivy, k6) | Написано, **не запускалось** | `devops/`; нужен `terraform validate` и прогон пайплайна |
| Нагрузочные цифры (RPS, p95, ёмкость пула) | **Нет данных** | Сценарий k6 готов; результаты появятся после прогона на staging |

Известные пробелы (не скрываем): несколько каталогов (`billing/`, `billing_v2/`, `parsers/`, `dlq/`, `llm/`, `obs/`, `tenant/`, `analytics_api/`) — итерации модулей, которые консолидируются в `app/` и `parser_worker/`.

---

## Карта репозитория

```
app/               FastAPI: `main.py`, роутеры (parser + SSE-стриминг, reviews, billing, webhooks), core (security, tracing), db, services
parser_worker/     ARQ-воркер: скрапинг, AI-обогащение, ретраи, интеграция с квотами
sql/               миграции: RLS, quota-функции, hardening, 013 Stripe
redesign/          React + TypeScript + Tailwind: клиент, дизайн-система
hardening/         Zero Trust: cookie-auth, CSRF, заголовки, PII, SSRF, nginx, изоляция
devops/            Terraform (Hetzner), docker-compose.prod, GitHub Actions, k6
tests/             pytest
SYSTEM_DESIGN.md   архитектура, инварианты, модель угроз, ADR
TRACING.md         сквозная трассировка
```

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 15+ (local or Supabase)
- Redis (optional, for background tasks)

### Environment Configuration

Copy example environment file and configure required variables:

```bash
cp .env.example .env
```

Required variables in `.env`:

```bash
# PostgreSQL connection (required)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database
TENANT_DATABASE_URL=postgresql+asyncpg://app_tenant:password@host:5432/database
USE_TENANT_ROLE=true

# Supabase configuration (for auth)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# AI provider (optional, for Sentiment Intelligence features)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash

# Redis (optional, for background workers)
REDIS_URL=redis://localhost:6379/0
```

### Database Initialization

Apply migrations in order:

```bash
python scripts/migrate.py
```

This applies all SQL migrations from `migrations/` directory in sequence. The script is idempotent and tracks applied migrations in `serm_schema_migrations` table.

### Backend Startup

Install dependencies and start server:

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Expected startup log:
```
✅ Подключение к PostgreSQL установлено
   database_driver=postgresql+asyncpg
✅ Сервисы инициализированы
```

If PostgreSQL connection fails, server will refuse to start (no fallback to SQLite).

### Frontend Startup

Install dependencies and start development server:

```bash
cd frontend
npm install
npm run dev
```

Access at http://localhost:3000

### Verification

```bash
# Health check
curl http://127.0.0.1:8000/health

# API documentation
open http://127.0.0.1:8000/docs
```

### Testing

```bash
# Run backend tests
pytest

# Run frontend tests
cd frontend
npm test

# Linting
ruff check .  # Python
cd frontend && npm run lint  # TypeScript
```

---

## Нагрузка: что мы докажем и как

`devops/loadtest/k6-tenable.js` — 1000 виртуальных пользователей и четыре инварианта: ровно один `202` на дублирующий URL, `used ≤ limit` после гонки за квоту, отсутствие `5xx` при исчерпании пула соединений, отсутствие утечки данных между арендаторами. Пороги — стартовые гипотезы; результаты будут опубликованы здесь после прогона на staging.

## Лицензия и контакты

Maxim Nesterov — Backend & System Integration (https://t.me/melavenn) ❤️
