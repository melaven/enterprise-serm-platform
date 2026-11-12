# TODO.md – Outstanding Tasks & Technical Debt

This file tracks all TODO, FIXME, and incomplete implementations across the codebase. Use this as a roadmap for future development.

---

## 🎯 Priority Levels

- **P0** – Critical (blocking production or major features)
- **P1** – High (important for stability/completeness)
- **P2** – Medium (improvements, minor bugs)
- **P3** – Low (nice-to-have, optimizations)

---

## 📋 Frontend Tasks

### Integrations Page
**File:** `frontend/src/pages/IntegrationsPage.tsx`

- [P2] **Line 135** – `// TODO: API integration`
  - Integrate with backend API for platform connection management
  - Currently using placeholder data

- [P2] **Line 152** – `// TODO: API integration`
  - Integrate with backend API for webhook configuration
  - Currently using placeholder data

### SI Config Page
**File:** `frontend/src/pages/SIConfigPage.tsx`

- [P2] **Line 141** – `// TODO: API integration`
  - Integrate with backend API for SI configuration
  - Currently using placeholder data

### Error Tracking
**File:** `frontend/src/components/error/GlobalErrorBoundary.tsx`

- [P1] **Line 48** – `// TODO: Отправить на error tracking сервис (Sentry, LogRocket, etc)`
  - Integrate error tracking service for production error monitoring
  - Currently only logging to console

### Testing
**File:** `frontend/README.md`

- [P1] **Unit tests (TODO)**
  - Implement comprehensive unit test coverage
  - Current test infrastructure exists but tests are incomplete

- [P1] **E2E tests (TODO)**
  - Implement end-to-end test coverage with Playwright
  - Currently no E2E tests exist

---

## 🔧 Backend Tasks

### LLM Analysis Integration
**File:** `app/infrastructure/queue/worker/tasks.py`

- [P1] **Line 68** – `# TODO: Call GroqReviewAnalyzer here for sentiment analysis`
  - Integrate Groq-based sentiment analyzer
  - Currently placeholder comment for where LLM analysis should be called

---

## 🧹 Code Quality & Technical Debt

### Ruff Linting
**File:** `pyproject.toml`

- [P2] **Line 73** – `"E501"` – `# TODO: Fix line length violations incrementally`
  - Gradually fix line length violations (currently ignored)
  - Target: Reduce ignored violations over time

- [P2] **Line 75** – `"B904"` – `# TODO: Add \`raise ... from\` in except blocks incrementally`
  - Add proper exception chaining in except blocks
  - Currently ignored for gradual migration

---

## 📝 Documentation

### Spanish Documentation
**File:** `docs/README.es.md`

- [P3] **Line 32** – Legal compliance note (contextual, not a task)
  - Reminder about data source authorization requirements
  - Not a code TODO, but important compliance guidance

- [P3] **Line 40** – PII sanitization limitations (contextual, not a task)
  - Reminder about pattern-based detection limitations
  - Not a code TODO, but important for understanding security boundaries

---

## 🚀 OpenAPI Integration

### Frontend Type Generation
**Status:** Partially implemented

- [P1] **OpenAPI schema exists but is placeholder**
  - `frontend/src/api/schema.d.ts` is generated but not automatically updated
  - Need to integrate `npm run api:gen` into CI/CD pipeline
  - Need to verify generated types match backend schema

- [P2] **OpenAPI client implementation incomplete**
  - `frontend/src/api/openapi-client.ts` exists but not widely used
  - Legacy `api/services.ts` still used in most places
  - Plan: Migrate all API calls to OpenAPI-generated client

---

## 🗄️ Database Migrations

### Migration for New Columns
**Status:** Not tracked

- [P1] **Database migration for `generated_reply` column**
  - Column added to `Review` model in `economics.py`
  - No corresponding Alembic migration exists
  - Production deployment requires migration

- [P1] **Database migration for `priority` column**
  - Column added to `OutboxEvent` model
  - No corresponding Alembic migration exists
  - Production deployment requires migration

---

## 🔐 Security & Compliance

### PII Sanitization Testing
**Status:** Partially implemented

- [P1] **Comprehensive PII pattern testing**
  - Regex patterns in `app/core/pii.py` need edge case coverage
  - Test existing: `tests/test_pii.py` or similar
  - Add tests for:
    - International phone formats
    - Edge cases in document number patterns
    - Social handle variations

### SpaCy PII Integration
**Status:** Implemented but not fully tested

- [P2] **SpaCy NER model testing**
  - `app/core/spacy_pii.py` exists with concurrency protection
  - Need performance benchmarks under load
  - Need accuracy evaluation against test dataset

---

## 🧪 Testing Coverage

### Backend Tests
**Status:** Infrastructure exists, coverage incomplete

- [P1] **Repository layer tests**
  - Test CRUD operations for all repositories
  - Test tenant isolation in repository queries

- [P1] **Service layer tests**
  - Test business logic in `app/application/`
  - Test economic calculations
  - Test review state transitions

- [P1] **Worker task tests**
  - Test outbox worker priority selection
  - Test retry logic and DLQ handling
  - Test LLM integration (mocked)

### Frontend Tests
**Status:** Infrastructure exists, coverage incomplete

- [P1] **Component tests**
  - Test all UI components in `frontend/src/components/`
  - Test ReviewCard, ReviewsList, ReviewsTable

- [P1] **Hook tests**
  - Test custom hooks in `frontend/src/hooks/`
  - Test optimistic mutations
  - Test abort logic in useSubmitReview

- [P1] **Integration tests**
  - Test API client with mocked backend
  - Test TanStack Query behavior
  - Test error boundary behavior

---

## 🎨 Design System

### B2B Design Compliance
**Status:** Partially implemented

- [P2] **Audit all components for design system violations**
  - Check for gray-* colors (should use chrome)
  - Check for shadows (should use borders)
  - Check for gradients (forbidden)
  - Check for rounded corners > 2px (should use rounded-none or rounded-sm)

- [P2] **Design lint script**
  - `frontend/package.json` has `design-lint` script
  - Implement actual design rule checking
  - Integrate into CI/CD pipeline

---

## 🚀 Performance & Scalability

### Frontend Virtualization
**Status:** Implemented for ReviewsTable

- [P2] **Extend virtualization to other list components**
  - Apply `@tanstack/react-virtual` to other long lists
  - Test performance with 10,000+ items

### Backend Connection Pooling
**Status:** NullPool configured

- [P2] **Evaluate connection pool strategy**
  - Currently using NullPool (no connection reuse)
  - Consider alternative pool for high-throughput scenarios
  - Test with PgBouncer transaction pooling

---

## 📦 Deployment & DevOps

### Docker Configuration
**Status:** Not verified

- [P1] **Verify Docker compose configuration**
  - Test `docker-compose up` for local development
  - Ensure all services (API, Redis, DB) start correctly
  - Verify environment variable injection

### CI/CD Pipeline
**Status:** Not implemented

- [P1] **Set up CI/CD pipeline**
  - Configure GitHub Actions or equivalent
  - Run tests on every PR
  - Run type checking and linting
  - Auto-generate OpenAPI types on backend changes

### Production Deployment
**Status:** Not documented

- [P0] **Production deployment guide**
  - Document production deployment steps
  - Document environment variables
  - Document secrets management
  - Document database migration procedure

---

## 🌐 Internationalization

### i18n Support
**Status:** Not implemented

- [P3] **Add internationalization support**
  - Russian is primary language
  - Consider adding English UI option
  - Use i18n library (react-i18next or similar)

---

## 📊 Analytics & Monitoring

### Application Monitoring
**Status:** Basic logging implemented

- [P1] **Integrate APM tool**
  - Consider Sentry, Datadog, or similar
  - Track error rates, latency, worker performance
  - Set up alerts for critical failures

- [P1] **Business metrics**
  - Track review ingestion rate
  - Track analysis queue depth
  - Track egress success rate

---

## 🔌 External Integrations

### Review Platform Adapters
**Status:** Partially implemented

- [P1] **Yandex adapter**
  - Verify OAuth flow
  - Test reply publishing
  - Test error handling

- [P1] **Google adapter**
  - Verify OAuth flow
  - Test reply publishing
  - Test error handling

- [P2] **Additional platforms**
  - Consider adding more platform adapters
  - Evaluate demand for other review platforms

---

## 💾 Data Management

### Dead Letter Queue
**Status:** Implemented but no recovery process

- [P1] **DLQ recovery process**
  - Implement automated retry for failed tasks
  - Implement manual recovery interface
  - Define retention policy for DLQ records

### Data Retention
**Status:** Not implemented

- [P1] **Data retention policy**
  - Define retention periods for reviews
  - Define retention periods for outbox events
  - Implement automated cleanup jobs

---

## 📱 Mobile Responsiveness

**Status:** Not verified

- [P2] **Mobile layout testing**
  - Test all pages on mobile viewports
  - Implement responsive breakpoints
  - Test touch interactions

---

## 🔄 State Management

### Zustand Store Refactoring
**Status:** Mixed concerns exist

- [P2] **Separate UI state from business data**
  - Current `useAppStore.ts` combines auth, parser state, and UI state
  - Plan: Split into focused stores (auth, parser, ui)
  - Document migration path

---

## 🎯 Summary Statistics

- **Total TODO/FIXME items:** 11
- **Frontend:** 5
- **Backend:** 1
- **Code Quality:** 2
- **Documentation:** 2 (contextual reminders)
- **Missing Migrations:** 2 (untracked)

---

## 📅 Next Steps (Recommended Order)

1. **P0 – Database Migrations** – Create migrations for `generated_reply` and `priority` columns
2. **P1 – Error Tracking** – Integrate Sentry or similar for production monitoring
3. **P1 – Testing Coverage** – Implement critical backend and frontend tests
4. **P1 – OpenAPI Migration** – Migrate API calls to OpenAPI-generated client
5. **P1 – LLM Integration** – Complete GroqReviewAnalyzer integration
6. **P2 – DLQ Recovery** – Implement DLQ recovery process
7. **P2 – CI/CD Pipeline** – Set up automated testing and type checking
8. **P2 – Design System Audit** – Verify all components follow B2B design rules

---

**Last Updated:** 2026-11-12  
**Total Tasks:** 11 TODO/FIXME items + additional technical debt items
