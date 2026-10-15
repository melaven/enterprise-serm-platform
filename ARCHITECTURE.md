# Архитектура SERM API

## Обзор

SERM (Service & Economy Reputation Management) API построен по трехслойной архитектуре с централизованной обработкой ошибок и dependency injection.

## Архитектурные слои

### 1. Слой маршрутизации (Routers/API)

**Расположение**: `app/routers/`

**Ответственность**:
- Прием HTTP-запросов
- Валидация входящих данных через Pydantic
- Возврат стандартизированных ответов
- **НЕ содержит бизнес-логику**

**Файлы**:
- `economics.py` - экономические операции и симуляции
- `reviews.py` - управление отзывами и webhook
- `companies.py` - CRUD операции с компаниями  
- `platforms.py` - управление платформами размещения
- `system.py` - системные endpoints (тестирование, диагностика)

### 2. Слой бизнес-логики (Services)

**Расположение**: `app/services/`

**Ответственность**:
- Вся математика SERM (расчет LTV, оценка влияния негатива)
- Координация между репозиториями
- Бизнес-правила и валидация
- Интеграция с внешними API (OpenAI)

**Файлы**:
- `economics.py` - расчеты финансового влияния, ROI, рисков
- `llm.py` - генерация ответов на отзывы через OpenAI
- `sentiment.py` - анализ тональности и приоритизация
- `review_processor.py` - центральный координатор обработки отзывов

### 3. Слой данных (Repositories/DAL)

**Расположение**: `app/repositories/`

**Ответственность**:
- Абстракция доступа к данным
- CRUD операции
- Сложные запросы и агрегация
- Изоляция от изменений в схеме БД

**Файлы**:
- `base.py` - базовый репозиторий с общими операциями
- `company.py` - операции с компаниями
- `platform.py` - управление платформами
- `review.py` - работа с отзывами и аналитика

## Централизованная обработка ошибок

**Файлы**:
- `exceptions.py` - кастомные исключения для разных типов ошибок
- `handlers.py` - глобальные обработчики с стандартизированным JSON

**Типы ошибок**:
- `NotFoundError` (404) - ресурс не найден
- `AccessDeniedError` (403) - нехватка прав доступа  
- `DatabaseError` (500/503) - ошибки БД и таймауты
- `LLMServiceError` (502) - проблемы с OpenAI API
- `EconomicsCalculationError` (400) - ошибки в расчетах

## Dependency Injection

**Файл**: `app/dependencies.py`

**Принципы**:
- Фабричные функции для создания экземпляров
- Синглтоны для stateless сервисов (LLM, Sentiment)
- Бандлы для группировки зависимостей
- Health check для мониторинга состояния

**Граф зависимостей**:
```
FastAPI Router
    ↓
Service Layer (Business Logic)
    ↓  
Repository Layer (Data Access)
    ↓
Database (PostgreSQL/Supabase)
```

## Модели данных

**Файлы**:
- `models/economics.py` - SQLAlchemy модели
- `schemas/economics.py` - Pydantic схемы для API

**Основные сущности**:
- `Company` - компания с экономическими показателями
- `Platform` - платформа размещения отзывов (Google Maps, 2GIS)
- `Review` - отзыв с анализом влияния и статусом обработки

## Конфигурация

**Environment Variables**:
```bash
DATABASE_URL=postgresql+asyncpg://...
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
DEBUG=false
LOG_LEVEL=INFO
```

## API Endpoints

### Economics (`/api/v1/economics/`)
- `POST /simulate` - симуляция влияния отзыва
- `POST /process` - полная обработка отзыва с сохранением
- `POST /bulk-process` - массовая обработка
- `GET /platform/{id}/roi` - ROI платформы
- `GET /platform/{id}/risk-assessment` - оценка рисков

### Reviews (`/api/v1/reviews/`)
- `POST /webhook` - прием отзывов от внешних систем
- `GET /{id}` - получение отзыва по ID
- `GET /platform/{id}/reviews` - отзывы платформы
- `PUT /{id}/status` - обновление статуса
- `GET /search` - поиск по содержимому

### Companies (`/api/v1/companies/`)
- `POST /` - создание компании
- `GET /{id}` - информация о компании
- `PUT /{id}/economics` - обновление показателей
- `GET /{id}/dashboard` - сводная аналитика

### Platforms (`/api/v1/platforms/`)
- `POST /` - создание платформы
- `GET /company/{id}/platforms` - платформы компании
- `PUT /{id}/metrics` - обновление метрик
- `GET /stats` - статистика платформ

### Parsers (`/api/v1/parsers/`)
- `POST /start` - проверка квоты и постановка задачи парсинга в очередь
- `GET /status/{job_id}` - получение статуса задачи

Перед постановкой задачи `POST /start` атомарно списывает запрос одним
`UPDATE ... FROM ... RETURNING`: активность организации и лимит тарифа
проверяются в том же SQL-запросе, что и обновление счётчика. Если списание
невозможно, endpoint возвращает HTTP 402 и задача не отправляется в очередь.

## Безопасность

- Валидация всех входных данных через Pydantic
- Параметризированные SQL-запросы (защита от инъекций)
- Централизованная обработка ошибок (не показываем внутренние детали)
- CORS настройки
- Request ID для трассировки

## Monitoring & Observability

- Структурированное логирование
- Health checks (`/health`)
- Request tracing с уникальными ID
- Метрики производительности
- Граф зависимостей в debug режиме

## Порядок чтения проекта для нового разработчика

Если открыть репозиторий “с нуля”, читать стоит в этом порядке, чтобы не потеряться в структуре.

### 1. Входные документы
- [README.md](README.md) — общее описание проекта, стек, запуск, основные сценарии
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектурная карта и базовые принципы
- [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md) — более техническая карта backend
- [frontend/FRONTEND_ARCHITECTURE.md](frontend/FRONTEND_ARCHITECTURE.md) — фронтенд-структура и модульность

### 2. Точки входа в приложение
- [app/main.py](app/main.py) — главный entrypoint FastAPI
- [app/core/dependencies.py](app/core/dependencies.py) — DI и фабрики сервисов/репозиториев
- [app/core/database.py](app/core/database.py) — БД и сессии
- [app/core/auth.py](app/core/auth.py) — аутентификация и авторизация
- [app/core/tenant.py](app/core/tenant.py) — tenant context

### 3. HTTP-уровень
- [app/routers](app/routers) — API endpoints
  - `auth.py` — логин/регистрация/токены
  - `reviews.py` — отзывы
  - `companies.py` — компании
  - `platforms.py` — платформы
  - `economics.py` — экономика и расчёты
  - `analytics.py` — аналитика
  - `parser.py` — запуск и статус парсинга
  - `reputation.py` — репутация и сводные метрики

### 4. Бизнес-логика
- [app/services](app/services) — доменная логика
  - `economics.py` — финансовые и экономические расчёты
  - `review_processor.py` — основной workflow обработки отзывов
  - `llm.py` / `llm_analyzer.py` — AI-логика и анализ текста
  - `sentiment.py` — скоринг тональности
  - `parser.py` — парсинг данных
  - `billing.py` — квоты и биллинг
  - `analytics.py` — аналитические агрегаты
  - `worker/` — фоновые задачи и ARQ worker

### 5. Данные и доступ к БД
- [app/repositories](app/repositories) — репозитории
  - `company.py`, `platform.py`, `review.py`
  - `analytics_repo.py`
  - `dlq.py`
  - `parser.py`
- [app/models](app/models) — SQLAlchemy модели
- [app/schemas](app/schemas) — Pydantic контракты API и доменных объектов

### 6. Интеграции и инфраструктура
- [migrations](migrations) — миграции БД
- [scripts](scripts) — утилиты миграций и seed
- [docker-compose.yml](docker-compose.yml) — локальная инфраструктура
- [docker-compose.prod.yml](docker-compose.prod.yml) — продовая конфигурация
- [run.py](run.py) — запуск backend
- [worker.py](worker.py) — отдельный worker entrypoint

### 7. Frontend
- [frontend](frontend) — React/Vite приложение
  - [frontend/src](frontend/src) — основной код UI
  - `api/` — HTTP клиент и интеграции
  - `features/` — feature-модули
  - `pages/` — маршруты
  - `components/` — UI-компоненты

### 8. Тесты и качества
- [tests](tests) — backend tests
- `*.test.ts` / `*.test.py` — проверка контрактов и логики
- `pytest.ini` и configuration files — настройки тестового окружения

## Карта ответственности проекта

```text
frontend/
  ├─ pages/              -> маршруты и экраны
  ├─ features/           -> бизнес-фичи
  ├─ components/         -> переиспользуемые UI-компоненты
  └─ api/                -> HTTP-контракты и запросы

app/
  ├─ routers/            -> HTTP API
  ├─ services/           -> бизнес-логика
  ├─ repositories/       -> доступ к данным
  ├─ models/             -> сущности БД
  ├─ schemas/            -> вход/выход контракты
  ├─ core/               -> auth, tenant, middleware, config, DI
  └─ main.py             -> сборка приложения

worker/
  ├─ parsing tasks       -> фоновые задачи
  ├─ queue/ARQ           -> асинхронная очередь
  └─ DLQ / retries       -> надежность обработчика

migrations/
  └─ database schema     -> схема и эволюция БД
```

## Быстрый маршрут для нового участника

Если нужно быстро войти в проект и понять, где что лежит:

1. Открыть [README.md](README.md)
2. Прочитать [ARCHITECTURE.md](ARCHITECTURE.md)
3. Открыть [app/main.py](app/main.py)
4. Посмотреть [app/core/dependencies.py](app/core/dependencies.py)
5. Далее идти по роутерам в [app/routers](app/routers)
6. Затем в сервисы в [app/services](app/services)
7. Потом в репозитории в [app/repositories](app/repositories)
8. И только после этого смотреть frontend в [frontend](frontend)

Это даёт “горизонтальный” путь по архитектуре без хаоса и повторных поисков по папкам.

## Масштабирование

**Текущая архитектура поддерживает**:
- Горизонтальное масштабирование (stateless сервисы)
- Кэширование на уровне dependency injection
- Connection pooling для БД (NullPool для Supabase)
- Асинхронная обработка запросов

**Возможные улучшения**:
- Redis для кэширования расчетов
- Message queues для асинхронной обработки
- Микросервисная декомпозиция по доменам
- Event sourcing для аудита изменений