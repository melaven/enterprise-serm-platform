# Production Deployment Guide - Tenable SERM

## Overview

Конфигурация для боевого сервера с Nginx Reverse Proxy, SSL termination, Rate Limiting и правильной передачей IP-адресов для Rate Limiter.

## Architecture

```
┌─────────────┐
│   Internet  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Nginx     │  (Port 80/443)
│  Reverse    │  ──► X-Forwarded-For headers
│   Proxy     │  ──► Rate Limiting
└──────┬──────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌─────────────┐      ┌─────────────┐
│  Frontend   │      │   Backend   │
│ (React+Nginx)│      │  (FastAPI)  │
│   Port 80   │      │   Port 8000 │
└─────────────┘      └──────┬──────┘
                            │
                            ├─────────────────────┐
                            │                     │
                            ▼                     ▼
                     ┌─────────────┐      ┌─────────────┐
                     │ PostgreSQL  │      │    Redis    │
                     │  Port 5432  │      │  Port 6379  │
                     └─────────────┘      └─────────────┘
```

## Files

### 1. docker-compose.prod.yml
Production конфигурация Docker Compose с:
- Nginx Reverse Proxy
- PostgreSQL с персистентностью
- Redis с AOF persistence
- FastAPI Backend (4 workers по умолчанию)
- ARQ Worker для фоновых задач
- React Frontend с Nginx

### 2. infra/nginx/nginx.conf
Nginx конфигурация с:
- Reverse Proxy для backend и frontend
- X-Forwarded-For headers для реальных IP
- Rate Limiting zones
- Увеличенные таймауты для парсера
- Gzip compression
- SSL готовая конфигурация (раскомментировать)

### 3. infra/nginx/generate-ssl.sh
Скрипт для генерации самоподписанных SSL сертификатов (только для тестирования)

## Key Features

### X-Forwarded-For Headers

**КРИТИЧЕСКИ ВАЖНО для Rate Limiter:**

Nginx правильно передает реальные IP-адреса клиентов в FastAPI:

```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

**Как это работает в FastAPI:**

```python
from fastapi import Request

@app.get("/api/v1/test")
async def test_endpoint(request: Request):
    # Получение реального IP клиента
    client_ip = request.client.host  # Это будет реальный IP благодаря X-Forwarded-For

    # Если нужно прокси-путь IP
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Первая запись - реальный IP клиента
        client_ip = x_forwarded_for.split(",")[0].strip()

    return {"client_ip": client_ip}
```

**Rate Limiter может использовать IP:**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/protected")
@limiter.limit("10/minute")
async def protected_endpoint(request: Request):
    # Rate limiting по реальному IP клиента
    return {"message": "Protected"}
```

### Rate Limiting Zones

Nginx настраивает 3 зоны rate limiting:

1. **general_limit** - 10 requests/second (общий лимит)
2. **api_limit** - 20 requests/second (API endpoints)
3. **parser_limit** - 5 requests/second (парсер - более строгий)

**Применение:**

```nginx
# Общие endpoint'ы
limit_req zone=general_limit burst=20 nodelay;

# API endpoint'ы
location /api/ {
    limit_req zone=api_limit burst=30 nodelay;
    limit_conn conn_limit 10;
}

# Парсер (долгие запросы)
location /api/v1/parsers/ {
    limit_req zone=parser_limit burst=10 nodelay;
    limit_conn conn_limit 5;
}
```

### Timeouts для Парсера

Парсер может выполнять долгие запросы (LLM анализ, веб-скрапинг), поэтому настроены увеличенные таймауты:

```nginx
# Клиентские таймауты
client_body_timeout 300s;   # 5 минут для загрузки body
client_header_timeout 60s;  # 1 минута для headers
send_timeout 300s;          # 5 минут для отправки ответа

# Proxy таймауты для API
proxy_connect_timeout 60s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;

# Увеличенные таймауты для парсера
location /api/v1/parsers/ {
    proxy_connect_timeout 120s;
    proxy_send_timeout 600s;  # 10 минут
    proxy_read_timeout 600s;  # 10 минут
}
```

### SSL Configuration

Конфигурация SSL готова к использованию (раскомментировать в nginx.conf):

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}
```

## Deployment Steps

### 1. Подготовка .env файла

```bash
# База данных
POSTGRES_USER=serm_user
POSTGRES_PASSWORD=<secure_password>
POSTGRES_DB=serm

# Redis
REDIS_PASSWORD=<secure_password>

# API Settings
WEB_CONCURRENCY=4  # Количество uvicorn workers

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your_service_role_key>

# Gemini AI
GEMINI_API_KEY=<your_gemini_api_key>

# JWT
JWT_SECRET_KEY=<generate_with_openssl_rand_hex_32>
```

### 2. Генерация SSL сертификатов (для тестирования)

```bash
cd nginx
bash generate-ssl.sh
```

**Для продакшена - используйте Let's Encrypt:**

```bash
# Установите certbot
sudo apt-get install certbot

# Получите сертификат
sudo certbot certonly --standalone -d your-domain.com

# Скопируйте сертификаты
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem infra/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem infra/nginx/ssl/key.pem
```

### 3. Запуск production конфигурации

```bash
# Сборка образов
docker-compose -f docker-compose.prod.yml build

# Запуск всех сервисов
docker-compose -f docker-compose.prod.yml up -d

# Проверка статуса
docker-compose -f docker-compose.prod.yml ps

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. Включение SSL (раскомментировать в nginx.conf)

Откройте `infra/nginx/nginx.conf` и:
1. Раскомментируйте `return 301 https://$host$request_uri;` в HTTP server
2. Раскомментируйте весь HTTPS server block
3. Замените `your-domain.com` на ваш домен
4. Перезапустите nginx:

```bash
docker-compose -f docker-compose.prod.yml restart nginx
```

## Monitoring

### Health Checks

```bash
# Nginx health check
curl http://localhost/nginx-health

# Backend health check
curl http://localhost/api/health

# Frontend health check
curl http://localhost/health
```

### Logs

```bash
# Nginx logs
docker-compose -f docker-compose.prod.yml logs nginx

# Backend logs
docker-compose -f docker-compose.prod.yml logs backend

# Worker logs
docker-compose -f docker-compose.prod.yml logs worker

# Все logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Metrics

Nginx логирует в формате с timing metrics:
- `request_time` - общее время запроса
- `upstream_connect_time` - время подключения к backend
- `upstream_header_time` - время получения headers
- `upstream_response_time` - время получения полного ответа

## Security

### Rate Limiter Integration

FastAPI Rate Limiter теперь может корректно работать с реальными IP:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi import Request, HTTPException

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/protected")
@limiter.limit("10/minute")
async def protected_endpoint(request: Request):
    # IP клиента корректно извлекается из X-Forwarded-For
    return {"message": "Protected"}
```

### IP Ban при DDoS

Можно комбинировать tenant_id + IP для жесткого ban:

```python
@app.get("/api/v1/sensitive")
async def sensitive_endpoint(
    request: Request,
    tenant_id: UUID = Depends(get_current_tenant)
):
    # Получаем реальный IP
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.client.host

    # Проверяем blacklist
    if is_ip_banned(client_ip):
        raise HTTPException(status_code=403, detail="IP banned")

    # Проверяем tenant blacklist
    if is_tenant_banned(tenant_id):
        raise HTTPException(status_code=403, detail="Tenant banned")

    return {"message": "OK"}
```

### Security Headers

Nginx добавляет security headers:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (только в HTTPS)

## Troubleshooting

### X-Forwarded-For не работает

**Проблема:** Rate Limiter видит IP Nginx вместо реального IP клиента.

**Решение:**
1. Убедитесь, что в nginx.conf есть:
   ```nginx
   proxy_set_header X-Real-IP $remote_addr;
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   ```
2. В FastAPI используйте `request.headers.get("X-Forwarded-For")`
3. Если есть еще один прокси перед Nginx, настройте `set_real_ip_from`

### Таймауты парсера

**Проблема:** Парсер падает с timeout на долгих запросах.

**Решение:**
1. Увеличьте таймауты в nginx.conf:
   ```nginx
   location /api/v1/parsers/ {
       proxy_read_timeout 600s;
       proxy_send_timeout 600s;
   }
   ```
2. Перезапустите nginx:
   ```bash
   docker-compose -f docker-compose.prod.yml restart nginx
   ```

### Rate Limiting слишком строгий

**Проблема:** Legitimate запросы блокируются.

**Решение:**
1. Увеличьте лимиты в nginx.conf:
   ```nginx
   limit_req_zone $binary_remote_addr zone=api_limit:10m rate=50r/s;
   ```
2. Увеличьте burst:
   ```nginx
   limit_req zone=api_limit burst=50 nodelay;
   ```
3. Перезапустите nginx

### SSL сертификаты

**Проблема:** Браузер показывает предупреждение о небезопасном сертификате.

**Решение:**
- Используйте Let's Encrypt вместо самоподписанных сертификатов
- Убедитесь, что домен совпадает с сертификатом
- Проверьте дату истечения сертификата

## Performance Tuning

### Worker Processes

Увеличьте количество workers в docker-compose.prod.yml:

```yaml
backend:
  environment:
    WEB_CONCURRENCY: 8  # Вместо 4
```

### Nginx Workers

Увеличьте worker_connections в nginx.conf:

```nginx
events {
    worker_connections 4096;  # Вместо 2048
}
```

### Keepalive

Nginx уже настроен с keepalive для upstream:
```nginx
upstream backend {
    keepalive 32;
    keepalive_requests 100;
    keepalive_timeout 60s;
}
```

## Backup Strategy

### PostgreSQL Backup

```bash
# Backup
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U serm_user serm > backup.sql

# Restore
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U serm_user serm < backup.sql
```

### Redis Backup

```bash
# Redis использует AOF persistence
# Backup volume
docker run --rm -v tenable-serm-prod_redis-data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .
```

## Update Strategy

### Rolling Update

```bash
# Pull new images
docker-compose -f docker-compose.prod.yml pull

# Update backend
docker-compose -f docker-compose.prod.yml up -d --no-deps backend

# Update frontend
docker-compose -f docker-compose.prod.yml up -d --no-deps frontend

# Update worker
docker-compose -f docker-compose.prod.yml up -d --no-deps worker
```

### Zero Downtime

Используйте Docker Swarm или Kubernetes для zero-downtime deployments.

---

**Версия:** 1.0
**Последнее обновление:** 2026-10-13
**Мейнтейнер:** Tenable SERM Team
