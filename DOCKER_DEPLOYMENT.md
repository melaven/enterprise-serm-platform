# Docker Production Deployment Guide

## Overview

This project now has a complete Docker infrastructure for production deployment on an isolated server. The setup includes:

- **backend.Dockerfile** - FastAPI application with uvicorn
- **worker.Dockerfile** - ARQ worker for background tasks
- **frontend.Dockerfile** - Multi-stage build with Nginx for static serving
- **docker-compose.yml** - Orchestrates all services with PostgreSQL and Redis
- **nginx.conf** - Nginx configuration for frontend with API proxy

## Prerequisites

- Docker 24.0+
- Docker Compose 2.0+
- At least 2GB RAM and 10GB disk space

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# PostgreSQL
POSTGRES_USER=serm_user
POSTGRES_PASSWORD=<secure_password>
POSTGRES_DB=serm

# Redis
REDIS_PASSWORD=<secure_password>

# API Settings
API_BIND=127.0.0.1  # Change to 0.0.0.0 if running without reverse proxy
API_PORT=8000
WEB_CONCURRENCY=2

# Frontend Settings
FRONTEND_BIND=0.0.0.0
FRONTEND_PORT=80

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your_service_role_key>

# Groq LLM
GROQ_API_KEY=<your_groq_api_key>

# JWT Secret
JWT_SECRET_KEY=<generate_with_openssl_rand_hex_32>
```

## Service Architecture

```
┌─────────────┐
│  Frontend   │ (Nginx on port 80)
│  (React)    │
└──────┬──────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌─────────────┐      ┌─────────────┐
│   Backend   │      │   Worker    │
│  (FastAPI)  │      │    (ARQ)    │
│  Port 8000  │      │             │
└──────┬──────┘      └──────┬──────┘
       │                    │
       │                    │
       ▼                    ▼
┌─────────────┐      ┌─────────────┐
│ PostgreSQL  │      │    Redis    │
│  Port 5432  │      │  Port 6379  │
└─────────────┘      └─────────────┘
```

## Network Configuration

All services communicate via the `backend` Docker network:

- Frontend proxies `/api/*` requests to `backend:8000`
- Backend connects to `postgres:5432` and `redis:6379`
- Worker connects to `postgres:5432` and `redis:6379`
- Redis and PostgreSQL are NOT exposed externally (only internal)

## Quick Start

1. **Build and start all services:**
   ```bash
   docker-compose up -d --build
   ```

2. **Check service status:**
   ```bash
   docker-compose ps
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f
   ```

4. **Stop services:**
   ```bash
   docker-compose down
   ```

## Individual Service Management

### Backend Only
```bash
docker-compose up -d backend
```

### Worker Only
```bash
docker-compose up -d worker
```

### Frontend Only
```bash
docker-compose up -d frontend
```

## Health Checks

All services have health checks configured:

- **PostgreSQL**: `pg_isready` every 5s
- **Redis**: `redis-cli ping` every 5s
- **Backend**: TCP connection check on port 8000 every 15s
- **Worker**: ARQ health check every 30s
- **Frontend**: HTTP check on `/health` every 30s

View health status:
```bash
docker-compose ps
```

## Security Features

All Python services run with:
- Non-root user (uid 10001)
- Read-only filesystem (except /tmp)
- No capabilities dropped
- No new privileges flag
- Resource limits via Docker

## Volume Persistence

Data persists across container restarts:
- `postgres-data` - PostgreSQL database
- `redis-data` - Redis append-only file

To backup volumes:
```bash
docker run --rm -v tenable-serm_postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz -C /data .
docker run --rm -v tenable-serm_redis-data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .
```

## Scaling

### Scale Workers
```bash
docker-compose up -d --scale worker=3
```

### Scale Backend
```bash
docker-compose up -d --scale backend=2
```

Note: Ensure `WEB_CONCURRENCY` is adjusted appropriately when scaling.

## Troubleshooting

### Backend not starting
```bash
docker-compose logs backend
# Check if postgres and redis are healthy
docker-compose ps postgres redis
```

### Worker not processing tasks
```bash
docker-compose logs worker
# Verify Redis connection
docker-compose exec redis redis-cli -a $REDIS_PASSWORD ping
```

### Frontend not serving
```bash
docker-compose logs frontend
# Check if backend is accessible
docker-compose exec frontend wget -O- http://backend:8000/api/health
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

### Clean rebuild (no cache)
```bash
docker-compose build --no-cache
docker-compose up -d
```

## Production Considerations

1. **Reverse Proxy**: Consider using Caddy or Nginx as a reverse proxy for SSL termination
2. **Secrets Management**: Use Docker Secrets or external secret manager instead of .env
3. **Monitoring**: Add Prometheus/Grafana for metrics
4. **Log Aggregation**: Configure centralized logging (ELK, Loki, etc.)
5. **Backup Strategy**: Implement automated volume backups
6. **Update Strategy**: Use rolling updates for zero-downtime deployments

## Auto-Migrations

The backend container automatically runs database migrations on startup:

1. Waits for PostgreSQL to be ready (using netcat)
2. Runs `scripts/migrate.py`
3. Executes the ordered SQL chain from `migrations/*.sql`
4. Only then starts the uvicorn server

This ensures your database schema is always up-to-date without manual intervention.

## CI/CD Pipeline

The project includes a GitHub Actions workflow (`.github/workflows/main.yml`) that:

### Lint Job
- Runs Ruff linter on `app/` and `tests/`
- Checks code formatting
- Fails if linting errors are found

### Test Job
- Spins up PostgreSQL and Redis containers
- Runs database migrations
- Executes all integration tests with pytest
- Generates coverage reports
- Uploads coverage to Codecov (optional)

### Build Job (main branch only)
- Builds all Docker images (backend, worker, frontend)
- Tests docker-compose build
- Optionally pushes images to Docker Hub

### Pipeline Flow
```
push to main → lint → test → build → (optional: push to registry)
```

**Broken code never reaches production** - the pipeline stops at the first failing stage.

### Required GitHub Secrets (for Docker push)
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub password/token

### Local Testing
To test the pipeline locally before pushing:

```bash
# Run linting
pip install ".[dev]"
ruff check app/ tests/
ruff format --check app/ tests/

# Run tests with docker-compose
docker-compose -f docker-compose.yml up -d postgres redis
DATABASE_URL=postgresql+asyncpg://serm_user:password@localhost:5432/serm \
REDIS_URL=redis://localhost:6379/0 \
pytest tests/ -v
docker-compose down
```

## Access Points

- **Frontend**: http://localhost:80 (or configured FRONTEND_PORT)
- **Backend API**: http://localhost:8000 (or configured API_PORT)
- **PostgreSQL**: Internal only (postgres:5432)
- **Redis**: Internal only (redis:6379)

## File Structure

```
.
├── backend.Dockerfile          # FastAPI backend image with auto-migrations
├── worker.Dockerfile           # ARQ worker image
├── frontend.Dockerfile         # React frontend with Nginx
├── docker-entrypoint.sh       # Backend entrypoint with auto-migrations
├── nginx.conf                  # Nginx configuration
├── docker-compose.yml          # Service orchestration
├── .dockerignore              # Docker build exclusions
├── frontend/.dockerignore      # Frontend build exclusions
├── .github/workflows/main.yml # CI/CD pipeline
└── DOCKER_DEPLOYMENT.md       # This file
```

## Next Steps

1. Set up your `.env` file with production values
2. Run `docker-compose up -d --build` to start services
3. Configure reverse proxy (optional but recommended)
4. Set up monitoring and backup strategies
5. Configure SSL certificates for production
