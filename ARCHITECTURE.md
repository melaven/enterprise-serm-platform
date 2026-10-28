# SERM API Architecture

## Overview

SERM (Service & Economy Reputation Management) API is built on a three-layer architecture with centralized error handling and dependency injection.

## Architecture Layers

### 1. Routing Layer (Routers/API)

**Location**: `app/routers/`

**Responsibilities**:
- Receive HTTP requests
- Validate incoming data via Pydantic
- Return standardized responses
- **Does NOT contain business logic**

**Files**:
- `economics.py` - economic operations and simulations
- `reviews.py` - review management and webhooks
- `companies.py` - company CRUD operations
- `platforms.py` - platform management
- `system.py` - system endpoints (testing, diagnostics)

### 2. Business Logic Layer (Services)

**Location**: `app/services/`

**Responsibilities**:
- All SERM mathematics (LTV calculation, negative impact assessment)
- Coordination between repositories
- Business rules and validation
- External API integration (OpenAI)

**Files**:
- `economics.py` - financial impact calculations, ROI, risk assessment
- `llm.py` - review response generation via OpenAI
- `sentiment.py` - sentiment analysis and prioritization
- `review_processor.py` - central review processing coordinator

### 3. Data Layer (Repositories/DAL)

**Location**: `app/repositories/`

**Responsibilities**:
- Data access abstraction
- CRUD operations
- Complex queries and aggregation
- Isolation from database schema changes

**Files**:
- `base.py` - base repository with common operations
- `company.py` - company operations
- `platform.py` - platform management
- `review.py` - review operations and analytics

## Centralized Error Handling

**Files**:
- `exceptions.py` - custom exceptions for different error types
- `handlers.py` - global handlers with standardized JSON

**Error Types**:
- `NotFoundError` (404) - resource not found
- `AccessDeniedError` (403) - insufficient access rights
- `DatabaseError` (500/503) - database errors and timeouts
- `LLMServiceError` (502) - OpenAI API issues
- `EconomicsCalculationError` (400) - calculation errors

## Dependency Injection

**File**: `app/dependencies.py`

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
- `models/economics.py` - SQLAlchemy models
- `schemas/economics.py` - Pydantic schemas for API

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
- [app/routers](app/routers) — API endpoints
  - `auth.py` — login/registration/tokens
  - `reviews.py` — reviews
  - `companies.py` — companies
  - `platforms.py` — platforms
  - `economics.py` — economics and calculations
  - `analytics.py` — analytics
  - `parser.py` — parsing start and status
  - `reputation.py` — reputation and summary metrics

### 4. Business Logic
- [app/services](app/services) — domain logic
  - `economics.py` — financial and economic calculations
  - `review_processor.py` — main review processing workflow
  - `llm.py` / `llm_analyzer.py` — AI logic and text analysis
  - `sentiment.py` — sentiment scoring
  - `parser.py` — data parsing
  - `billing.py` — quotas and billing
  - `analytics.py` — analytical aggregates
  - `worker/` — background tasks and ARQ worker

### 5. Data and Database Access
- [app/repositories](app/repositories) — repositories
  - `company.py`, `platform.py`, `review.py`
  - `analytics_repo.py`
  - `dlq.py`
  - `parser.py`
- [app/models](app/models) — SQLAlchemy models
- [app/schemas](app/schemas) — Pydantic API and domain object contracts

### 6. Integrations and Infrastructure
- [migrations](migrations) — database migrations
- [scripts](scripts) — migration and seed utilities
- [docker-compose.yml](docker-compose.yml) — local infrastructure
- [docker-compose.prod.yml](docker-compose.prod.yml) — production configuration
- [run.py](run.py) — backend startup
- [worker.py](worker.py) — separate worker entrypoint

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
  ├─ routers/            -> HTTP API
  ├─ services/           -> business logic
  ├─ repositories/       -> data access
  ├─ models/             -> database entities
  ├─ schemas/            -> input/output contracts
  ├─ core/               -> auth, tenant, middleware, config, DI
  └─ main.py             -> application composition

worker/
  ├─ parsing tasks       -> background tasks
  ├─ queue/ARQ           -> async queue
  └─ DLQ / retries       -> handler reliability

migrations/
  └─ database schema     -> schema and database evolution
```

## Quick Route for New Contributors

If you need to quickly understand the project and locate components:

1. Open [README.md](README.md)
2. Read [ARCHITECTURE.md](ARCHITECTURE.md)
3. Open [app/main.py](app/main.py)
4. Review [app/core/dependencies.py](app/core/dependencies.py)
5. Navigate through routers in [app/routers](app/routers)
6. Then services in [app/services](app/services)
7. Then repositories in [app/repositories](app/repositories)
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
