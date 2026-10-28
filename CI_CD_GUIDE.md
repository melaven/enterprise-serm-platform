# CI/CD Pipeline Guide - Tenable SERM

## Overview

The project uses GitHub Actions to automate testing, linting, and Docker image builds. The pipeline is configured to protect against broken code and ensure reliability before deployment.

## Pipeline Structure

```
┌─────────────┐
│    Lint     │  (Ruff + MyPy)
└──────┬──────┘
       │
       ├─────────────────────────────┐
       │                             │
       ▼                             ▼
┌─────────────┐           ┌─────────────┐
│   Unit      │           │ Integration │
│   Tests     │           │   Tests     │
└──────┬──────┘           └──────┬──────┘
       │                          │
       ├──────────────────────────┤
       │                          │
       ▼                          ▼
┌─────────────┐           ┌─────────────┐
│  Tenant     │           │  Security   │
│ Isolation   │           │   Tests     │
└──────┬──────┘           └──────┬──────┘
       │                          │
       └──────────┬───────────────┘
                  │
                  ▼
         ┌─────────────┐
         │    Build    │  (Docker + Security Scan)
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │   Deploy    │  (Push to Docker Hub)
         └─────────────┘
```

## Jobs

### 1. Lint Job

**Purpose:** Code quality check before testing

**Tools:**
- **Ruff** - linter and code formatter
- **MyPy** - static type checking (strict mode)

**Commands:**
```bash
ruff check app/ tests/
ruff format --check app/ tests/
mypy app/ --strict
```

**Failure Reasons:**
- Incorrect syntax
- PEP8 violations
- Type errors
- Formatting mismatches

### 2. Test Job (Matrix Strategy)

**Purpose:** Comprehensive testing in 4 parallel streams

#### 2.1 Unit Tests
- Run fast tests without external dependencies
- Code coverage generation
- XML reports generation

#### 2.2 Integration Tests
- PostgreSQL and Redis integration testing
- Database migration verification
- API endpoint testing

#### 2.3 Tenant Isolation (RLS) Tests
**CRITICAL for multitenancy:**
- Row Level Security verification
- Tenant isolation testing
- Verify Tenant A cannot see Tenant B data

**Test commands:**
```bash
pytest tests/test_reviews_api.py -v -k "tenant"
pytest tests/test_billing.py -v -k "tenant"
pytest tests/test_auth_session.py -v -k "tenant"
```

#### 2.4 Security Tests
- JWT authentication verification
- Quota and billing testing
- Authorization checks on all endpoints

**Test commands:**
```bash
pytest tests/test_auth_session.py -v
pytest tests/test_billing_deps.py -v
```

### 3. Build Job

**Purpose:** Docker image build and security scanning

**Steps:**
1. Build backend.Dockerfile
2. Build worker.Dockerfile
3. Build frontend.Dockerfile
4. Test docker-compose build
5. **Security Scan (Trivy)** - vulnerability check
6. Upload security results to GitHub Security
7. Push images to Docker Hub (main branch only)

## Environment Variables

### Test Environment
```yaml
DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
REDIS_URL: redis://localhost:6379/0
SUPABASE_URL: https://test.supabase.co
SUPABASE_SERVICE_ROLE_KEY: test_key
GROQ_API_KEY: test_key
JWT_SECRET_KEY: test_secret_key_for_ci
ENVIRONMENT: testing
TEST_DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
```

### Required GitHub Secrets
- `DOCKER_USERNAME` - Docker Hub username for pushing images
- `DOCKER_PASSWORD` - Docker Hub password/token

## Tenant Isolation Testing

### What is verified:

1. **RLS Policies**
   - Tenant A reviews are inaccessible to Tenant B
   - Platforms isolated by company_id
   - Quotas work correctly for each tenant

2. **JWT Claims**
   - `tenant_id` correctly extracted from token
   - `company_id` set in database context
   - Non-existent tenant_id rejected

3. **Cross-Tenant Data Leakage**
   - Tenant A cannot access Tenant B data via API
   - SQL injections don't bypass RLS
   - Direct SQL queries with incorrect tenant_id blocked

### Example test:

```python
async def test_tenant_isolation():
    # Tenant A creates review
    review_a = await create_review(tenant_id=tenant_a, text="Good")

    # Tenant B tries to access Tenant A's review
    response = await client.get(f"/reviews/{review_a.id}",
                                headers={"X-Tenant-ID": str(tenant_b)})

    # Should return 404 or 403
    assert response.status_code in [404, 403]
```

## Security Testing

### What is verified:

1. **JWT Authentication**
   - Invalid tokens rejected
   - Expired tokens rejected
   - Missing token returns 401

2. **Authorization**
   - Anonymous access forbidden
   - Incorrect roles rejected
   - Access rights checked on every endpoint

3. **Quota Enforcement**
   - Limit exceeded blocked
   - Quotas isolated per tenant
   - Billing checks work correctly

## Database Migrations in CI

**Steps:**
1. Run Python migrations (multitenancy)
2. Run Python migrations (additional)
3. Apply SQL migrations via psql:
   - `001_multitenancy_rls.sql` - RLS policies
   - `002_custom_access_token_hook.sql` - Supabase hooks

**Fault tolerance:**
- All migrations run with `|| true`
- If migration already applied, it's skipped
- Error in one migration doesn't stop pipeline

## Docker Image Security

### Trivy Scan
- Vulnerability check in images
- Dependency scanning
- SARIF format report for GitHub Security

### Results
- High/critical vulnerabilities block deployment
- Results uploaded to GitHub Security tab
- Automatic issue creation for critical problems

## Deployment Flow

### Trigger Conditions
- Push to `main` branch
- All tests passed successfully
- Build job completed without errors

### Deployment Steps
1. Tag images with Git SHA
2. Push to Docker Hub
3. Create deployment summary in GitHub
4. Display tag and deployment time

### Manual Deployment
For manual server deployment:
```bash
docker pull your-username/tenable-serm-backend:latest
docker pull your-username/tenable-serm-worker:latest
docker pull your-username/tenable-serm-frontend:latest
docker-compose up -d
```

## Troubleshooting

### Lint Failures
```bash
# Local check
pip install -r requirements-dev.txt
ruff check app/ tests/
ruff format app/ tests/
mypy app/ --strict
```

### Test Failures
```bash
# Local run with same variables
export DATABASE_URL="postgresql+asyncpg://test_user:test_password@localhost:5432/test_db"
export REDIS_URL="redis://localhost:6379/0"
pytest tests/ -v --asyncio-mode=auto
```

### Tenant Isolation Failures
```bash
# Run only tenant tests
pytest tests/test_reviews_api.py -v -k "tenant"
pytest tests/test_billing.py -v -k "tenant"
```

### Docker Build Failures
```bash
# Local build
docker-compose build
# Separately
docker build -f backend.Dockerfile -t test-backend .
docker build -f worker.Dockerfile -t test-worker .
docker build -f frontend.Dockerfile -t test-frontend .
```

## Best Practices

### 1. Pre-commit Hooks
Install pre-commit for local checks:
```bash
pip install pre-commit
pre-commit install
```

### 2. Test Naming
Use descriptive test names:
```python
async def test_tenant_a_cannot_access_tenant_b_reviews():
    # ...
```

### 3. Test Markers
Use pytest markers for grouping:
```python
@pytest.mark.integration
async def test_api_integration():
    # ...

@pytest.mark.tenant
async def test_tenant_isolation():
    # ...
```

### 4. Coverage Goals
- Minimum coverage: 80%
- Target coverage: 90%
- Critical modules: 95%+

## Monitoring

### GitHub Actions Status
- Green checkmark = all good
- Red cross = broken code, don't deploy
- Yellow = warnings, requires attention

### Coverage Reports
- Codecov automatically uploads coverage
- Check coverage % in PR
- New code should have coverage > 80%

### Security Alerts
- GitHub Security tab shows vulnerabilities
- Trivy findings in PR comments
- Critical issues require immediate fix

## Future Enhancements

### Planned Additions
- [ ] E2E tests with real browser (Playwright)
- [ ] Performance testing (Locust)
- [ ] Load testing in CI
- [ ] Automatic rollback on failed deployment
- [ ] Canary deployments
- [ ] Blue-green deployments

### Possible Integrations
- [ ] SonarQube for code quality
- [ ] Snyk for dependency scanning
- [ ] OWASP ZAP for security testing
- [ ] Datadog/APM for monitoring

## Support

If pipeline fails:
1. Check logs in GitHub Actions
2. Run failing tests locally
3. Ensure .env configured correctly locally
4. Check dependencies in requirements.txt
5. Contact DevOps team

---

**Version:** 1.0  
**Last Updated:** 2026-10-13  
**Maintainer:** Tenable SERM Team
