# Local Development Guide - Tenable SERM
## Setup Without Docker

### Overview

This guide covers setting up a local development environment for Tenable SERM without using Docker. This is useful when:
- Docker is not available
- Disk space is limited
- You want faster iteration cycles
- You prefer native Python development

---

## Prerequisites

### Required Software

1. **Python 3.10+**
   - Download from https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation

2. **Git**
   - Download from https://git-scm.com/downloads

3. **Code Editor**
   - VS Code (recommended) with Python extension
   - Or PyCharm Community Edition

4. **PostgreSQL** (required; use Supabase or a local PostgreSQL instance)
   - Download from https://www.postgresql.org/download/windows/
   - Or use Docker for PostgreSQL only (when disk space allows)

### Optional Software

1. **Redis** (if you need background task processing locally)
   - Download from https://redis.io/download
   - Or use Memurai for Windows

---

## Quick Start

### Windows (PowerShell)

```powershell
# 1. Run setup script
.\setup_env.ps1

# 2. Configure environment
copy .env.example .env
# Edit .env with your settings

# 3. Start backend
.\start_backend.bat
```

### Linux/Mac

```bash
# 1. Run setup script
chmod +x setup_env.sh
./setup_env.sh

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start backend
./start_backend.sh
```

---

## Environment Configuration

### .env.example

Copy `.env.example` to `.env` and configure:

**Critical Settings:**
```bash
# PostgreSQL (Supabase or a provisioned local PostgreSQL instance)
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_JWT_SECRET=...

# Groq or another configured LLM provider
GROQ_API_KEY=...
```

**Optional Settings:**
```bash
# Disable ARQ queueing for local development
REDIS_URL=dummy://skip

# Disable rate limiting
RATE_LIMIT_ENABLED=false

# Debug mode
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## Development Workflow

### 1. Start Backend

**Windows:**
```batch
.\start_backend.bat
```

**Linux/Mac:**
```bash
./start_backend.sh
```

Backend will start at http://127.0.0.1:8000

### 2. Run Tests

**Windows:**
```batch
.\run_tests.bat
```

**Linux/Mac:**
```bash
./run_tests.sh
```

Coverage report will be generated in `htmlcov/index.html`

### 3. Run Linting

**Windows:**
```batch
.\run_lint.bat
```

**Linux/Mac:**
```bash
./run_lint.sh
```

### 4. Format Code

**Windows:**
```batch
.\format_code.bat
```

**Linux/Mac:**
```bash
ruff format app/ tests/
ruff check --fix app/ tests/
```

---

## Virtual Environment Management

### Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### Deactivate Virtual Environment

```bash
deactivate
```

### Install New Dependencies

```bash
# Activate venv first
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\Activate.ps1  # Windows

# Install new package
pip install package-name

# Add the dependency to pyproject.toml
```

---

## Database Setup (Local)

### Option 1: SQLite (Easiest)

No setup required! Just configure in `.env`:
```bash
DATABASE_URL=sqlite+aiosqlite:///./serm_local.db
```

The database file will be created automatically.

### Option 2: PostgreSQL (Local)

1. Install PostgreSQL from https://www.postgresql.org/download/windows/
2. Create a database:
```sql
CREATE DATABASE serm_local;
```

3. Configure in `.env`:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/serm_local
```

### Option 3: PostgreSQL (Docker Only)

If you want to use Docker only for PostgreSQL (lightweight):

```bash
docker run -d --name postgres-local \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=serm_local \
  -p 5432:5432 \
  postgres:16-alpine
```

Configure in `.env`:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/serm_local
```

---

## Redis Setup (Local)

### Option 1: Skip Redis (Recommended for Local Dev)

Configure in `.env`:
```bash
REDIS_URL=dummy://skip
```

Redis-dependent features will be disabled.

### Option 2: Memurai (Windows)

Download from https://github.com/microsoftarchive/redis/releases

Configure in `.env`:
```bash
REDIS_URL=redis://localhost:6379/0
```

### Option 3: Docker Redis Only

```bash
docker run -d --name redis-local \
  -p 6379:6379 \
  redis:7-alpine
```

---

## API Testing

### With curl

```bash
# Health check
curl http://127.0.0.1:8000/health

# Root endpoint
curl http://127.0.0.1:8000/

# OpenAPI docs
# Open browser to http://127.0.0.1:8000/docs
```

### With Python httpx

```python
import httpx

client = httpx.Client(base_url="http://127.0.0.1:8000")

# Health check
response = client.get("/health")
print(response.json())
```

---

## Troubleshooting

### Virtual Environment Issues

**Problem:** `.venv` folder is ignored by Git
**Solution:** Already handled by `.gitignore`

**Problem:** Scripts can't find Python
**Solution:** Make sure you activated the virtual environment first

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'app'`
**Solution:** 
```bash
# Install the project and development dependencies in editable mode
pip install -e ".[dev]"
```

### Database Connection Errors

**Problem:** Cannot connect to database
**Solution:** 
- If using SQLite: Check write permissions
- If using PostgreSQL: Ensure PostgreSQL is running
- Check DATABASE_URL in `.env`

### Port Already in Use

**Problem:** `Address already in use: ('127.0.0.1', 8000)`
**Solution:**
```bash
# Find process using port 8000 (Windows)
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or use different port in start_backend.bat
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

---

## IDE Configuration

### VS Code

**Recommended Extensions:**
- Python (Microsoft)
- Pylance (Microsoft)
- Ruff (charliermarsh)
- SQLite Viewer (alexcvzz)
- REST Client (humao.rest-client)

**Settings (.vscode/settings.json):**
```json
{
  "python.defaultInterpreterPath": "./.venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

### PyCharm

**Configuration:**
1. File → Settings → Project → Python Interpreter
2. Add Local Interpreter → Select `.venv/Scripts/python.exe`
3. Install required packages
4. Configure run configuration for `app.main:app`

---

## Pre-commit Hooks

Pre-commit hooks are installed automatically by `setup_env.ps1`/`setup_env.sh`.

To manually install:
```bash
pre-commit install
```

To run hooks manually:
```bash
pre-commit run --all-files
```

To skip hooks (not recommended):
```bash
git commit --no-verify -m "message"
```

---

## Performance Tips

### 1. Use SQLite for Local Dev

SQLite is fastest for local development:
- No external dependencies
- Instant startup
- No network overhead

### 2. Disable Redis

Skip Redis if you don't need it:
```bash
REDIS_URL=dummy://skip
```

### 3. Disable Rate Limiting

```bash
RATE_LIMIT_ENABLED=false
```

### 4. Use Single Worker

```bash
WEB_CONCURRENCY=1
```

---

## Testing Without External Services

### Mocking Services

Some tests mock external services. To run tests without real services:

```bash
# Run specific test file
pytest tests/test_auth_session.py -v

# Run with markers
pytest tests/ -m "not integration" -v
```

### Test Database

Tests can use SQLite automatically:
```bash
TEST_DATABASE_URL=sqlite+aiosqlite:///:memory: pytest tests/ -v
```

---

## Migration to Docker

When you're ready to use Docker (evening):

1. Ensure Docker Desktop is running
2. Use `docker-compose.yml` for full stack
3. Use `docker-compose.prod.yml` for production
4. See `DOCKER_DEPLOYMENT.md` for details

---

## Cleanup

### Remove Virtual Environment

**Windows:**
```powershell
deactivate
Remove-Item -Recurse -Force .venv
```

**Linux/Mac:**
```bash
deactivate
rm -rf .venv
```

### Clean Python Cache

```bash
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### Remove Database File (SQLite)

```bash
rm serm_local.db
```

---

## FAQ

**Q: Can I use both Docker and local development?**
A: Yes! You can switch between them. Just ensure your `.env` matches your chosen environment.

**Q: How do I sync my local database with Docker database?**
A: You'd need to export/import data. For development, it's easier to stick to one environment at a time.

**Q: Why SQLite instead of PostgreSQL?**
A: SQLite is faster for local dev, requires no setup, and is sufficient for most development tasks. PostgreSQL is recommended for production.

**Q: Can I run the frontend locally too?**
A: Yes! The frontend has its own setup. See `frontend/SETUP.md` for details.

**Q: How do I debug with breakpoints?**
A: Use VS Code debugger or PyCharm debugger. Both work with the virtual environment.

---

## Support

If you encounter issues:
1. Check this guide first
2. Check existing `.env` configuration
3. Run linting to catch code issues
4. Check Python version (3.10+ required)
5. See `TROUBLESHOOTING.md` for common issues

---

**Version:** 1.0
**Last Updated:** 2026-10-14
**Maintainer:** Tenable SERM Team
