# Tenable SERM

**B2B SaaS dashboard for analytics on public business ratings and service-quality alerts.**

`FastAPI` · `PostgreSQL + RLS` · `Redis / ARQ` · `React + TypeScript` · `Stripe` · `Terraform + GitHub Actions + k6`

> This is an MVP, but engineering decisions were made as if building a payment-grade multi-tenant system:
> database-level data isolation, atomic quotas, idempotent queues and webhooks, end-to-end tracing, Zero Trust by default.
> The [Status](#status-whats-implemented-and-whats-not) section honestly separates "working and verified", "written but not connected", and "designed".

[🇷🇺 Русская версия](README.md)

---

## What the Product Does

| For Whom | What They Get |
|---|---|
| **Business Owner** (restaurants, e-commerce, HoReCa) | Sentiment, risk level, and a dashboard tracking public review trends |

**Data minimization.** Source text is analyzed in memory and is not stored in the database; `reviews` stores only a short summary derived from fixed analytics categories and rating. Author names are replaced with a generic label; external IDs, links, and free-form replies are not stored. Reply publishing is disabled.

Automatic public-page scraping is disabled. Reviews are retrieved through the authorized Google Business Profile integration; other sources may only be customer-provided or handled through a separately approved official integration. Replies are drafts and require human publication.

These are technical data-minimization measures, not legal advice or a guarantee that Russian Federal Law 152-FZ does not apply. The customer must establish a lawful basis and ensure submitted data may be provided; party roles depend on actual processing, and a contract does not remove the provider's own obligations. Counsel should review processing terms and notices.

**Monetization.** Free (hard quota) → Pro (Stripe subscription). Quota is not marketing — it's a database invariant: when limit is exhausted, client receives `402 Payment Required` with data for paywall.

**What the product intentionally does not do:** does not delete honest reviews and does not promise to (only complaints about platform policy violations), does not inflate ratings.

---

## Architecture

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

## Key Engineering Decisions

**1. Tenant isolation in database, not in `WHERE` clauses.**
Each request-transaction starts with `set_config('app.current_tenant_id', …, true)`; RLS policies filter out foreign rows even if application code contains bugs. `company_id` is extracted only from signed JWT (custom access token hook), never from request body. Billing webhook role is separate and can only call `app.billing_*` functions.

**2. Concurrency without advisory locks.**
Race conditions are closed by atomic instructions and constraints, not session locks:
- quota: `UPDATE … WHERE used + :n <= limit RETURNING` in single statement (reserve **before** parsing, return excess after);
- duplicate job: deterministic `job_id` (company + platform + URL hash) → second click gets `409`;
- source-ID deduplication is disabled; exact duplicate records are compared only by tenant, platform, publication date, rating, and safe summary;
- duplicate webhook: `event_id` as PRIMARY KEY, event recording and application in single transaction.

Why not advisory locks: through Supavisor pooler in transaction mode, session-level locks are unsafe (connection can change between requests), and xact-level locks hold connections and complicate pool. Atomic SQL is simpler, faster, and testable.

**3. Zero Trust.**
HttpOnly + `__Host-` cookie with signed double-submit CSRF (tokens inaccessible to JS), strict headers (CSP, HSTS, nosniff, frame-ancestors), HMAC pseudonymization for other PII identifiers (not review authors), SSRF protection (platform host allowlist, **every** redirect checked, private/service addresses blocked; DNS rebinding closed by resolver and egress policy), worker isolation by networks and database roles.

**4. Stripe billing as state machine.**
Webhook signature verified by `stripe.Webhook.construct_event` on raw bytes (5-min window against replay) **before** any parsing or database access. Plan changes only by signed event; Pro without Stripe subscription forbidden by CHECK constraint. Late or out-of-order events are safe.

**5. End-to-end tracing.**
`X-Correlation-ID` flows browser → API → ARQ task → worker → JSON logs; client shows "Request ID" in error, support finds entire path with single search.

**6. Degradation instead of failure.**
Sentiment Intelligence behind circuit breaker, "poisonous" review isolated by batch bisection, reviews without classification get `ai_pending` and are reprocessed by background cron with lease (`FOR UPDATE SKIP LOCKED`).

---

## Status: What's Implemented and What's Not

We don't call the system "load-ready" without numbers. Below is what's actually in the repository.

| Area | Status | Verification |
|---|---|---|
| Multi-tenancy, RLS, tenant sessions, atomic quota (SQL 001–012b) | Implemented | SQL smoke test in repo; 008 and 013 applied and verified on PostgreSQL 16 |
| ARQ queue, idempotent enqueue, SI retries, tracing | Implemented | Unit tests `tests/core`, `parser_worker` |
| Stripe: schema, signed webhook, checkout, 402 gate | Implemented | SQL verified on PG16; event logic — 14 tests; signature test with real SDK written, awaits `stripe` environment |
| React client: design tokens, dashboard, 401/402/429 interceptors, polling fallback | Implemented | Vitest tests for API layer |
| SSRF: platform allowlist + every redirect checked in scraper | Implemented | `tests/services/scrapers/test_ssrf.py` |
| Zero Trust (cookie/CSRF, headers, PII hashing, DNS resolver SSRF, nginx) | Written, **not connected** | `infra/hardening/`; PII/SSRF/OpSec run, middleware and cookie-auth require integration test |
| IaC and CI/CD (Terraform, GitHub Actions, Trivy, k6) | Written, **not run** | `infra/devops/`; needs `terraform validate` and pipeline run |
| Load numbers (RPS, p95, pool capacity) | **No data** | k6 scenario ready; results will appear after staging run |

Known gaps (not hiding): several directories (`billing/`, `billing_v2/`, `parsers/`, `dlq/`, `llm/`, `obs/`, `tenant/`, `analytics_api/`) are module iterations being consolidated into `app/` and `parser_worker/`.

---

## Repository Map

```
app/               FastAPI: main.py, routers (parser, reviews, billing, webhooks), core (security, tracing), db, services
parser_worker/     ARQ worker: scraping, SI enrichment, retries, quota integration
migrations/         SQL migrations: RLS, quota functions, hardening, Stripe
redesign/          React + TypeScript + Tailwind: client, design system
infra/hardening/   Zero Trust: cookie-auth, CSRF, headers, PII, SSRF, nginx, isolation
infra/devops/      Terraform (Hetzner), docker-compose.prod, GitHub Actions, k6
tests/             pytest
SYSTEM_DESIGN.md   architecture, invariants, threat model, ADR
TRACING.md         end-to-end tracing
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

# SI provider (optional, for Sentiment Intelligence features)
GROQ_API_KEY=your-groq-api-key
LLM_MODEL=openai/gpt-oss-20b

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
pip install .

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

## Load Testing: What We Will Prove and How

`infra/devops/loadtest/k6-tenable.js` — 1000 virtual users and four invariants: exactly one `202` for duplicate URL, `used ≤ limit` after quota race, no `5xx` on connection pool exhaustion, no data leakage between tenants. Thresholds are initial hypotheses; results will be published here after staging run.

## License and Contacts

License: not determined (specify before publication). Maxim Nesterov — Backend & System Integration.
