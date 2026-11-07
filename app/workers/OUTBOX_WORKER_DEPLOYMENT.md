# Outbox Worker Deployment Guide

## Dual-Worker Architecture

SentiGuard uses two separate ARQ worker instances to process outbox events based on priority:

### Q1: Critical Worker (Priority 1)
- **Purpose**: Immediate processing of high-priority events
- **Use cases**: Manual review creation, real-time notifications, urgent feedback
- **Configuration**: `CriticalWorkerSettings`
- **Cron interval**: Every 5 seconds
- **Batch size**: 20 events
- **Max concurrent jobs**: 4
- **Job timeout**: 60 seconds

### Q2: Bulk Worker (Priority 2)
- **Purpose**: Batch processing of lower-priority events
- **Use cases**: Mass import, scheduled analytics, non-urgent tasks
- **Configuration**: `BulkWorkerSettings`
- **Cron interval**: Every 30 seconds
- **Batch size**: 100 events
- **Max concurrent jobs**: 2
- **Job timeout**: 180 seconds

## Startup Instructions

### Option 1: Two Separate Processes (Recommended)

Run both workers in separate terminal sessions or via systemd/supervisor:

```bash
# Terminal 1: Critical Worker (Q1)
arq worker --settings app.workers.outbox_worker.CriticalWorkerSettings

# Terminal 2: Bulk Worker (Q2)
arq worker --settings app.workers.outbox_worker.BulkWorkerSettings
```

### Option 2: Systemd Service Files

Create `/etc/systemd/system/sentiguard-outbox-critical.service`:

```ini
[Unit]
Description=SentiGuard Critical Outbox Worker (Q1)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=sentiguard
WorkingDirectory=/path/to/SentiGuard
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/arq worker --settings app.workers.outbox_worker.CriticalWorkerSettings
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/sentiguard-outbox-bulk.service`:

```ini
[Unit]
Description=SentiGuard Bulk Outbox Worker (Q2)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=sentiguard
WorkingDirectory=/path/to/SentiGuard
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/arq worker --settings app.workers.outbox_worker.BulkWorkerSettings
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable sentiguard-outbox-critical
sudo systemctl enable sentiguard-outbox-bulk
sudo systemctl start sentiguard-outbox-critical
sudo systemctl start sentiguard-outbox-bulk
```

### Option 3: Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  outbox-critical:
    build: .
    command: arq worker --settings app.workers.outbox_worker.CriticalWorkerSettings
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  outbox-bulk:
    build: .
    command: arq worker --settings app.workers.outbox_worker.BulkWorkerSettings
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
```

## Environment Variables

Both workers require the same environment variables:

```bash
# Database
TENANT_DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM (for reply generation)
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

## Monitoring

Check worker status:

```bash
# Critical worker logs
sudo journalctl -u sentiguard-outbox-critical -f

# Bulk worker logs
sudo journalctl -u sentiguard-outbox-bulk -f
```

## Scaling

For high-traffic scenarios:

- **Critical worker**: Scale horizontally (multiple instances with same settings)
- **Bulk worker**: Increase `max_jobs` or add more instances

Example scaling with systemd:

```bash
# 3 critical workers
sudo systemctl enable sentiguard-outbox-critical@{1,2,3}
sudo systemctl start sentiguard-outbox-critical@{1,2,3}
```

## Priority Logic

Events are processed in order:
1. Critical worker checks `priority=1` events first
2. If no critical events, checks `priority=2` events
3. Row-level locking (`SKIP LOCKED`) prevents duplicates across workers

This ensures:
- Manual reviews get processed immediately (Q1)
- Mass imports don't block critical events (Q2)
- Horizontal scaling is safe (no race conditions)
