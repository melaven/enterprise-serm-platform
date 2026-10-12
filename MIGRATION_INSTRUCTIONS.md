# 🔧 Инструкции по применению миграций для Dashboard API

## Проблема
Dashboard API эндпоинты (`GET /api/v1/reviews` и `/api/v1/reviews/summary`) не работают из-за отсутствующих колонок в таблице `reviews`:
- ❌ `company_id` — требуется для RLS изоляции по tenant
- ❌ `sentiment` — требуется для KPI-метрики sentiment_distribution

## Решение
Выполнить 2 миграции в Supabase SQL Editor:

---

## Миграция 1: Добавление `company_id` для мультитенантности

**Файл:** `app/migrations/004_update_models_for_multitenancy.py`

**SQL скрипт для Supabase:**

```sql
-- Миграция 004: Мультитенантность для reviews
BEGIN;

-- 1. Добавляем company_id
ALTER TABLE public.reviews 
  ADD COLUMN IF NOT EXISTS company_id UUID 
  REFERENCES companies(id) ON DELETE CASCADE;

-- 2. Создаем индексы для производительности RLS
CREATE INDEX IF NOT EXISTS ix_reviews_company_id ON reviews(company_id);
CREATE INDEX IF NOT EXISTS ix_reviews_platform_company ON reviews(platform_id, company_id);
CREATE INDEX IF NOT EXISTS ix_reviews_status_company ON reviews(status, company_id);
CREATE INDEX IF NOT EXISTS ix_reviews_external_id ON reviews(external_review_id) WHERE external_review_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_platforms_company_id ON platforms(company_id);

-- 3. Бэкфилл company_id в reviews
UPDATE reviews 
SET company_id = platforms.company_id
FROM platforms 
WHERE reviews.platform_id = platforms.id 
  AND reviews.company_id IS NULL;

-- 4. Делаем company_id обязательным (если все заполнены)
-- Раскомментировать после проверки что все reviews имеют company_id:
-- ALTER TABLE reviews ALTER COLUMN company_id SET NOT NULL;

COMMIT;
```

**Проверка:**
```sql
-- Должно вернуть 0
SELECT COUNT(*) FROM reviews WHERE company_id IS NULL;
```

---

## Миграция 2: Добавление AI-полей (sentiment, tags, etc.)

**Файл:** `app/migrations/010_reviews_ai_fields.sql`

**SQL скрипт для Supabase:**

```sql
-- Миграция 010: AI enrichment поля
BEGIN;

ALTER TABLE public.reviews
  ADD COLUMN IF NOT EXISTS sentiment varchar(20),
  ADD COLUMN IF NOT EXISTS tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS is_critical boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS auto_reply text,
  ADD COLUMN IF NOT EXISTS ai_pending boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS ai_error text;

COMMIT;
```

**Проверка:**
```sql
-- Должна вернуть структуру с новыми колонками
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'reviews' 
  AND column_name IN ('company_id', 'sentiment', 'tags', 'is_critical')
ORDER BY column_name;
```

---

## Как применить

### Вариант A: Через Supabase Dashboard (Рекомендуется)

1. Открыть Supabase Dashboard: https://app.supabase.com
2. Выбрать проект: `wdagxpgabnxotmfmreev`
3. Перейти в **SQL Editor**
4. Создать **New Query**
5. Скопировать SQL скрипт миграции 004
6. Нажать **Run**
7. Проверить результат
8. Повторить для миграции 010

### Вариант B: Через Python скрипт (Локально)

```bash
# Находясь в корне проекта
python app/migrations/run_multitenancy_migration.py
```

**Примечание:** Скрипт должен быть обновлен для работы с Supabase async connection.

---

## После применения миграций

1. **Перезапустить API:**
   ```bash
   # Остановить текущий процесс (Ctrl+C)
   # Запустить снова
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Протестировать Dashboard API:**
   ```bash
   python test_dashboard_api.py
   ```

3. **Ожидаемый результат:**
   ```
   ✅ Логин успешен
   ✅ Список отзывов получен
   ✅ KPI-метрики получены
   ✅ Фильтрация работает
   ```

---

## Текущий статус тестирования

```
============================================================
DASHBOARD API TEST RESULTS
============================================================

✅ 1. АВТОРИЗАЦИЯ - PASS
   - JWT token generation: WORKING
   - User: test@example.com
   - Token format: ES256 (Supabase)

❌ 2. GET /api/v1/reviews - FAIL
   - Error: column reviews.company_id does not exist
   - Status: 500 Internal Server Error
   - Fix: Apply migration 004

❌ 3. GET /api/v1/reviews/summary - FAIL
   - Error: column reviews.sentiment does not exist
   - Status: 500 Internal Server Error
   - Fix: Apply migration 010

❌ 4. Filtering (rating=5, platform=google) - FAIL
   - Error: Same as #2 (company_id missing)
```

---

## Дополнительные миграции (опционально)

Если нужны полные возможности биллинга:

### Миграция 008: Billing & Quotas
```bash
# Файл: app/migrations/008_billing_quotas.sql
# Применить через Supabase SQL Editor
```

### Миграция 009: Billing Seed Data
```bash
# Файл: app/migrations/009_billing_seed.sql
# Применить через Supabase SQL Editor
```

---

## Troubleshooting

### Ошибка: "permission denied for table reviews"
**Решение:** Выполнить миграцию под ролью `postgres` (не `app_tenant`).

### Ошибка: "column already exists"
**Решение:** Миграции идемпотентные (`IF NOT EXISTS`), повторное выполнение безопасно.

### Ошибка: "cannot make NOT NULL without checking existing data"
**Решение:** Сначала выполнить бэкфилл (UPDATE), затем добавить NOT NULL constraint.

---

## Контакты и поддержка

**Backend:** `http://localhost:8000`  
**API Docs:** `http://localhost:8000/docs`  
**Frontend:** `http://localhost:3000`

**Test credentials:**
- Email: `test@example.com`
- Password: `TestPassword123!`
- Tenant ID: `11111111-1111-1111-1111-111111111111`
