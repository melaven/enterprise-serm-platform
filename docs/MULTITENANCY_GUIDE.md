# SERM API Multitenancy Guide

## Overview

SERM API supports multitenancy through Row Level Security (RLS) in PostgreSQL. Each company is a separate tenant and sees only its own data.

## Multitenancy Architecture

### Core Components

1. **JWT authentication** - token contains `company_id` (tenant ID)
2. **Row Level Security (RLS)** - automatic data filtering at database level
3. **Tenant Session** - session with established `app.company_id` context
4. **Isolated roles** - `postgres` (admin) and `app_tenant` (runtime)

### Authentication Flow

```
1. Client → JWT Token → FastAPI
2. JWT verification → AuthContext (user_id, company_id)
3. Set app.company_id → RLS filtering
4. Queries see only their tenant's data
```

## Setup and Configuration

> For local development, use PostgreSQL 16 + pgvector from `docker-compose.yml`
> and only run `python scripts/migrate.py` from the repository root. It maintains
> the version log and sets the `app_tenant` password from `APP_TENANT_PASSWORD`
> automatically. The manual password and SQL backfill instructions below apply to
> legacy installations and are not part of the local Docker workflow.

### 1. Install Dependencies

```bash
pip install .
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# postgres role for migrations
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/serm_db

# app_tenant role for runtime  
TENANT_DATABASE_URL=postgresql+asyncpg://app_tenant:tenant_password@localhost:5432/serm_db

# JWT settings
AUTH_JWT_ALGORITHM=RS256
AUTH_JWKS_URL=https://your-project.supabase.co/auth/v1/jwks
```

### 3. Apply Migrations

```bash
docker compose up -d postgres
python scripts/migrate.py
python scripts/seed_db.py
```

### 4. Additional Setup

After migrations:

1. **Set app_tenant password**:
```sql
ALTER ROLE app_tenant PASSWORD 'secure_password';
```

2. **Enable Custom Access Token Hook** in Supabase Dashboard:
   - Authentication → Hooks → Custom Access Token

3. **Populate company_members table**:
```sql
INSERT INTO company_members (user_id, company_id, role) VALUES 
('user-uuid-1', 'company-uuid-1', 'owner'),
('user-uuid-2', 'company-uuid-1', 'member');
```

4. **Backfill company_id in reviews**:
```sql
UPDATE reviews SET company_id = (
    SELECT company_id FROM platforms 
    WHERE platforms.id = reviews.platform_id
) WHERE company_id IS NULL;
```

## Usage in Code

### JWT Authentication

```python
from uuid import UUID
from fastapi import Depends
from app.core.auth import get_current_tenant

# In router
async def my_endpoint(
    tenant_id: UUID = Depends(get_current_tenant)
):
    # Tenant ID extracted and verified from JWT.
    company_id = tenant_id
```

### Tenant-aware Repositories

```python
from app.core.dependencies import get_review_repository
from app.infrastructure.persistence.repositories import ReviewRepository

# Repository is automatically tenant-isolated
async def get_reviews(
    review_repo: ReviewRepository = Depends(get_review_repository)
):
    # Sees only own company's reviews thanks to RLS
    reviews = await review_repo.get_all()
```

### Tenant Session

```python
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.core.dependencies import get_tenant_db

async def list_reviews(db: AsyncSession = Depends(get_tenant_db)):
    # Dependency sets the tenant context before repository queries run.
    ...
```

## Security

### Row Level Security (RLS)

RLS policies are applied automatically:

```sql
-- Companies see only their own records
CREATE POLICY companies_policy ON companies
FOR ALL TO app_tenant
USING (id = current_setting('app.company_id')::uuid);

-- Platforms filtered by company_id  
CREATE POLICY platforms_policy ON platforms
FOR ALL TO app_tenant
USING (company_id = current_setting('app.company_id')::uuid);

-- Reviews isolated by company_id
CREATE POLICY reviews_policy ON reviews  
FOR ALL TO app_tenant
USING (company_id = current_setting('app.company_id')::uuid);
```

### Role Isolation

- **`postgres`** - full privileges, migrations and admin only
- **`app_tenant`** - restricted privileges, cannot bypass RLS

### JWT Security

- RS256 with JWKS support (recommended)
- Legacy HS256 for development
- Token signature and expiration verification
- Extract `company_id` from various claims

## Testing Isolation

### Smoke Test

```bash
# Verify RLS is working
cd app
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def test():
    async with engine.begin() as conn:
        await conn.execute(text('SET ROLE app_tenant'))
        result = await conn.execute(text('SELECT COUNT(*) FROM reviews'))
        print('Reviews without tenant context:', result.scalar())
        
        await conn.execute(text(\"SELECT set_config('app.company_id', 'fake-uuid', true)\"))
        result = await conn.execute(text('SELECT COUNT(*) FROM reviews'))  
        print('Reviews with fake tenant:', result.scalar())

asyncio.run(test())
"
```

Should return 0 for both cases.

### Unit Tests

```python
import pytest
from app.core.jwt_handler import JWTHandler

@pytest.mark.asyncio
async def test_jwt_verification():
    handler = JWTHandler()
    
    # Test with valid token
    token = "valid.jwt.token"
    context = await handler.verify_token(token)
    
    assert context.user_id is not None
    assert context.company_id is not None

@pytest.mark.asyncio  
async def test_tenant_isolation(tenant_db_session):
    # Data must be tenant-isolated
    reviews = await review_repo.get_all()
    
    # All reviews must belong to one company
    company_ids = {r.company_id for r in reviews}
    assert len(company_ids) <= 1
```

## Troubleshooting

### RLS Issues

**Symptom**: Queries return 0 rows

**Solution**:
1. Check that `app.company_id` is set:
```sql
SELECT current_setting('app.company_id', true);
```

2. Check that RLS is enabled:
```sql
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
```

3. Check policies:
```sql
SELECT * FROM pg_policies WHERE schemaname = 'public';
```

### JWT Issues

**Symptom**: 401 Unauthorized

**Solution**:
1. Check token format: `Authorization: Bearer <token>`
2. Verify JWKS URL availability
3. Verify token contains `company_id`

### Role Issues

**Symptom**: Permission denied

**Solution**:
1. Check that you're using `TENANT_DATABASE_URL`
2. Ensure `app_tenant` role exists
3. Check table access permissions

## Monitoring

### Logging

All operations are logged with tenant context:

```
INFO - User authenticated: user-id-123, company: company-id-456
DEBUG - Tenant context set: company_id=company-id-456  
DEBUG - Tenant session closed: company_id=company-id-456
```

### Metrics

Track:
- Request count per tenant
- Tenant context setup time
- Authentication errors per tenant
- Isolation violations (should be 0)

### Health Checks

```bash
GET /health
```

Checks:
- ✅ Database connection (tenant role)
- ✅ JWT Handler (JWKS availability)  
- ✅ LLM service
- ✅ Multitenancy configuration

## Performance

### RLS Optimization

1. **Indexes on company_id** - created automatically
2. **Partitioning** - consider for large tables
3. **Connection pooling** - NullPool for Supabase

### Caching

- JWT claims cached until token expiration
- JWKS cached for 1 hour
- Singleton services reused

## Deployment

### Environment Variables

```bash
# Production
USE_TENANT_ROLE=true
AUTH_JWT_ALGORITHM=RS256
SQL_ECHO=false

# Development  
USE_TENANT_ROLE=false  # For debugging without RLS
SQL_ECHO=true         # To view SQL queries
```

### CI/CD

1. Migrations run under `postgres` role
2. Runtime uses `app_tenant` role  
3. Smoke tests verify isolation
4. Health checks verify all components

## Best Practices

1. **Always use tenant-aware dependencies**
2. **Don't use `session.commit()` in middleware**  
3. **Test isolation for every new table**
4. **Log all operations with tenant context**
5. **Monitor security violations**
6. **Regularly rotate JWT secrets**
