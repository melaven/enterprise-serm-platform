# SERM API Architecture

## Overview

SERM (Service & Economy Reputation Management) API uses layered FastAPI architecture with domain-oriented packages, centralized error handling, and dependency injection.

## Architecture Layers

### 1. HTTP Layer

**Location**: `app/api/v1/routes/`

**Responsibilities**:
- Receive HTTP requests
- Validate incoming data via Pydantic
- Return standardized responses
- **Does NOT contain business logic**

Request and response DTOs live in `app/api/schemas/`; the SQLAdmin integration is in `app/api/admin.py`.

### 2. Application and Domain Layers

**Locations**: `app/application/` and `app/domain/`

Application modules coordinate use cases and persistence/integration adapters. Domain rules that can remain independent of FastAPI and storage belong in `app/domain/`, including review lifecycle state and transitions.

### 3. Infrastructure

**Location**: `app/infrastructure/`

- `persistence/models/` and `persistence/repositories/` - SQLAlchemy models and database access
- `integrations/llm/` and `integrations/review_platforms/` - external service adapters
- `parsers/` - source-specific review parsers
- `queue/worker/` - ARQ worker configuration and background tasks

## Centralized Error Handling

**Files**:
- `app/core/exceptions.py` - custom exceptions for different error types
- `app/core/handlers.py` - global handlers with standardized JSON

**Error Types**:
- `NotFoundError` (404) - resource not found
- `AccessDeniedError` (403) - insufficient access rights
- `DatabaseError` (500/503) - database errors and timeouts
- `LLMServiceError` (502) - OpenAI API issues
- `EconomicsCalculationError` (400) - calculation errors

## Dependency Injection

**File**: `app/core/dependencies.py`

**Principles**:
- Factory functions for instance creation
- Singletons for stateless services (LLM, Sentiment)
- Bundles for grouping dependencies
- Health checks for state monitoring

**Dependency Graph**:
```
FastAPI Router
    ↓
Service Layer (Business Logic)
    ↓  
Repository Layer (Data Access)
    ↓
Database (PostgreSQL/Supabase)
```

## Data Models

**Files**:
- `app/infrastructure/persistence/models/economics.py` - SQLAlchemy models
- `app/api/schemas/economics.py` - Pydantic schemas for API

**Core Entities**:
- `Company` - company with economic indicators
- `Platform` - review platform (Google Maps, 2GIS)
- `Review` - review with impact analysis and processing status

## Configuration

**Environment Variables**:
```bash
DATABASE_URL=postgresql+asyncpg://...
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
DEBUG=false
LOG_LEVEL=INFO
```

## API Endpoints

### Economics (`/api/v1/economics/`)
- `POST /simulate` - simulate review impact
- `POST /process` - full review processing with persistence
- `POST /bulk-process` - bulk processing
- `GET /platform/{id}/roi` - platform ROI
- `GET /platform/{id}/risk-assessment` - risk assessment

### Reviews (`/api/v1/reviews/`)
- `POST /webhook` - receive reviews from external systems
- `GET /{id}` - get review by ID
- `GET /platform/{id}/reviews` - platform reviews
- `PUT /{id}/status` - update status
- `GET /search` - content search

### Companies (`/api/v1/companies/`)
- `POST /` - create company
- `GET /{id}` - company information
- `PUT /{id}/economics` - update metrics
- `GET /{id}/dashboard` - summary analytics

### Platforms (`/api/v1/platforms/`)
- `POST /` - create platform
- `GET /company/{id}/platforms` - company platforms
- `PUT /{id}/metrics` - update metrics
- `GET /stats` - platform statistics

### Parsers (`/api/v1/parsers/`)
- `POST /start` - check quota and enqueue parsing task
- `GET /status/{job_id}` - get task status

Before enqueuing a task, `POST /start` atomically deducts the request with a single
`UPDATE ... FROM ... RETURNING`: organization activity and plan limit are checked
in the same SQL query as the counter update. If deduction is impossible, the endpoint
returns HTTP 402 and the task is not sent to the queue.

## Security

- All input data validation via Pydantic
- Parameterized SQL queries (SQL injection protection)
- Centralized error handling (no internal details exposed)
- CORS configuration
- Request ID for tracing

## Monitoring & Observability

- Structured logging
- Health checks (`/health`)
- Request tracing with unique IDs
- Performance metrics
- Dependency graph in debug mode

## Reading Order for New Developers

If opening the repository from scratch, read in this order to navigate the structure effectively.

### 1. Entry Documents
- [README.md](README.md) — general project description, stack, startup, main scenarios
- [ARCHITECTURE.md](ARCHITECTURE.md) — architecture map and core principles
- [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md) — more technical backend map
- [frontend/FRONTEND_ARCHITECTURE.md](frontend/FRONTEND_ARCHITECTURE.md) — frontend structure and modularity

### 2. Application Entry Points
- [app/main.py](app/main.py) — main FastAPI entrypoint
- [app/core/dependencies.py](app/core/dependencies.py) — DI and service/repository factories
- [app/core/database.py](app/core/database.py) — database and sessions
- [app/core/auth.py](app/core/auth.py) — authentication and authorization
- [app/core/tenant.py](app/core/tenant.py) — tenant context

### 3. HTTP Layer
- [app/api/v1/routes](app/api/v1/routes) — API endpoints
  - `auth.py` — login/registration/tokens
  - `reviews.py` — reviews
  - `companies.py` — companies
  - `platforms.py` — platforms
  - `economics.py` — economics and calculations
  - `analytics.py` — analytics
  - `parser.py` — parsing start and status
  - `reputation.py` — reputation and summary metrics

### 4. Business Logic
- [app/application](app/application) — use cases and application services
- [app/domain/reviews](app/domain/reviews) — review lifecycle and domain rules

### 5. Data and Database Access
- [app/infrastructure/persistence/repositories](app/infrastructure/persistence/repositories) — repositories
  - `company.py`, `platform.py`, `review.py`
  - `analytics_repo.py`
  - `dlq.py`
  - `parser.py`
- [app/infrastructure/persistence/models](app/infrastructure/persistence/models) — SQLAlchemy models
- [app/api/schemas](app/api/schemas) — Pydantic API contracts

### 6. Integrations and Infrastructure
- [app/infrastructure](app/infrastructure) — persistence, integrations, parsers, and queue workers
- [migrations](migrations) — database migrations
- [scripts](scripts) — migration and seed utilities
- [docker-compose.yml](docker-compose.yml) — local infrastructure
- [docker-compose.prod.yml](docker-compose.prod.yml) — production configuration
- [scripts/run_api.py](scripts/run_api.py) — optional backend startup
- [app/worker.py](app/worker.py) — compatibility import for the ARQ worker

### 7. Frontend
- [frontend](frontend) — React/Vite application
  - [frontend/src](frontend/src) — main UI code
  - `api/` — HTTP client and integrations
  - `features/` — feature modules
  - `pages/` — routes
  - `components/` — UI components

### 8. Tests and Quality
- [tests](tests) — backend tests
- `*.test.ts` / `*.test.py` — contract and logic validation
- `pytest.ini` and configuration files — test environment settings

## Project Responsibility Map

```text
frontend/
  ├─ pages/              -> routes and screens
  ├─ features/           -> business features
  ├─ components/         -> reusable UI components
  └─ api/                -> HTTP contracts and requests

app/
  ├─ api/                -> versioned HTTP routes, schemas, admin
  ├─ application/        -> use cases and application services
  ├─ domain/             -> domain rules and lifecycle state
  ├─ infrastructure/     -> persistence, integrations, parsers, queue
  ├─ core/               -> auth, tenant, middleware, config, DI
  └─ main.py             -> application composition

migrations/
  └─ database schema     -> schema and database evolution
```

## Quick Route for New Contributors

If you need to quickly understand the project and locate components:

1. Open [README.md](README.md)
2. Read [ARCHITECTURE.md](ARCHITECTURE.md)
3. Open [app/main.py](app/main.py)
4. Review [app/core/dependencies.py](app/core/dependencies.py)
5. Navigate through routes in [app/api/v1/routes](app/api/v1/routes)
6. Then use cases in [app/application](app/application)
7. Then persistence adapters in [app/infrastructure/persistence](app/infrastructure/persistence)
8. Only after that review frontend in [frontend](frontend)

This provides a "horizontal" path through the architecture without chaos or repeated folder searches.

## Scaling

**Current architecture supports**:
- Horizontal scaling (stateless services)
- Caching at dependency injection level
- Connection pooling for database (NullPool for Supabase)
- Asynchronous request processing

**Possible improvements**:
- Redis for calculation caching
- Message queues for async processing
- Microservice decomposition by domain
- Event sourcing for change auditing
