# Руководство по мультитенантности SERM API

## Обзор

SERM API поддерживает мультитенантность через Row Level Security (RLS) в PostgreSQL. Каждая компания является отдельным tenant и видит только свои данные.

## Архитектура мультитенантности

### Основные компоненты

1. **JWT аутентификация** - токен содержит `company_id` (tenant ID)
2. **Row Level Security (RLS)** - автоматическая фильтрация данных на уровне БД
3. **Tenant Session** - сессия с установленным контекстом `app.company_id`
4. **Изолированные роли** - `postgres` (админ) и `app_tenant` (runtime)

### Поток аутентификации

```
1. Клиент → JWT Token → FastAPI
2. JWT проверка → AuthContext (user_id, company_id)
3. Установка app.company_id → RLS фильтрация
4. Запросы видят только данные своего tenant
```

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и настройте:

```bash
# Роль postgres для миграций
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/serm_db

# Роль app_tenant для runtime  
TENANT_DATABASE_URL=postgresql+asyncpg://app_tenant:tenant_password@localhost:5432/serm_db

# JWT настройки
AUTH_JWT_ALGORITHM=RS256
AUTH_JWKS_URL=https://your-project.supabase.co/auth/v1/jwks
```

### 3. Применение миграций

```bash
cd app
python migrations/run_multitenancy_migration.py
```

### 4. Дополнительная настройка

После миграций:

1. **Установите пароль для app_tenant**:
```sql
ALTER ROLE app_tenant PASSWORD 'secure_password';
```

2. **Включите Custom Access Token Hook** в Supabase Dashboard:
   - Authentication → Hooks → Custom Access Token

3. **Заполните таблицу company_members**:
```sql
INSERT INTO company_members (user_id, company_id, role) VALUES 
('user-uuid-1', 'company-uuid-1', 'owner'),
('user-uuid-2', 'company-uuid-1', 'member');
```

4. **Выполните бэкфилл company_id в reviews**:
```sql
UPDATE reviews SET company_id = (
    SELECT company_id FROM platforms 
    WHERE platforms.id = reviews.platform_id
) WHERE company_id IS NULL;
```

## Использование в коде

### JWT аутентификация

```python
from app.dependencies import get_auth_context
from app.auth import AuthContext

# В роутере
async def my_endpoint(
    auth_context: AuthContext = Depends(get_auth_context)
):
    # Автоматически получаем user_id и company_id из JWT
    user_id = auth_context.user_id
    company_id = auth_context.company_id  # tenant ID
```

### Tenant-aware репозитории

```python
from app.dependencies import get_review_repository
from app.repositories import ReviewRepository

# Репозиторий автоматически изолирован по tenant
async def get_reviews(
    review_repo: ReviewRepository = Depends(get_review_repository)
):
    # Видит только отзывы своей компании благодаря RLS
    reviews = await review_repo.get_all()
```

### Tenant Session

```python
from app.auth import get_tenant_session, AuthContext

async with await get_tenant_session(auth_context) as session:
    # app.company_id установлен автоматически
    result = await session.execute("SELECT * FROM reviews")
    # Возвращает только данные текущего tenant
```

## Безопасность

### Row Level Security (RLS)

Политики RLS применяются автоматически:

```sql
-- Компании видят только свои записи
CREATE POLICY companies_policy ON companies
FOR ALL TO app_tenant
USING (id = current_setting('app.company_id')::uuid);

-- Платформы фильтруются по company_id  
CREATE POLICY platforms_policy ON platforms
FOR ALL TO app_tenant
USING (company_id = current_setting('app.company_id')::uuid);

-- Отзывы изолированы по company_id
CREATE POLICY reviews_policy ON reviews  
FOR ALL TO app_tenant
USING (company_id = current_setting('app.company_id')::uuid);
```

### Изоляция ролей

- **`postgres`** - полные права, только для миграций и админки
- **`app_tenant`** - ограниченные права, не может обходить RLS

### JWT Security

- Поддержка RS256 с JWKS (рекомендуется)
- Legacy HS256 для разработки
- Проверка подписи и срока действия токена
- Извлечение `company_id` из различных claims

## Тестирование изоляции

### Smoke Test

```bash
# Проверка что RLS работает
cd app
python -c "
import asyncio
from database import engine
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

Должен вернуть 0 для обоих случаев.

### Unit тесты

```python
import pytest
from app.auth import JWTHandler

@pytest.mark.asyncio
async def test_jwt_verification():
    handler = JWTHandler()
    
    # Тест с валидным токеном
    token = "valid.jwt.token"
    context = await handler.verify_token(token)
    
    assert context.user_id is not None
    assert context.company_id is not None

@pytest.mark.asyncio  
async def test_tenant_isolation(tenant_db_session):
    # Данные должны быть изолированы по tenant
    reviews = await review_repo.get_all()
    
    # Все отзывы должны принадлежать одной компании
    company_ids = {r.company_id for r in reviews}
    assert len(company_ids) <= 1
```

## Troubleshooting

### Проблемы с RLS

**Симптом**: Запросы возвращают 0 строк

**Решение**:
1. Проверьте что установлен `app.company_id`:
```sql
SELECT current_setting('app.company_id', true);
```

2. Проверьте что RLS включен:
```sql
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
```

3. Проверьте политики:
```sql
SELECT * FROM pg_policies WHERE schemaname = 'public';
```

### Проблемы с JWT

**Симптом**: 401 Unauthorized

**Решение**:
1. Проверьте формат токена: `Authorization: Bearer <token>`
2. Проверьте JWKS URL доступность
3. Проверьте что токен содержит `company_id`

### Проблемы с ролями

**Симптом**: Permission denied

**Решение**:
1. Проверьте что используете `TENANT_DATABASE_URL`
2. Убедитесь что роль `app_tenant` существует
3. Проверьте права доступа к таблицам

## Мониторинг

### Логирование

Все операции логируются с tenant context:

```
INFO - User authenticated: user-id-123, company: company-id-456
DEBUG - Tenant context set: company_id=company-id-456  
DEBUG - Tenant session closed: company_id=company-id-456
```

### Метрики

Отслеживайте:
- Количество запросов по tenant
- Время установки tenant context
- Ошибки аутентификации по tenant
- Нарушения изоляции (должно быть 0)

### Health Checks

```bash
GET /health
```

Проверяет:
- ✅ Подключение к БД (tenant роль)
- ✅ JWT Handler (JWKS доступность)  
- ✅ LLM сервис
- ✅ Конфигурацию мультитенантности

## Производительность

### Оптимизация RLS

1. **Индексы по company_id** - созданы автоматически
2. **Партиционирование** - рассмотрите для больших таблиц
3. **Connection pooling** - NullPool для Supabase

### Кэширование

- JWT claims кэшируются до истечения токена
- JWKS кэшируется на 1 час
- Singleton сервисы переиспользуются

## Развертывание

### Environment Variables

```bash
# Production
USE_TENANT_ROLE=true
AUTH_JWT_ALGORITHM=RS256
SQL_ECHO=false

# Development  
USE_TENANT_ROLE=false  # Для отладки без RLS
SQL_ECHO=true         # Для просмотра SQL запросов
```

### CI/CD

1. Миграции выполняются под `postgres` ролью
2. Runtime использует `app_tenant` роль  
3. Smoke tests проверяют изоляцию
4. Health checks проверяют все компоненты

## Best Practices

1. **Всегда используйте tenant-aware dependencies**
2. **Не используйте `session.commit()` в middleware**  
3. **Тестируйте изоляцию для каждой новой таблицы**
4. **Логируйте все операции с tenant context**
5. **Мониторьте нарушения безопасности**
6. **Регулярно ротируйте JWT секреты**