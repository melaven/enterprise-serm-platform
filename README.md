# SERM API - Service & Economy Reputation Management

API для управления репутацией и расчета экономического влияния отзывов на бизнес.

## 🏗️ Архитектура

Проект построен по **трехслойной архитектуре**:

- **Routers** (HTTP-слой) - прием запросов, валидация, возврат ответов
- **Services** (бизнес-логика) - расчеты SERM, LTV, обработка отзывов  
- **Repositories** (слой данных) - абстракция работы с БД

Подробнее в [ARCHITECTURE.md](ARCHITECTURE.md)

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env`:

```bash
# База данных (PostgreSQL с asyncpg)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/serm_db

# OpenAI API для генерации ответов
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Настройки приложения  
DEBUG=true
LOG_LEVEL=INFO

# SERM параметры (опционально)
DEFAULT_LOST_LEADS_COEFFICIENT=5
DEFAULT_POSITIVE_BOOST_COEFFICIENT=0.5
```

### Настройка для мультитенантности

```bash
# База данных - две роли
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost/serm_db
TENANT_DATABASE_URL=postgresql+asyncpg://app_tenant:password@localhost/serm_db

# JWT аутентификация  
AUTH_JWT_ALGORITHM=RS256
AUTH_JWKS_URL=https://your-project.supabase.co/auth/v1/jwks
```

### 3. Применение миграций

```bash
cd app

# Стандартные миграции
python migrations/run_migration.py

# Миграции мультитенантности
python migrations/run_multitenancy_migration.py
```

### 4. Запуск приложения

```bash
# Из корня проекта
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Или через Python модуль
python -m app.main
```

## 📖 API Документация

После запуска доступна по адресам:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 🔍 Основные endpoints:

#### Экономические операции
```bash
# Симуляция влияния отзыва (без сохранения)
POST /api/v1/economics/simulate

# Полная обработка отзыва  
POST /api/v1/economics/process

# ROI платформы
GET /api/v1/economics/platform/{platform_id}/roi
```

#### Управление отзывами
```bash
# Webhook для внешних интеграций
POST /api/v1/reviews/webhook

# Получение отзыва
GET /api/v1/reviews/{review_id}

# Отзывы платформы с фильтрацией
GET /api/v1/reviews/platform/{platform_id}/reviews
```

#### Компании и платформы
```bash
# CRUD операции с компаниями
GET/POST/PUT/DELETE /api/v1/companies/

# Управление платформами  
GET/POST/PUT/DELETE /api/v1/platforms/

# Дашборд компании
GET /api/v1/companies/{company_id}/dashboard
```

## 🔐 Мультитенантность

SERM API поддерживает мультитенантность через Row Level Security (RLS):

- **JWT аутентификация** с `company_id` в токене
- **Автоматическая изоляция** данных на уровне БД  
- **Безопасные роли** (`postgres` для миграций, `app_tenant` для runtime)
- **Tenant-aware API** - каждая компания видит только свои данные

Подробнее: [MULTITENANCY_GUIDE.md](MULTITENANCY_GUIDE.md)

### Health Check

```bash
curl http://localhost:8000/health
```

### Тестирование обработчиков ошибок

```bash
# Тест различных типов ошибок
GET /api/v1/system/test-errors?error_type=404
GET /api/v1/system/test-errors?error_type=timeout
GET /api/v1/system/test-errors?error_type=llm
```

## 🧪 Тестирование

### Health Check

```bash
curl http://localhost:8000/health
```

### Тестирование обработчиков ошибок

```bash
# Тест различных типов ошибок
GET /api/v1/system/test-errors?error_type=404
GET /api/v1/system/test-errors?error_type=timeout
GET /api/v1/system/test-errors?error_type=llm
```

### Пример создания компании (аутентифицированный)

## 🔧 Разработка

### Структура проекта

```
app/
├── main.py              # Точка входа FastAPI
├── database.py          # Конфигурация БД
├── dependencies.py      # Dependency Injection
├── exceptions.py        # Кастомные исключения
├── handlers.py          # Обработчики ошибок
├── models/             # SQLAlchemy модели
│   └── economics.py
├── schemas/            # Pydantic схемы  
│   └── economics.py
├── repositories/       # Слой данных
│   ├── base.py
│   ├── company.py
│   ├── platform.py
│   └── review.py
├── services/          # Бизнес-логика
│   ├── economics.py
│   ├── llm.py
│   ├── sentiment.py
│   └── review_processor.py
├── routers/           # HTTP endpoints
│   ├── economics.py
│   ├── reviews.py
│   ├── companies.py
│   ├── platforms.py
│   └── system.py
└── migrations/        # Миграции БД
    ├── add_external_review_id.py
    └── run_migration.py
```

### Добавление новых сервисов

1. Создайте класс в `app/services/`
2. Добавьте фабричную функцию в `app/dependencies.py`
3. Используйте через `Depends()` в роутерах

### Создание новых endpoints

1. Создайте роутер в `app/routers/`
2. Подключите в `app/main.py` 
3. Используйте только HTTP-обработку, делегируйте логику в сервисы

## 🔍 Особенности архитектуры

### Dependency Injection

- **Репозитории**: создаются для каждого запроса
- **Сервисы**: могут быть синглтонами (LLM, Sentiment) или per-request
- **Бандлы**: группировка зависимостей для удобства

### Обработка ошибок

- Централизованные exception handlers  
- Стандартизированный JSON формат ответов
- Логирование с Request ID для трассировки
- Локализация ошибок на русском языке

### Интеграции

- **OpenAI API** для генерации ответов на отзывы
- **PostgreSQL** с async поддержкой через asyncpg
- **Supabase** совместимость с connection pooling
- **External Review IDs** для интеграции с Google Maps, 2GIS, Trustpilot

## 📊 Мониторинг

### Логирование

Структурированные логи с уровнями:
- `INFO` - штатная работа  
- `WARNING` - предупреждения
- `ERROR` - ошибки выполнения
- `CRITICAL` - критические ошибки

### Health Checks

```bash
GET /health
```

Проверяет:
- ✅ Подключение к базе данных
- ✅ Доступность OpenAI API  
- ✅ Состояние сервисов

### Трассировка

Каждый запрос получает уникальный `X-Request-ID` для отслеживания в логах.

## 🤝 Contributing

1. Форкните репозиторий
2. Создайте feature branch
3. Следуйте принципам трехслойной архитектуры
4. Добавьте тесты для новой функциональности
5. Создайте Pull Request

## 📝 Лицензия

MIT License - см. [LICENSE](LICENSE) файл.

## 📞 Поддержка

- 📧 Email: support@serm-api.com  
- 📚 Документация: [/docs](http://localhost:8000/docs)
- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/issues)