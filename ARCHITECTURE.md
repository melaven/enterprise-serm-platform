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