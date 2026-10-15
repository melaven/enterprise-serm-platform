# Backend architecture

The backend is organized around API, business logic, persistence, and shared
infrastructure boundaries. `app/main.py` composes the FastAPI application;
routers validate HTTP input and delegate work, services own business logic and
background processing, and repositories isolate database access.

```text
app/
├── core/
│   ├── auth.py
│   ├── auth_session.py
│   ├── billing_deps.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── exceptions.py
│   ├── handlers.py
│   ├── jwt_handler.py
│   ├── llm_cache.py
│   ├── logger.py
│   ├── middleware.py
│   ├── rate_limit.py
│   ├── tenant.py
│   ├── tenant_session.py
│   └── tracing.py
├── models/
│   ├── __init__.py
│   └── economics.py
├── repositories/
│   ├── __init__.py
│   ├── analytics_repo.py
│   ├── base.py
│   ├── company.py
│   ├── dlq.py
│   ├── parser.py
│   ├── platform.py
│   ├── postgres_review_sink.py
│   └── review.py
├── routers/
│   ├── __init__.py
│   ├── analytics.py
│   ├── auth.py
│   ├── companies.py
│   ├── economics.py
│   ├── parser.py
│   ├── platforms.py
│   ├── quotas.py
│   ├── reputation.py
│   ├── reviews.py
│   └── system.py
├── schemas/
│   ├── __init__.py
│   ├── ai.py
│   ├── analytics.py
│   ├── auth.py
│   ├── billing.py
│   ├── dlq.py
│   ├── economics.py
│   └── parser.py
├── services/
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   └── twogis.py
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── hooks.py
│   │   ├── main.py
│   │   ├── tasks.py
│   │   └── worker.py
│   ├── __init__.py
│   ├── ai_processor.py
│   ├── analytics.py
│   ├── billing.py
│   ├── economics.py
│   ├── llm.py
│   ├── llm_analyzer.py
│   ├── parser.py
│   ├── parser_queue.py
│   ├── review_processor.py
│   └── sentiment.py
├── __init__.py
└── main.py

scripts/
├── migrate.py
└── seed_db.py

migrations/
├── 000_local_core_schema.sql
├── 001_multitenancy_rls.sql
├── 002_custom_access_token_hook.sql
├── 003_rls_smoke_test.sql
├── 004_reviews_dedup.sql
├── 004_update_models_for_multitenancy.py
├── 005_llm_analytics.sql
├── 005_reviews_scraper_fields.sql
├── 006_dead_letter_queue.sql
├── 008_billing_quotas.sql
├── 009_billing_seed.sql
├── 010_reviews_ai_fields.sql
├── 011_reputation_data.sql
├── 012_llm_cache.sql
├── README.md
├── add_external_review_id.py
├── run_migration.py
└── run_multitenancy_migration.py
```

The supported migration entry point is `python scripts/migrate.py`. It applies
the ordered SQL migration list from `migrations/`; migration helper scripts in
that directory are retained for compatibility and historical maintenance.
All repository SQL migration files are kept in `migrations/`. This project does
not currently contain an Alembic environment or Alembic revision scripts.

## Frontend-facing review contracts

- `GET /api/v1/reviews` accepts `limit`, `offset`, and optional review filters.
  Its response remains `{success, data: {items, total, page, page_size,
  total_pages}}`; the frontend API adapter unwraps `data` and maps database
  review fields to its view model.
- `GET /api/v1/reviews/summary` returns summary metrics, sentiment distribution,
  a 30-day timeline, and critical/AI-pending counts in the standard
  `{success, data}` envelope.
- `GET /api/v1/reputation/statistics?period_days=N` returns the platform
  statistics shape consumed by the Reputation screen.

## Frontend-facing parser contracts

- `POST /api/v1/parser/start` accepts `{platform, url}` and returns HTTP 202
  with a `job_id`. The legacy `/api/v1/parsers/start` path remains available.
- `GET /api/v1/parser/jobs/{job_id}` returns
  `{job_id, state, result, error}`. Backend ARQ status `complete` is mapped to
  frontend state `succeeded`; completed worker counters are mapped to the
  `ParseResult` fields used by the parsing screen. The legacy
  `/api/v1/parsers/status/{job_id}` route remains available.
- Job lookup and cancellation are scoped to the tenant that submitted the job.
- The frontend and parser API currently expose only `2gis`, matching the only
  platform implemented by the parser factory. Add a parser implementation
  before exposing another platform in the frontend/API.
- CORS exposes `Retry-After` and `X-Correlation-ID` so browser clients can read
  rate-limit retry timing and request correlation identifiers.
