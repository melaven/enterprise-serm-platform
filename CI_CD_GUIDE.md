# CI/CD Pipeline Guide - Tenable SERM

## Overview

Проект использует GitHub Actions для автоматизации тестирования, линтинга и сборки Docker образов. Пайплайн настроен для защиты от сломанного кода и обеспечения надежности перед деплоем.

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

**Цель:** Проверка качества кода перед тестированием

**Инструменты:**
- **Ruff** - линтер и форматировщик кода
- **MyPy** - статическая типизация (strict mode)

**Команды:**
```bash
ruff check app/ tests/
ruff format --check app/ tests/
mypy app/ --strict
```

**Причины падения:**
- Некорректный синтаксис
- Нарушение PEP8
- Ошибки типизации
- Несоответствие форматированию

### 2. Test Job (Matrix Strategy)

**Цель:** Комплексное тестирование в 4 параллельных потоках

#### 2.1 Unit Tests
- Запуск быстрых тестов без внешних зависимостей
- Покрытие кода (coverage)
- Генерация XML отчетов

#### 2.2 Integration Tests
- Тестирование интеграции с PostgreSQL и Redis
- Проверка миграций базы данных
- Тестирование API endpoints

#### 2.3 Tenant Isolation (RLS) Tests
**КРИТИЧЕСКИ ВАЖНО для мультитенантности:**
- Проверка Row Level Security
- Тестирование изоляции арендаторов
- Проверка, что Tenant A не видит данные Tenant B

**Запускаемые тесты:**
```bash
pytest tests/test_reviews_api.py -v -k "tenant"
pytest tests/test_billing.py -v -k "tenant"
pytest tests/test_auth_session.py -v -k "tenant"
```

#### 2.4 Security Tests
- Проверка JWT аутентификации
- Тестирование квот и billing
- Проверка авторизации на всех эндпоинтах

**Запускаемые тесты:**
```bash
pytest tests/test_auth_session.py -v
pytest tests/test_billing_deps.py -v
```

### 3. Build Job

**Цель:** Сборка Docker образов и проверка безопасности

**Шаги:**
1. Build backend.Dockerfile
2. Build worker.Dockerfile
3. Build frontend.Dockerfile
4. Test docker-compose build
5. **Security Scan (Trivy)** - проверка уязвимостей
6. Upload security results to GitHub Security
7. Push images to Docker Hub (только для main ветки)

## Environment Variables

### Test Environment
```yaml
DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
REDIS_URL: redis://localhost:6379/0
SUPABASE_URL: https://test.supabase.co
SUPABASE_SERVICE_ROLE_KEY: test_key
GEMINI_API_KEY: test_key
JWT_SECRET_KEY: test_secret_key_for_ci
ENVIRONMENT: testing
TEST_DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/test_db
```

### Required GitHub Secrets
- `DOCKER_USERNAME` - Docker Hub username для пуша образов
- `DOCKER_PASSWORD` - Docker Hub password/token

## Tenant Isolation Testing

### Что проверяется:

1. **RLS Policies**
   - Отзывы Tenant A недоступны Tenant B
   - Платформы изолированы по company_id
   - Квоты работают корректно для каждого tenant

2. **JWT Claims**
   - `tenant_id` корректно извлекается из токена
   - `company_id` устанавливается в БД контексте
   - Несуществующий tenant_id отклоняется

3. **Cross-Tenant Data Leakage**
   - Tenant A не может получить данные Tenant B через API
   - SQL инъекции не обходят RLS
   - Прямые SQL запросы с неверным tenant_id блокируются

### Пример теста:

```python
async def test_tenant_isolation():
    # Tenant A создает отзыв
    review_a = await create_review(tenant_id=tenant_a, text="Good")

    # Tenant B пытается получить отзыв Tenant A
    response = await client.get(f"/reviews/{review_a.id}",
                                headers={"X-Tenant-ID": str(tenant_b)})

    # Должен вернуть 404 или 403
    assert response.status_code in [404, 403]
```

## Security Testing

### Что проверяется:

1. **JWT Authentication**
   - Недействительные токены отклоняются
   - Истекшие токены отклоняются
   - Отсутствие токена возвращает 401

2. **Authorization**
   - Анонимный доступ запрещен
   - Неверные роли отклоняются
   - Права доступа проверяются на каждом endpoint

3. **Quota Enforcement**
   - Превышение лимитов блокируется
   - Квоты изолированы по tenant
   - Billing проверки работают корректно

## Database Migrations in CI

**Шаги:**
1. Запуск Python миграций (multitenancy)
2. Запуск Python миграций (additional)
3. Применение SQL миграций через psql:
   - `001_multitenancy_rls.sql` - RLS политики
   - `002_custom_access_token_hook.sql` - Supabase hooks

**Отказоустойчивость:**
- Все миграции запускаются с `|| true`
- Если миграция уже применена, она пропускается
- Ошибка в одной миграции не останавливает пайплайн

## Docker Image Security

### Trivy Scan
- Проверка уязвимостей в образах
- Сканирование зависимостей
- Отчет в SARIF формате для GitHub Security

### Results
- Уязвимости high/critical блокируют деплой
- Results загружаются в GitHub Security tab
- Автоматическое создание issues для критических проблем

## Deployment Flow

### Trigger Conditions
- Push to `main` branch
- Все тесты прошли успешно
- Build job завершен без ошибок

### Deployment Steps
1. Тегирование образов с Git SHA
2. Пуш в Docker Hub
3. Создание deployment summary в GitHub
4. Отображение тега и времени деплоя

### Manual Deployment
Для ручного деплоя на сервер:
```bash
docker pull your-username/tenable-serm-backend:latest
docker pull your-username/tenable-serm-worker:latest
docker pull your-username/tenable-serm-frontend:latest
docker-compose up -d
```

## Troubleshooting

### Lint Failures
```bash
# Локальная проверка
pip install -r requirements-dev.txt
ruff check app/ tests/
ruff format app/ tests/
mypy app/ --strict
```

### Test Failures
```bash
# Локальный запуск с теми же переменными
export DATABASE_URL="postgresql+asyncpg://test_user:test_password@localhost:5432/test_db"
export REDIS_URL="redis://localhost:6379/0"
pytest tests/ -v --asyncio-mode=auto
```

### Tenant Isolation Failures
```bash
# Запуск только tenant тестов
pytest tests/test_reviews_api.py -v -k "tenant"
pytest tests/test_billing.py -v -k "tenant"
```

### Docker Build Failures
```bash
# Локальная сборка
docker-compose build
# Отдельно
docker build -f backend.Dockerfile -t test-backend .
docker build -f worker.Dockerfile -t test-worker .
docker build -f frontend.Dockerfile -t test-frontend .
```

## Best Practices

### 1. Pre-commit Hooks
Установите pre-commit для локальной проверки:
```bash
pip install pre-commit
pre-commit install
```

### 2. Test Naming
Используйте описательные имена тестов:
```python
async def test_tenant_a_cannot_access_tenant_b_reviews():
    # ...
```

### 3. Test Markers
Используйте pytest markers для группировки:
```python
@pytest.mark.integration
async def test_api_integration():
    # ...

@pytest.mark.tenant
async def test_tenant_isolation():
    # ...
```

### 4. Coverage Goals
- Минимальное покрытие: 80%
- Целевое покрытие: 90%
- Критические модули: 95%+

## Monitoring

### GitHub Actions Status
- Зеленый галочка = все хорошо
- Красный крест = сломанный код, не деплоить
- Желтый = warnings, требует внимания

### Coverage Reports
- Codecov автоматически загружает coverage
- Проверьте % покрытия в PR
- New code должен иметь покрытие > 80%

### Security Alerts
- GitHub Security tab показывает уязвимости
- Trivy findings в PR comments
- Critical issues требуют немедленного исправления

## Future Enhancements

### Planned Additions
- [ ] E2E tests с реальным браузером (Playwright)
- [ ] Performance testing (Locust)
- [ ] Load testing в CI
- [ ] Automatic rollback при failed deployment
- [ ] Canary deployments
- [ ] Blue-green deployments

### Possible Integrations
- [ ] SonarQube для code quality
- [ ] Snyk для dependency scanning
- [ ] OWASP ZAP для security testing
- [ ] Datadog/APM для monitoring

## Support

Если пайплайн падает:
1. Проверьте logs в GitHub Actions
2. Запустите failing tests локально
3. Убедитесь, что .env локально настроен корректно
4. Проверьте зависимости в requirements.txt
5. Свяжитесь с DevOps командой

---

**Версия:** 1.0
**Последнее обновление:** 2026-10-13
**Мейнтейнер:** Tenable SERM Team
